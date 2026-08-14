#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="io.github.brm-src.calendar-agenda"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_DIR="$CONFIG_HOME/omarchy/calendar-widget"
CONFIG_PATH="$CONFIG_DIR/config.json"

if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$CONFIG_PATH"
  rmdir "$CONFIG_DIR" 2>/dev/null || true
  if command -v omarchy >/dev/null 2>&1; then
    if omarchy plugin remove "$PLUGIN_ID" --yes; then
      omarchy restart shell
    else
      printf 'El plugin ya no estaba instalado; se limpió la configuración local.\n'
    fi
  fi
  printf 'Desktop Agenda eliminado.\n'
  exit 0
fi

printf 'Desktop Agenda necesita la URL privada iCalendar (.ics).\n'
printf 'No se guarda en el repositorio ni se envía a ningún servicio externo.\n\n'
read -r -p 'URL privada iCalendar: ' ical_url

if [[ ! "$ical_url" =~ ^https:// ]]; then
  printf 'Error: la URL debe comenzar con https://.\n' >&2
  exit 1
fi

umask 077
mkdir -p "$CONFIG_DIR"
OMARCHY_CALENDAR_ICS_URL="$ical_url" OMARCHY_CALENDAR_CONFIG_PATH="$CONFIG_PATH" python3 - <<'PY'
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

url = os.environ["OMARCHY_CALENDAR_ICS_URL"].strip()
path = Path(os.environ["OMARCHY_CALENDAR_CONFIG_PATH"])
try:
    request = Request(url, headers={"User-Agent": "omarchy-calendar-agenda-setup/1.0"})
    with urlopen(request, timeout=15) as response:
        sample = response.read(512_000).decode("utf-8-sig", errors="replace")
except Exception:
    raise SystemExit("No se pudo leer la URL. Revisa que sea una URL iCalendar privada válida.")

if "BEGIN:VCALENDAR" not in sample:
    raise SystemExit("La URL respondió, pero no parece ser un calendario iCalendar (.ics).")

tmp = path.with_name(path.name + ".tmp")
tmp.write_text(json.dumps({"icalUrl": url}, ensure_ascii=False) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY

chmod 600 "$CONFIG_PATH"
printf '\nCalendario configurado en %s\n' "$CONFIG_PATH"
if command -v omarchy >/dev/null 2>&1; then
  omarchy restart shell
else
  printf 'Reinicia el shell de Omarchy para aplicar el cambio.\n'
fi
