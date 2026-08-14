# Agenda de escritorio para Omarchy

[English](README.en.md)

Un widget discreto para Omarchy Quattro que muestra las próximas reuniones en una tarjeta sobre el escritorio, debajo de la barra.

![Vista previa de Desktop Agenda](preview.png)

Funciona con cualquier servicio que entregue un calendario iCalendar (`.ics`): Google Calendar, Nextcloud, Fastmail, calendarios propios y otros. No depende de una API específica.

## Instalación rápida

Requiere Omarchy Quattro, Quickshell, Python 3.9 o superior y una URL privada `.ics`.

```bash
omarchy plugin add https://github.com/brm-src/omarchy-calendar-agenda.git --enable --yes
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/setup.sh
```

El segundo comando te pide la URL privada, comprueba que realmente sea un calendario iCalendar, la guarda localmente con permisos `600` y reinicia el shell de Omarchy. No instala paquetes, no usa `sudo` y no ejecuta código descargado desde otra URL.

Si prefieres revisar el código antes de activarlo, omite `--enable` en el primer comando y ejecuta después:

```bash
omarchy plugin enable io.github.brm-src.calendar-agenda
```

## Uso

La tarjeta aparece arriba a la derecha y se actualiza cada cinco minutos. Muestra hasta ocho eventos dentro de los próximos 30 días.

- Las reuniones de hoy aparecen como `HOY`.
- Las del día siguiente aparecen como `MAÑANA`.
- Los eventos se ordenan por hora.
- Al hacer clic se abre el enlace del evento con el navegador predeterminado.
- Los enlaces de Google Meet y Zoom dentro de la descripción tienen prioridad.

## Privacidad: por qué no hay API keys

El plugin no usa API de proveedor, OAuth, client secrets ni una credencial compartida. Cada persona configura su propia URL privada iCalendar en:

```text
~/.config/omarchy/calendar-widget/config.json
```

La URL privada funciona como una contraseña: quien la tenga puede leer el calendario. No la publiques ni la pegues en issues, capturas o logs.

El repositorio no contiene credenciales y el plugin no envía los eventos a ningún servidor intermedio. La descarga ocurre directamente desde el equipo local.

## Solución de problemas

Si la tarjeta dice que falta configurar el calendario:

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/setup.sh
```

Para comprobar el archivo local y sus permisos:

```bash
stat -c '%a %n' ~/.config/omarchy/calendar-widget/config.json
```

La salida esperada es `600`.

## Desinstalación

Este comando elimina el plugin y su configuración local, pero no toca tu cuenta ni borra eventos remotos:

```bash
bash ~/.config/omarchy/plugins/io.github.brm-src.calendar-agenda/setup.sh --remove
```

## Desarrollo y validación

```bash
python3 -m unittest discover -s tests -v
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" CalendarAgenda.qml
```

## Licencia

MIT. Consulta [LICENSE](LICENSE).
