#!/usr/bin/env python3
"""Read a private iCalendar feed and emit the next desktop agenda events."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy" / "calendar-widget" / "config.json"
HORIZON_DAYS = 30
MAX_EVENTS = 8
WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
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
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value.astimezone()


def parse_datetime(value: str, params: dict[str, str]) -> tuple[datetime, bool]:
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=datetime.now().astimezone().tzinfo), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(), False
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid = params.get("TZID")
    if tzid:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tzid))
        except Exception:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return localize(parsed), False


def parse_until(value: str) -> datetime:
    parsed, _ = parse_datetime(value, {})
    return parsed


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


def parse_events(text: str, now: datetime, horizon: date) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if not current or "DTSTART" not in current or current.get("STATUS", ({}, ""))[1].upper() == "CANCELLED":
                current = None
                continue
            start_params, start_value = current["DTSTART"]
            start, all_day = parse_datetime(start_value, start_params)
            rule = current.get("RRULE", ({}, ""))[1]
            starts = occurrence_dates(start, rule, horizon) if rule else [start]
            for occurrence in starts:
                if occurrence < now or occurrence.date() > horizon:
                    continue
                day = "HOY" if occurrence.date() == now.date() else "MAÑANA" if occurrence.date() == now.date() + timedelta(days=1) else f"{WEEKDAYS[occurrence.weekday()]} {occurrence.day}"
                result.append({
                    "day": day,
                    "time": "TODO EL DÍA" if all_day else occurrence.strftime("%H:%M"),
                    "title": unescape(current.get("SUMMARY", ({}, "Sin título"))[1]) or "Sin título",
                    "url": event_link(current),
                    "sort": occurrence.isoformat(),
                })
            current = None
        elif current is not None and ":" in line:
            name, params, value = property_value(line)
            current[name] = (params, value)
    result.sort(key=lambda item: item["sort"])
    for item in result:
        item.pop("sort", None)
    return result[:MAX_EVENTS]


def load_config() -> str:
    env_url = os.environ.get("OMARCHY_CALENDAR_ICS_URL", "").strip()
    if env_url:
        return env_url
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, json.JSONDecodeError):
        return ""
    return str(config.get("icalUrl") or config.get("ical_url") or config.get("url") or "").strip()


def is_secure_ical_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


class HTTPSOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_secure_ical_url(newurl):
            raise ValueError("La URL iCalendar redirige a una conexión no segura")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main() -> None:
    url = load_config()
    if not url:
        json_out(error=f"Configura tu URL privada iCalendar en {CONFIG_PATH}", events=[])
        return
    if not is_secure_ical_url(url):
        json_out(error="La URL iCalendar debe comenzar con https://", events=[])
        return
    request = Request(url, headers={"User-Agent": "omarchy-calendar-agenda/1.0"})
    opener = build_opener(HTTPSOnlyRedirectHandler())
    with opener.open(request, timeout=15) as response:
        calendar = response.read(2_000_000).decode("utf-8-sig", errors="replace")
    now = datetime.now().astimezone()
    events = parse_events(calendar, now, now.date() + timedelta(days=HORIZON_DAYS))
    json_out(updated=now.isoformat(), events=events)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        json_out(error="No se pudo actualizar el calendario. Revisa la URL privada iCalendar.", events=[])
