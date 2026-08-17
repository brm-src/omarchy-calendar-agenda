import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
SUMMARY:Team sync\\, important
URL:https://example.com/event
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Team sync, important")
        self.assertEqual(events[0]["time"], "08:00")
        self.assertEqual(events[0]["url"], "https://example.com/event")
        self.assertEqual(events[0]["date"], "2026-08-14")
        self.assertFalse(events[0]["allDay"])

    def test_parses_all_day_event_with_iso_date(self):
        now = datetime.fromisoformat("2026-08-14T09:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260815
SUMMARY:Work day
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date() + module.timedelta(days=2))
        self.assertEqual(events[0]["date"], "2026-08-15")
        self.assertTrue(events[0]["allDay"])

    def test_keeps_calendar_name_on_events(self):
        now = datetime.fromisoformat("2026-08-14T07:00:00-04:00")
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T120000Z
SUMMARY:Work
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date(), "Work")
        self.assertEqual(events[0]["calendar"], "Work")

    def test_normalizes_multiple_calendar_sources_and_legacy_config(self):
        self.assertEqual(
            module.normalize_calendar_sources({"icalUrl": "https://one.example/a.ics"}),
            [{"name": "Calendar", "icalUrl": "https://one.example/a.ics"}],
        )
        self.assertEqual(
            module.normalize_calendar_sources({
                "calendars": [
                    {"name": "Work", "icalUrl": "https://one.example/a.ics"},
                    {"name": "Personal", "url": "https://two.example/b.ics"},
                ]
            }),
            [
                {"name": "Work", "icalUrl": "https://one.example/a.ics"},
                {"name": "Personal", "icalUrl": "https://two.example/b.ics"},
            ],
        )

    def test_reads_complete_calendar_response_until_safe_limit(self):
        body = b"BEGIN:VCALENDAR\n" + (b"x" * 128)
        self.assertEqual(module.read_calendar_response(io.BytesIO(body)), body.decode())

    def test_rejects_calendar_response_over_safe_limit(self):
        with self.assertRaises(ValueError):
            module.read_calendar_response(io.BytesIO(b"x" * (module.MAX_FEED_BYTES + 1)))

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
SUMMARY:Follow-up
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date().replace(day=31))
        self.assertEqual([event["day"] for event in events], ["TODAY", "Wed 19", "Mon 24"])

    def test_localizes_utc_event_to_configured_timezone(self):
        tz = ZoneInfo("Pacific/Kiritimati")  # fixed UTC+14, no DST
        now = datetime(2026, 8, 15, 0, 30, tzinfo=tz)
        ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260814T233000Z
SUMMARY:Cross-midnight
END:VEVENT
END:VCALENDAR
"""
        events = module.parse_events(ics, now, now.date(), tz=tz)
        self.assertEqual(events[0]["day"], "TODAY")
        self.assertEqual(events[0]["date"], "2026-08-15")

    def test_apply_settings_round_trips_without_dropping_calendars(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(json.dumps({"calendars": [{"name": "Work", "icalUrl": "https://one.example/a.ics"}]}), encoding="utf-8")
            original_path = module.CONFIG_PATH
            module.CONFIG_PATH = config_path
            try:
                module.apply_settings(["language=es", "timezone=America/Sao_Paulo"])
            finally:
                module.CONFIG_PATH = original_path

            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["language"], "es")
            self.assertEqual(saved["timezone"], "America/Sao_Paulo")
            self.assertEqual(saved["calendars"], [{"name": "Work", "icalUrl": "https://one.example/a.ics"}])


if __name__ == "__main__":
    unittest.main()
