# Desktop Agenda for Omarchy

A small, quiet desktop overlay for Omarchy Quattro. It shows the next events from a private iCalendar (`.ics`) feed in the top-right corner, below the bar.

It is intentionally source-agnostic: Google Calendar, Nextcloud, Fastmail, a self-hosted calendar, or any service that exposes an iCalendar URL can provide the feed.

## Why there are no API keys

The plugin does not use a vendor API, OAuth client, or shared credential. Each user keeps their own private iCalendar URL in a local file. The URL is a bearer secret: do not publish it or paste it into issue reports.

## Requirements

- Omarchy Quattro with Quickshell
- Python 3.9+
- A private iCalendar URL

No Python packages are required.

## Install

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --enable --yes
```

Then reload the shell:

```bash
omarchy restart shell
```

The plugin starts disabled until you explicitly enable it through the install command. Review the repository before enabling it; Omarchy plugins run unsandboxed inside the shell process.

## Configure

Create the local configuration directory and file:

```bash
mkdir -p ~/.config/omarchy/calendar-widget
chmod 700 ~/.config/omarchy/calendar-widget
printf '%s\n' '{"icalUrl":"https://calendar.example/private/basic.ics"}' > ~/.config/omarchy/calendar-widget/config.json
chmod 600 ~/.config/omarchy/calendar-widget/config.json
```

Replace the example URL with your own private `.ics` URL. The plugin refreshes every five minutes and displays up to eight events within the next 30 days.

You can also test without writing a config file:

```bash
OMARCHY_CALENDAR_ICS_URL='https://calendar.example/private/basic.ics' \\
  python3 ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/calendar_events.py
```

Click an event to open its URL with the desktop default browser. Google Meet and Zoom links found in the event description are preferred.

## Security

- The repository contains no credentials.
- `config.json` is user-local and should remain mode `600`.
- Private iCalendar URLs grant access to calendar data. Treat them like passwords.
- The feed is fetched directly by the local machine; no third-party proxy is involved.
- Do not use a public calendar URL for private events.

## Troubleshooting

If the card says the calendar is not configured, check the path and permissions:

```bash
cat ~/.config/omarchy/calendar-widget/config.json
stat -c '%a %n' ~/.config/omarchy/calendar-widget/config.json
```

If the card cannot update, fetch the feed directly:

```bash
curl -fsSL --max-time 15 'https://calendar.example/private/basic.ics' | head
```

The plugin intentionally hides the actual URL from error messages.

## Uninstall

```bash
omarchy plugin remove io.github.brm-src.calendar-agenda --yes
rm -f ~/.config/omarchy/calendar-widget/config.json
rmdir ~/.config/omarchy/calendar-widget 2>/dev/null || true
omarchy restart shell
```

The uninstall command does not touch any calendar account or remote data.

## Development

Run the parser tests:

```bash
python3 -m unittest discover -s tests -v
```

Validate the Omarchy manifest and QML on a machine with Omarchy installed:

```bash
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" CalendarAgenda.qml
```

## License

MIT. See [LICENSE](LICENSE).
