import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "calendar_events.py"
spec = importlib.util.spec_from_file_location("calendar_events", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CalendarEventsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
