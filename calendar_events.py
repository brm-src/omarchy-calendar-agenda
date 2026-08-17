#!/usr/bin/env python3
"""Read a private iCalendar feed and emit the next desktop agenda events."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy" / "calendar-widget" / "config.json"
HORIZON_DAYS = 30
MAX_EVENTS = 8
MAX_FEED_BYTES = 8_000_000
BYDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
LANGUAGES = {"en", "es", "pt"}

WEEKDAYS_BY_LANG = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "es": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
    "pt": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"],
}

DAY_LABELS = {
    "en": {"today": "TODAY", "tomorrow": "TOMORROW", "allDay": "ALL DAY", "calendar": "Calendar", "untitled": "Untitled"},
    "es": {"today": "HOY", "tomorrow": "MAÑANA", "allDay": "TODO EL DÍA", "calendar": "Calendario", "untitled": "Sin título"},
    "pt": {"today": "HOJE", "tomorrow": "AMANHÃ", "allDay": "DIA TODO", "calendar": "Calendário", "untitled": "Sem título"},
}

ERROR_MESSAGES = {
    "en": {
        "configure": "Configure at least one calendar in {path}",
        "could_not_update": "Could not update: {names}",
        "generic_failure": "Could not update the calendar. Check the private iCalendar URL.",
    },
    "es": {
        "configure": "Configura al menos un calendario en {path}",
        "could_not_update": "No se pudo actualizar: {names}",
        "generic_failure": "No se pudo actualizar el calendario. Revisa la URL privada iCalendar.",
    },
    "pt": {
        "configure": "Configure ao menos um calendário em {path}",
        "could_not_update": "Não foi possível atualizar: {names}",
        "generic_failure": "Não foi possível atualizar o calendário. Verifique a URL privada iCalendar.",
    },
}


def json_out(**payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def unfold(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def property_value(line: str) -> tuple[str, dict[str, str], str]:
    name_and_params, value = line.split(":", 1)
    parts = name_and_params.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for item in parts[1:]:
        if "=" in item:
            key, raw = item.split("=", 1)
            params[key.upper()] = raw.strip('"')
    return name, params, value


def resolve_timezone(name: str) -> tzinfo:
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo


def localize(value: datetime, tz: tzinfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def parse_datetime(value: str, params: dict[str, str], tz: tzinfo) -> tuple[datetime, bool]:
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=tz), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(tz), False
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid = params.get("TZID")
    if tzid:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tzid))
        except Exception:
            parsed = parsed.replace(tzinfo=tz)
    return localize(parsed, tz), False


def parse_until(value: str, tz: tzinfo) -> datetime:
    parsed, _ = parse_datetime(value, {}, tz)
    return parsed


def parse_rrule(value: str) -> dict[str, str]:
    return {key.upper(): raw for key, raw in (part.split("=", 1) for part in value.split(";") if "=" in part)}


def occurrence_dates(start: datetime, rule_value: str, horizon: date, tz: tzinfo) -> Iterable[datetime]:
    rule = parse_rrule(rule_value)
    freq = rule.get("FREQ", "").upper()
    interval = max(1, int(rule.get("INTERVAL", "1")))
    count_limit = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = parse_until(rule["UNTIL"], tz) if rule.get("UNTIL") else None
    bydays = {BYDAY[item[-2:]] for item in rule.get("BYDAY", "").split(",") if item[-2:] in BYDAY}
    bymonthday = int(rule["BYMONTHDAY"]) if rule.get("BYMONTHDAY", "").lstrip("-").isdigit() else start.day
    generated = 0
    cursor = start
    limit = datetime.combine(horizon + timedelta(days=1), datetime.min.time(), tzinfo=start.tzinfo)

    while cursor < limit and cursor.date() <= horizon:
        matches = False
        if freq == "DAILY":
            matches = (cursor.date() - start.date()).days % interval == 0
        elif freq == "WEEKLY":
            week_delta = (cursor.date() - start.date()).days // 7
            matches = week_delta >= 0 and week_delta % interval == 0 and (not bydays or cursor.weekday() in bydays)
        elif freq == "MONTHLY":
            months = (cursor.year - start.year) * 12 + cursor.month - start.month
            matches = months >= 0 and months % interval == 0 and cursor.day == bymonthday
        elif freq == "YEARLY":
            matches = (cursor.year - start.year) % interval == 0 and cursor.month == start.month and cursor.day == start.day

        if matches:
            generated += 1
            if count_limit is not None and generated > count_limit:
                break
            if until is not None and cursor > until:
                break
            yield cursor
        cursor += timedelta(days=1)


def event_link(values: dict[str, tuple[dict[str, str], str]]) -> str:
    candidates = [values.get("URL", ({}, ""))[1], values.get("X-GOOGLE-HANGOUT", ({}, ""))[1]]
    description = values.get("DESCRIPTION", ({}, ""))[1]
    candidates.append(description)
    pattern = re.compile(r"https?://(?:[\w.-]+\.)?(?:zoom\.us|meet\.google\.com)/[^\s<>\"']+")
    for candidate in candidates:
        match = pattern.search(candidate)
        if match:
            return match.group(0).rstrip(".,;:)]}")
    return next((value for value in candidates if value.startswith("http")), "")


def parse_events(text: str, now: datetime, horizon: date, calendar_name: str = "", language: str = "en", tz: tzinfo | None = None) -> list[dict[str, object]]:
    tz = tz or now.tzinfo or resolve_timezone("")
    labels = DAY_LABELS.get(language, DAY_LABELS["en"])
    weekdays = WEEKDAYS_BY_LANG.get(language, WEEKDAYS_BY_LANG["en"])
    result: list[dict[str, object]] = []
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if not current or "DTSTART" not in current or current.get("STATUS", ({}, ""))[1].upper() == "CANCELLED":
                current = None
                continue
            start_params, start_value = current["DTSTART"]
            start, all_day = parse_datetime(start_value, start_params, tz)
            rule = current.get("RRULE", ({}, ""))[1]
            starts = occurrence_dates(start, rule, horizon, tz) if rule else [start]
            for occurrence in starts:
                if occurrence < now or occurrence.date() > horizon:
                    continue
                day = labels["today"] if occurrence.date() == now.date() else labels["tomorrow"] if occurrence.date() == now.date() + timedelta(days=1) else f"{weekdays[occurrence.weekday()]} {occurrence.day}"
                result.append({
                    "date": occurrence.date().isoformat(),
                    "day": day,
                    "time": labels["allDay"] if all_day else occurrence.strftime("%H:%M"),
                    "allDay": all_day,
                    "calendar": calendar_name or labels["calendar"],
                    "title": unescape(current.get("SUMMARY", ({}, labels["untitled"]))[1]) or labels["untitled"],
                    "url": event_link(current),
                    "sort": occurrence.isoformat(),
                })
            current = None
        elif current is not None and ":" in line:
            name, params, value = property_value(line)
            current[name] = (params, value)
    result.sort(key=lambda item: str(item["sort"]))
    for item in result:
        item.pop("sort", None)
    return result[:MAX_EVENTS]


def normalize_calendar_sources(config: object) -> list[dict[str, str]]:
    if not isinstance(config, dict):
        return []

    raw_calendars = config.get("calendars")
    if isinstance(raw_calendars, list):
        sources: list[dict[str, str]] = []
        for index, item in enumerate(raw_calendars, start=1):
            if not isinstance(item, dict):
                continue
            url = str(item.get("icalUrl") or item.get("url") or "").strip()
            if not url:
                continue
            name = str(item.get("name") or f"Calendar {index}").strip()
            sources.append({"name": name or f"Calendar {index}", "icalUrl": url})
        return sources

    url = str(config.get("icalUrl") or config.get("ical_url") or config.get("url") or "").strip()
    return [{"name": "Calendar", "icalUrl": url}] if url else []


def load_config() -> dict[str, object]:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            config = {}
    except FileNotFoundError:
        config = {}
    except (OSError, json.JSONDecodeError):
        config = {}

    env_url = os.environ.get("OMARCHY_CALENDAR_ICS_URL", "").strip()
    if env_url:
        config = {**config, "icalUrl": env_url}
        config.pop("calendars", None)
    return config


def resolve_language(config: dict[str, object]) -> str:
    language = str(config.get("language") or "en").strip().lower()
    return language if language in LANGUAGES else "en"


def is_secure_ical_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def fetch_calendar(url: str) -> str:
    request = Request(url, headers={"User-Agent": "omarchy-calendar-agenda/1.0"})
    opener = build_opener(HTTPSOnlyRedirectHandler())
    with opener.open(request, timeout=15) as response:
        return read_calendar_response(response)


def read_calendar_response(response: object) -> str:
    data = response.read(MAX_FEED_BYTES + 1)  # type: ignore[attr-defined]
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("The iCalendar feed exceeds the allowed limit")
    return data.decode("utf-8-sig", errors="replace")


class HTTPSOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_secure_ical_url(newurl):
            raise ValueError("The iCalendar URL redirects to an insecure connection")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main() -> None:
    config = load_config()
    sources = normalize_calendar_sources(config)
    language = resolve_language(config)
    tz_name = str(config.get("timezone") or "").strip()
    tz = resolve_timezone(tz_name)
    messages = ERROR_MESSAGES[language]

    if not sources:
        json_out(error=messages["configure"].format(path=CONFIG_PATH), events=[], calendars=[], language=language, timezone=tz_name)
        return

    now = datetime.now(tz)
    horizon = now.date() + timedelta(days=HORIZON_DAYS)
    events: list[dict[str, object]] = []
    errors: list[str] = []
    for source in sources:
        url = source["icalUrl"]
        if not is_secure_ical_url(url):
            errors.append(source["name"])
            continue
        try:
            events.extend(parse_events(fetch_calendar(url), now, horizon, source["name"], language, tz))
        except Exception:
            errors.append(source["name"])

    events.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", "")), str(item.get("title", ""))))
    json_out(
        updated=now.isoformat(),
        events=events[:MAX_EVENTS],
        calendars=[source["name"] for source in sources],
        language=language,
        timezone=tz_name,
        error=messages["could_not_update"].format(names=", ".join(errors)) if errors and not events else "",
    )


def apply_settings(args: list[str]) -> None:
    overrides: dict[str, str] = {}
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        overrides[key] = value

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raw = {}

    if "language" in overrides:
        language = overrides["language"].strip().lower()
        if language not in LANGUAGES:
            json_out(ok=False, error=f"Unsupported language: {language}")
            return
        raw["language"] = language

    if "timezone" in overrides:
        tz_name = overrides["timezone"].strip()
        if tz_name:
            try:
                ZoneInfo(tz_name)
            except Exception:
                json_out(ok=False, error=f"Unknown timezone: {tz_name}")
                return
            raw["timezone"] = tz_name
        else:
            raw.pop("timezone", None)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)
    json_out(ok=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--set":
            apply_settings(sys.argv[2:])
        else:
            main()
    except Exception:
        json_out(error=ERROR_MESSAGES[resolve_language(load_config())]["generic_failure"], events=[])
