# Desktop Agenda for Omarchy

<p align="center">
  <a href="https://www.ko-fi.com/brmcl"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support me on Ko-fi" /></a>
</p>

[Español](README.es.md)

A small desktop agenda for Omarchy Quattro. It shows upcoming meetings below the top bar, without opening a calendar app and without using a vendor API.

![Desktop Agenda preview](preview.png)

It works with any service that publishes an iCalendar (`.ics`) feed: Google Calendar, Nextcloud, Fastmail, institutional calendars, or a self-hosted calendar.

## What it does

- Keeps upcoming meetings visible while you are on the desktop.
- Starts compact so it does not take over the screen.
- Expands to a monthly calendar and a longer agenda.
- Filters the agenda by day.
- Combines multiple calendars in one widget.
- Opens Zoom, Google Meet, and other event links with one click.
- Uses no new account, API key, OAuth flow, or third-party proxy.

## Install

Requires Omarchy Quattro, Quickshell, and Python 3.9+.

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --enable --yes
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh
```

The setup helper asks for one or more private iCalendar URLs and a name for each calendar. Press Enter on an empty URL when you are done.

It:

- requires HTTPS;
- verifies that every URL returns a real iCalendar feed;
- stores the configuration with mode `600`;
- restarts the Omarchy shell so the agenda is ready.

It does not install packages or execute code downloaded from the network.

To inspect the source before enabling it:

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --yes
omarchy plugin enable io.github.brm-src.calendar-agenda
```

## Configure it

### Google Calendar

1. Open Google Calendar.
2. Open Settings with the gear icon.
3. Select the calendar in the left sidebar.
4. Scroll to **Integrate calendar**.
5. Copy **Secret address in iCal format**.
6. Paste it when `configure-calendar.sh` asks for a URL.

The URL normally ends in `/basic.ics`. Do not paste the Google Calendar page URL or a public address when the calendar is private.

### Multiple calendars

Run the helper again and add every feed you want:

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh
```

The configuration is stored at `~/.config/omarchy/calendar-widget/config.json`:

```json
{
  "calendars": [
    {"name": "Work", "icalUrl": "https://example/work.ics"},
    {"name": "Personal", "icalUrl": "https://example/personal.ics"}
  ]
}
```

The legacy single-calendar `icalUrl` format is still accepted.

## Interface behavior

The card sits in the upper-right corner of the desktop, below the top bar. When an application window is active, it hides completely so it never overlays a window or bleeds through a translucent terminal.

- **`+`**: expand the agenda and show the monthly calendar.
- **`−`**: return to the compact view.
- **`↻`**: refresh every feed immediately.
- **Day with events**: click it to filter the list to that day.
- **Selected day**: click it again to clear the filter.
- **Empty day**: opens Google Calendar directly on that date so you can create an event.
- **Event row**: opens the event link, preferring Zoom or Google Meet links when present.
- **All-day events**: remain all-day events; the plugin does not invent a time.

The compact view shows the next four events. The expanded view shows up to eight events and the current month.

## Privacy and security

The plugin uses no vendor API, OAuth, client secret, or shared credential. Your machine fetches the feeds you configure directly.

A private iCalendar URL is a bearer secret: anyone who obtains it may read that calendar. Therefore:

- use only `https://` URLs;
- never publish the URL in issues, screenshots, or repositories;
- regenerate it at the calendar provider if it leaks;
- keep the local configuration at mode `600`.

Check the permissions with:

```bash
stat -c '%a %n' ~/.config/omarchy/calendar-widget/config.json
```

The expected output is `600`.

## Troubleshooting

### No events appear

1. Inspect the configured feed:

   ```bash
   python3 ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/calendar_events.py
   ```

2. If it reports a configuration error, run the helper again:

   ```bash
   bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh
   ```

3. Events beyond the next 30 days are intentionally not shown.
4. If the URL stopped working, generate a new secret iCal URL at the provider.

### The agenda is not visible

It is intentionally below windows. Minimize or close applications to return to a clean desktop.

### The feed changed but the widget did not

Press `↻`. Automatic refresh runs every five minutes.

## Uninstall

Remove the plugin and its local configuration:

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh --remove
omarchy plugin remove io.github.brm-src.calendar-agenda --yes
```

This does not delete remote events or change your calendar account.

## Development and validation

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile calendar_events.py
qmllint -I /usr/share/omarchy/shell CalendarAgenda.qml
omarchy plugin validate .
bash -n configure-calendar.sh
git diff --check
```

## Marketplace

Desktop Agenda is a small productivity plugin for Omarchy: local, vendor-neutral, and compatible with any HTTPS iCalendar feed. Marketplace listing is not a substitute for reviewing source code; Omarchy plugins run unsandboxed.

## License

MIT. See [LICENSE](LICENSE).
