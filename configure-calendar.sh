#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="io.github.brm-src.calendar-agenda"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_DIR="$CONFIG_HOME/omarchy/calendar-widget"
CONFIG_PATH="$CONFIG_DIR/config.json"

if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$CONFIG_PATH"
  rmdir "$CONFIG_DIR" 2>/dev/null || true
  printf 'Calendar configuration removed.\n'
  exit 0
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf 'Usage: %s [--remove]\n' "$0"
  printf 'With no arguments, replaces the configuration and lets you enter multiple calendars.\n'
  exit 0
fi

printf 'Desktop Agenda: add one or more iCalendar calendars.\n'
printf 'Press Enter with an empty URL to finish.\n\n'

umask 077
mkdir -p "$CONFIG_DIR"
entries_file="$(mktemp "$CONFIG_DIR/.calendars.XXXXXX")"
trap 'rm -f "$entries_file"' EXIT

count=0
while true; do
  read -r -p 'Private iCalendar URL (.ics): ' ical_url || break
  [[ -n "$ical_url" ]] || break
  read -r -p 'Name (optional): ' calendar_name || calendar_name=""
  calendar_name="${calendar_name:-Calendar $((count + 1))}"
  printf '%s\t%s\n' "$calendar_name" "$ical_url" >> "$entries_file"
  count=$((count + 1))
done

if (( count == 0 )); then
  printf 'No calendar was added.\n' >&2
  exit 1
fi

CALENDAR_ENTRIES_FILE="$entries_file" CALENDAR_CONFIG_PATH="$CONFIG_PATH" python3 - <<'PY'
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

entries_path = Path(os.environ["CALENDAR_ENTRIES_FILE"])
config_path = Path(os.environ["CALENDAR_CONFIG_PATH"])
entries = []

def is_secure_url(value):
    parsed = urlsplit(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)

class HTTPSOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not is_secure_url(newurl):
            raise ValueError("URL redirects to an insecure connection")
        return super().redirect_request(request, fp, code, msg, headers, newurl)

opener = build_opener(HTTPSOnlyRedirectHandler())
for line in entries_path.read_text(encoding="utf-8").splitlines():
    name, url = line.split("\t", 1)
    url = url.strip()
    if not is_secure_url(url):
        raise SystemExit(f"The URL for {name} must start with https://")
    try:
        request = Request(url, headers={"User-Agent": "omarchy-calendar-agenda-setup/1.0"})
        with opener.open(request, timeout=15) as response:
            sample = response.read(512_000).decode("utf-8-sig", errors="replace")
    except Exception:
        raise SystemExit(f"Could not read calendar: {name}")
    if "BEGIN:VCALENDAR" not in sample:
        raise SystemExit(f"The URL for {name} does not look like an iCalendar (.ics) feed")
    entries.append({"name": name, "icalUrl": url})

try:
    existing = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(existing, dict):
        existing = {}
except (FileNotFoundError, OSError, json.JSONDecodeError):
    existing = {}
existing["calendars"] = entries

tmp = config_path.with_name(config_path.name + ".tmp")
tmp.write_text(json.dumps(existing, ensure_ascii=False) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, config_path)
PY
chmod 600 "$CONFIG_PATH"
printf '\nCalendars configured: %s\n' "$count"
printf 'File: %s\n' "$CONFIG_PATH"
if command -v omarchy >/dev/null 2>&1; then
  omarchy restart shell
fi
