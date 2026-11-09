#!/usr/bin/env python3
"""Read a private iCalendar feed and emit the next desktop agenda events."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy" / "calendar-widget" / "config.json"
HORIZON_DAYS = 30
MAX_EVENTS = 64
MAX_FEED_BYTES = 8_000_000
MAX_CALENDARS = 16
MAX_CALENDAR_NAME = 128
MAX_URL_LENGTH = 4096
WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
LANG = "es"


def _t(es: str, en: str) -> str:
    return es if LANG == "es" else en


BYDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


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


def localize(value: datetime) -> datetime:
    # A naive datetime is local wall time; astimezone() applies that date's own DST offset.
    return value.astimezone()


def parse_datetime(value: str, params: dict[str, str]) -> tuple[datetime, bool]:
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").astimezone(), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(), False
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid = params.get("TZID")
    if tzid:
        try:
            # Keep the named zone: recurrences must step in wall-clock time across DST.
            return parsed.replace(tzinfo=ZoneInfo(tzid)), False
        except Exception:
            pass
    return localize(parsed), False


def parse_until(value: str) -> datetime:
    parsed, _ = parse_datetime(value, {})
    return parsed


def parse_duration(value: str) -> timedelta | None:
    match = re.fullmatch(
        r"P(?:(?P<weeks>\d+)W|(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?)",
        value.strip().upper(),
    )
    if not match or not any(match.group(name) for name in ("weeks", "days", "hours", "minutes", "seconds")):
        return None
    return timedelta(**{name: int(match.group(name) or 0) for name in ("weeks", "days", "hours", "minutes", "seconds")})


def parse_rrule(value: str) -> dict[str, str]:
    return {key.upper(): raw for key, raw in (part.split("=", 1) for part in value.split(";") if "=" in part)}


def occurrence_dates(start: datetime, rule_value: str, horizon: date) -> Iterable[datetime]:
    rule = parse_rrule(rule_value)
    freq = rule.get("FREQ", "").upper()
    interval = max(1, int(rule.get("INTERVAL", "1")))
    count_limit = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = parse_until(rule["UNTIL"]) if rule.get("UNTIL") else None
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
            weekdays = bydays or {start.weekday()}
            matches = week_delta >= 0 and week_delta % interval == 0 and cursor.weekday() in weekdays
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


def active_event_dates(start: datetime, end: datetime | None, all_day: bool, horizon: date) -> Iterable[datetime]:
    """Yield each calendar day touched by one event, capped by the horizon."""
    last_date = start.date()
    if end is not None and end > start:
        last_date = (end.date() - timedelta(days=1)) if all_day else (end - timedelta(microseconds=1)).date()
    cursor = start.date()
    while cursor <= last_date and cursor <= horizon:
        yield datetime.combine(cursor, start.timetz())
        cursor += timedelta(days=1)


def event_link(values: dict[str, tuple[dict[str, str], str]]) -> str:
    def value(name: str) -> str:
        return unescape(values.get(name, ({}, ""))[1])

    candidates = [value("URL"), value("X-GOOGLE-HANGOUT"), value("CONFERENCE"), value("DESCRIPTION")]
    pattern = re.compile(r"https?://(?:[\w.-]+\.)?(?:zoom\.us|meet\.google\.com)/[^\s<>\"']+")
    for candidate in candidates:
        match = pattern.search(candidate)
        if match:
            return match.group(0).rstrip(".,;:)]}")
    return next((candidate.splitlines()[0] for candidate in candidates if candidate.startswith("http")), "")


def parse_events(text: str, now: datetime, horizon: date, calendar_name: str = "") -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    vevents: list[dict] = []
    current: dict | None = None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {"EXDATE": []}
        elif line == "END:VEVENT":
            if current and "DTSTART" in current:
                vevents.append(current)
            current = None
        elif current is not None and ":" in line:
            name, params, value = property_value(line)
            if name == "EXDATE":
                current["EXDATE"].extend((params, item) for item in value.split(",") if item)
            else:
                current[name] = (params, value)

    def moment(entry: tuple[dict[str, str], str]) -> datetime | None:
        try:
            return parse_datetime(*reversed(entry))[0]
        except ValueError:
            return None

    # A RECURRENCE-ID event replaces (or cancels) one occurrence of its series;
    # EXDATE removes one. Both must hide the series' own copy of that occurrence.
    skipped: dict[str, set[datetime]] = {}
    for event in vevents:
        uid = event.get("UID", ({}, ""))[1]
        hidden = skipped.setdefault(uid, set())
        if "RECURRENCE-ID" in event:
            hidden.add(moment(event["RECURRENCE-ID"]))
        if "RRULE" in event:
            hidden.update(moment(entry) for entry in event["EXDATE"])

    for current in vevents:
        if current.get("STATUS", ({}, ""))[1].upper() == "CANCELLED":
            continue
        hidden = skipped.get(current.get("UID", ({}, ""))[1], set()) if "RRULE" in current else set()
        start_params, start_value = current["DTSTART"]
        start, all_day = parse_datetime(start_value, start_params)
        end: datetime | None = None
        if "DTEND" in current:
            end_params, end_value = current["DTEND"]
            try:
                end, end_all_day = parse_datetime(end_value, end_params)
                if end_all_day != all_day or end <= start:
                    end = None
            except ValueError:
                end = None
        if end is None and "DURATION" in current:
            duration = parse_duration(current["DURATION"][1])
            if duration and duration > timedelta(0):
                end = start + duration
        rule = current.get("RRULE", ({}, ""))[1]
        starts = occurrence_dates(start, rule, horizon) if rule else [start]
        for occurrence in starts:
            if occurrence in hidden:
                continue
            if not all_day:
                occurrence = occurrence.astimezone()
            if end is not None:
                duration = end - start
                occurrence_end = occurrence + duration
                if not all_day and occurrence_end <= now:
                    continue
            else:
                occurrence_end = None
                if not all_day and occurrence < now:
                    continue
            for active_date in active_event_dates(occurrence, occurrence_end, all_day, horizon):
                if active_date.date() < now.date():
                    continue
                day = "HOY" if active_date.date() == now.date() else "MAÑANA" if active_date.date() == now.date() + timedelta(days=1) else f"{WEEKDAYS[active_date.weekday()]} {active_date.day}"
                result.append({
                    "date": active_date.date().isoformat(),
                    "day": day,
                    "time": "TODO EL DÍA" if all_day else occurrence.strftime("%H:%M"),
                    "allDay": all_day,
                    "calendar": calendar_name or _t("Calendario", "Calendar"),
                    "location": unescape(current.get("LOCATION", ({}, ""))[1])[:512],
                    "title": unescape(current.get("SUMMARY", ({}, ""))[1])[:512] or _t("Sin título", "Untitled"),
                    "url": event_link(current),
                    "sort": active_date.isoformat(),
                })
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
            if len(sources) >= MAX_CALENDARS:
                break
            if not isinstance(item, dict):
                continue
            url = str(item.get("icalUrl") or item.get("url") or "").strip()
            if not url or len(url) > MAX_URL_LENGTH:
                continue
            default_name = f"{_t('Calendario', 'Calendar')} {index}"
            name = str(item.get("name") or default_name).strip()[:MAX_CALENDAR_NAME]
            sources.append({"name": name or default_name, "icalUrl": url})
        return sources

    url = str(config.get("icalUrl") or config.get("ical_url") or config.get("url") or "").strip()
    return [{"name": _t("Calendario", "Calendar"), "icalUrl": url}] if url and len(url) <= MAX_URL_LENGTH else []


def load_config() -> dict[str, object]:
    env_url = os.environ.get("OMARCHY_CALENDAR_ICS_URL", "").strip()
    if env_url:
        return {"icalUrl": env_url}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


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
        raise ValueError("El feed iCalendar supera el límite permitido")
    text = data.decode("utf-8-sig", errors="replace")
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("La respuesta no parece un calendario iCalendar")
    return text


class HTTPSOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_secure_ical_url(newurl):
            raise ValueError("La URL iCalendar redirige a una conexión no segura")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--lang", choices=("es", "en"), default="es")
    args, _ = parser.parse_known_args(argv)
    global LANG
    LANG = args.lang

    sources = normalize_calendar_sources(load_config())
    if not sources:
        json_out(error=_t(f"Configura al menos un calendario en {CONFIG_PATH}", f"Configure at least one calendar in {CONFIG_PATH}"), events=[], calendars=[])
        return

    now = datetime.now().astimezone()
    horizon = now.date() + timedelta(days=HORIZON_DAYS)
    events: list[dict[str, object]] = []
    errors: list[str] = []
    for source in sources:
        url = source["icalUrl"]
        if not is_secure_ical_url(url):
            errors.append(source["name"])
            continue
        try:
            events.extend(parse_events(fetch_calendar(url), now, horizon, source["name"]))
        except Exception:
            errors.append(source["name"])

    events.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", "")), str(item.get("title", ""))))
    json_out(updated=now.isoformat(), events=events[:MAX_EVENTS], calendars=[source["name"] for source in sources], error=(_t("No se pudo actualizar: ", "Could not refresh: ") + ", ".join(errors)) if errors else "")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        json_out(error=_t("No se pudo actualizar el calendario. Revisa la URL privada iCalendar.", "Could not refresh the calendar. Check the private iCalendar URL."), events=[])
