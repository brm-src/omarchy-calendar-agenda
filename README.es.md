# Calendar Agenda para Omarchy

[English](README.md)

Un widget de calendario para la barra de Omarchy. Lee feeds privados iCalendar (`.ics`) directamente desde tu equipo y ofrece vistas de día, semana y mes sin abrir una aplicación de calendario ni usar una API del proveedor.

![Vista previa de Calendar Agenda](preview.png)

Funciona con Google Calendar, Nextcloud, Fastmail, calendarios institucionales y cualquier servicio que publique un feed iCalendar.

## Qué cambia en 1.3

- Vive en la barra de Omarchy en lugar de ocupar el escritorio.
- Vistas de día, semana y mes con navegación anterior/siguiente y botón Hoy.
- Eventos agrupados por día, con calendario y ubicación cuando están disponibles.
- Eventos de varios días y de todo el día expandidos en cada fecha afectada.
- Panel compacto que usa los componentes nativos de Omarchy y sigue el tema activo.
- Atajos: `D`, `W`, `M`, `T`, `[`, `]` y `R`.
- Clic central en el icono para actualizar.
- Mantiene feeds privados HTTPS, varios calendarios y enlaces de eventos.

No incluye OAuth ni un servicio de sincronización nuevo. El flujo iCalendar existente es más pequeño, funciona con cualquier proveedor y no guarda credenciales de cuentas.

## Instalación

Requiere Omarchy Quattro, Quickshell y Python 3.10 o superior.

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --enable --yes
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh
```

El asistente pide una o más URL privadas iCalendar y un nombre opcional para cada calendario. Pulsa Enter con la URL vacía cuando termines. Exige HTTPS, verifica el feed, guarda la configuración con permisos `600` y reinicia el shell.

Para revisar el código antes de activarlo:

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --yes
```

Después agrega **Calendar Agenda** al lado derecho de la barra desde los controles de plugins de Omarchy.

## Configuración

En Google Calendar:

1. Abre la configuración de Google Calendar.
2. Selecciona el calendario.
3. Abre **Integrar el calendario**.
4. Copia **Dirección secreta en formato iCal**.
5. Pégala cuando `configure-calendar.sh` pida una URL.

No pegues la URL de la página de Google Calendar. Una URL privada iCalendar funciona como una contraseña.

Para reemplazar los feeds configurados, ejecuta de nuevo el asistente:

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh
```

La configuración queda en `~/.config/omarchy/calendar-widget/config.json`:

```json
{
  "calendars": [
    {"name": "Trabajo", "icalUrl": "https://ejemplo/trabajo.ics"},
    {"name": "Personal", "icalUrl": "https://ejemplo/personal.ics"}
  ]
}
```

También se acepta el formato antiguo de un solo calendario con `icalUrl`.

## Interfaz

Haz clic en el icono de calendario de la barra para abrir el panel.

- **DÍA**, **SEMANA**, **MES**: cambia el rango visible.
- **Hoy**: vuelve a la semana actual.
- **‹ / ›**: avanza o retrocede según la vista.
- **↻**: actualiza todos los feeds.
- **Fila de evento**: abre el enlace detectado de Zoom, Google Meet u otro evento.
- **D / W / M**: cambia de vista.
- **T**: vuelve a hoy.
- **[ / ]**: retrocede o avanza.
- **R**: actualiza.
- **Esc**: cierra el panel.

El feed se descarga al abrir el panel y se actualiza cada cinco minutos mientras está abierto. Se leen los próximos 30 días y se muestran como máximo 64 eventos para mantener el shell ágil.

## Privacidad y seguridad

El plugin no usa API del proveedor, OAuth, client secrets ni una credencial compartida. Tu equipo descarga los feeds directamente.

- Usa únicamente URL `https://`.
- No publiques una URL privada en issues, capturas ni repositorios.
- Si se filtra, regénérala en el proveedor.
- Mantén la configuración local con permisos `600`.
- El plugin rechaza redirecciones de HTTPS a HTTP.

Comprueba los permisos:

```bash
stat -c '%a %n' ~/.config/omarchy/calendar-widget/config.json
```

La salida esperada es `600`.

## Solución de problemas

Comprueba directamente la respuesta del feed:

```bash
python3 ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/calendar_events.py
```

Si pide configurar el calendario, ejecuta de nuevo el asistente. Los eventos posteriores a 30 días no aparecen todavía.

Si el widget no está en la barra, agrega **Calendar Agenda** al layout y reinicia el shell:

```bash
omarchy restart shell
```

## Desinstalación

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/configure-calendar.sh --remove
omarchy plugin remove io.github.brm-src.calendar-agenda --yes
```

Esto no borra eventos remotos ni modifica tu cuenta de calendario.

## Desarrollo y validación

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile calendar_events.py
qmllint -I /usr/share/omarchy/shell CalendarAgenda.qml
omarchy plugin validate .
bash -n configure-calendar.sh
git diff --check
```

## Licencia

MIT. Consulta [LICENSE](LICENSE).
