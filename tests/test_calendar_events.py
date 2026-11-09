import importlib.util
import io
import json
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "calendar_events.py"
spec = importlib.util.spec_from_file_location("calendar_events", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CalendarEventsTests(unittest.TestCase):
    def test_requires_https_for_private_feed(self):
        self.assertTrue(module.is_secure_ical_url("https://calendar.example.test/private.ics"))
        self.assertFalse(module.is_secure_ical_url("http://calendar.example.test/private.ics"))
        self.assertFalse(module.is_secure_ical_url("https://"))

    def test_rejects_https_to_http_redirect(self):
        request = module.Request("https://calendar.example.test/private.ics")
        with self.assertRaises(ValueError):
            module.HTTPSOnlyRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "http://calendar.example.test/private.ics"
            )

    def test_unfolds_long_ical_lines(self):
        text = "SUMMARY:This is a long\\n\n folded title"
        self.assertEqual(module.unfold(text), ["SUMMARY:This is a long\\nfolded title"])

    def test_parses_timed_event_and_unescapes_title(self):
        now = datetime.fromisoformat("2026-08-14T07:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T120000Z
SUMMARY:Reunión\\, importante
URL:https://example.com/event
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Reunión, importante")
        self.assertEqual(events[0]["time"], "08:00")
        self.assertEqual(events[0]["url"], "https://example.com/event")
        self.assertEqual(events[0]["date"], "2026-08-14")
        self.assertFalse(events[0]["allDay"])

    def test_extracts_link_from_escaped_description(self):
        self.assertEqual(
            module.event_link({"DESCRIPTION": ({}, "Join https://meet.google.com/abc\\nDial-in")}),
            "https://meet.google.com/abc",
        )

    def test_extracts_conference_property(self):
        self.assertEqual(
            module.event_link({"CONFERENCE": ({}, "https://teams.example.test/meeting/123")}),
            "https://teams.example.test/meeting/123",
        )

    def test_localizes_missing_event_fields_in_english(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T100000
END:VEVENT
END:VCALENDAR
"""
        previous_language = getattr(module, "LANG")
        try:
            setattr(module, "LANG", "en")
            events = module.parse_events(ics, now, now.date())
        finally:
            setattr(module, "LANG", previous_language)
        self.assertEqual(events[0]["title"], "Untitled")
        self.assertEqual(events[0]["calendar"], "Calendar")

    def test_override_and_exdate_hide_series_occurrences(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:series
DTSTART:20260814T110000
RRULE:FREQ=DAILY;COUNT=4
EXDATE:20260816T110000
SUMMARY:Daily
END:VEVENT
BEGIN:VEVENT
UID:series
RECURRENCE-ID:20260815T110000
DTSTART:20260815T120000
SUMMARY:Daily moved
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date() + module.timedelta(days=7))
        self.assertEqual(
            [(event["date"], event["title"]) for event in events],
            [("2026-08-14", "Daily"), ("2026-08-15", "Daily moved"), ("2026-08-17", "Daily")],
        )

    def test_override_matches_series_across_dst(self):
        now = datetime.fromisoformat("2026-11-09T09:00:00-03:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:weekly
DTSTART;TZID=America/Santiago:20260519T110000
RRULE:FREQ=WEEKLY;BYDAY=TU
SUMMARY:Weekly
END:VEVENT
BEGIN:VEVENT
UID:weekly
RECURRENCE-ID;TZID=America/Santiago:20261110T110000
DTSTART;TZID=America/Santiago:20261110T110000
SUMMARY:Weekly
END:VEVENT
END:VCALENDAR
"""
        try:
            with patch.dict(module.os.environ, {"TZ": "America/Santiago"}):
                time.tzset()
                events = module.parse_events(ics, now, now.date() + module.timedelta(days=1))
        finally:
            time.tzset()
        self.assertEqual([(event["date"], event["time"]) for event in events], [("2026-11-10", "11:00")])

    def test_parses_all_day_event_with_iso_date(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260815
SUMMARY:Día de trabajo
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date() + module.timedelta(days=2))
        self.assertEqual(events[0]["date"], "2026-08-15")
        self.assertTrue(events[0]["allDay"])

    def test_expands_multiday_events_and_keeps_today_all_day(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260813
DTEND;VALUE=DATE:20260815
SUMMARY:Retiro\\, equipo
LOCATION:Casa de campo
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date())
        self.assertEqual([event["date"] for event in events], ["2026-08-14"])
        self.assertEqual(events[0]["location"], "Casa de campo")
        self.assertTrue(events[0]["allDay"])

    def test_expands_timed_event_across_midnight(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T230000
DTEND:20260815T010000
SUMMARY:Turno nocturno
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date() + module.timedelta(days=1))
        self.assertEqual([event["date"] for event in events], ["2026-08-14", "2026-08-15"])

    def test_expands_duration_based_all_day_event(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260815
DURATION:P3D
SUMMARY:Conferencia
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date() + module.timedelta(days=4))
        self.assertEqual([event["date"] for event in events], ["2026-08-15", "2026-08-16", "2026-08-17"])

    def test_keeps_calendar_name_on_events(self):
        now = datetime.fromisoformat("2026-08-14T07:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T120000Z
SUMMARY:Trabajo
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date(), "Trabajo")
        self.assertEqual(events[0]["calendar"], "Trabajo")

    def test_normalizes_multiple_calendar_sources_and_legacy_config(self):
        self.assertEqual(
            module.normalize_calendar_sources({"icalUrl": "https://one.example/a.ics"}),
            [{"name": "Calendario", "icalUrl": "https://one.example/a.ics"}],
        )
        self.assertEqual(
            module.normalize_calendar_sources({
                "calendars": [
                    {"name": "Trabajo", "icalUrl": "https://one.example/a.ics"},
                    {"name": "Personal", "url": "https://two.example/b.ics"},
                ]
            }),
            [
                {"name": "Trabajo", "icalUrl": "https://one.example/a.ics"},
                {"name": "Personal", "icalUrl": "https://two.example/b.ics"},
            ],
        )
        bounded = module.normalize_calendar_sources(
            {
                "calendars": [
                    {"name": "x" * 200, "icalUrl": f"https://example.test/{index}.ics"}
                    for index in range(module.MAX_CALENDARS + 2)
                ]
            }
        )
        self.assertEqual(len(bounded), module.MAX_CALENDARS)
        self.assertEqual(len(bounded[0]["name"]), module.MAX_CALENDAR_NAME)
        self.assertEqual(
            module.normalize_calendar_sources({"icalUrl": "https://x.test/" + "a" * module.MAX_URL_LENGTH}),
            [],
        )

    def test_main_localizes_generated_calendar_name_in_english(self):
        start = datetime.now().astimezone() + module.timedelta(hours=2)
        ics = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{start.strftime("%Y%m%dT%H%M%S")}
SUMMARY:Planning
END:VEVENT
END:VCALENDAR
"""
        output = io.StringIO()
        with patch.object(module, "LANG", "es"), patch.object(
            module,
            "load_config",
            return_value={"icalUrl": "https://example.test/calendar.ics"},
        ), patch.object(module, "fetch_calendar", return_value=ics), redirect_stdout(output):
            module.main(["--lang", "en"])

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["calendars"], ["Calendar"])
        self.assertEqual(payload["events"][0]["calendar"], "Calendar")

    def test_main_localizes_numbered_calendar_name_in_english(self):
        start = datetime.now().astimezone() + module.timedelta(hours=2)
        ics = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{start.strftime("%Y%m%dT%H%M%S")}
SUMMARY:Planning
END:VEVENT
END:VCALENDAR
"""
        output = io.StringIO()
        with patch.object(module, "LANG", "es"), patch.object(
            module,
            "load_config",
            return_value={
                "calendars": [
                    {"icalUrl": "https://example.test/calendar.ics"},
                ]
            },
        ), patch.object(module, "fetch_calendar", return_value=ics), redirect_stdout(output):
            module.main(["--lang", "en"])

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["calendars"], ["Calendar 1"])
        self.assertEqual(payload["events"][0]["calendar"], "Calendar 1")

    def test_reports_partial_feed_failure_with_valid_events(self):
        start = datetime.now().astimezone() + module.timedelta(hours=2)
        ics = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{start.strftime("%Y%m%dT%H%M%S")}
SUMMARY:Evento válido
END:VEVENT
END:VCALENDAR
"""
        output = io.StringIO()
        with patch.object(
            module,
            "load_config",
            return_value={
                "calendars": [
                    {"name": "Trabajo", "icalUrl": "https://work.example/calendar.ics"},
                    {"name": "Personal", "icalUrl": "https://personal.example/calendar.ics"},
                ]
            },
        ), patch.object(module, "fetch_calendar", side_effect=[ics, RuntimeError("offline")]), redirect_stdout(output):
            module.main(["--lang", "en"])

        payload = json.loads(output.getvalue())
        self.assertEqual(len(payload["events"]), 1)
        self.assertIn("Could not refresh: Personal", payload["error"])

    def test_reads_complete_calendar_response_until_safe_limit(self):
        body = b"BEGIN:VCALENDAR\n" + (b"x" * 128)
        self.assertEqual(module.read_calendar_response(io.BytesIO(body)), body.decode())

    def test_rejects_calendar_response_over_safe_limit(self):
        with self.assertRaises(ValueError):
            module.read_calendar_response(io.BytesIO(b"x" * (module.MAX_FEED_BYTES + 1)))

    def test_rejects_non_ical_calendar_response(self):
        with self.assertRaises(ValueError):
            module.read_calendar_response(io.BytesIO(b"<html>login</html>"))

    def test_skips_cancelled_and_expired_events(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T080000
SUMMARY:Expired
END:VEVENT
BEGIN:VEVENT
DTSTART:20260814T100000
STATUS:CANCELLED
SUMMARY:Cancelled
END:VEVENT
END:VCALENDAR
"""
        self.assertEqual(module.parse_events(ics, now, now.date()), [])

    def test_expands_weekly_byday(self):
        now = datetime.fromisoformat("2026-08-17T08:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260817T100000
RRULE:FREQ=WEEKLY;COUNT=3;BYDAY=MO,WE
SUMMARY:Seguimiento
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date().replace(day=31))
        self.assertEqual([event["day"] for event in events], ["HOY", "mié 19", "lun 24"])

    def test_weekly_without_byday_uses_dtstart_weekday(self):
        now = datetime.fromisoformat("2026-08-17T08:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260817T100000
RRULE:FREQ=WEEKLY;COUNT=2
SUMMARY:Seguimiento semanal
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date().replace(day=31))
        self.assertEqual([event["date"] for event in events], ["2026-08-17", "2026-08-24"])


if __name__ == "__main__":
    unittest.main()
