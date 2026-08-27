import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.brm-src.calendar-agenda"

  property string uiLanguage: Qt.locale().name.toLowerCase().startsWith("es") ? "es" : "en"
  readonly property bool isSpanish: uiLanguage === "es"
  function words(es, en) { return root.isSpanish ? es : en }

  property var events: []
  property string errorMessage: ""
  property string updatedAt: ""
  property string lastCalendarSummary: ""
  property string viewMode: "week"
  property date anchorDate: new Date()
  property bool panelOpen: false
  property bool loading: false

  readonly property string eventScript: Qt.resolvedUrl("calendar_events.py").toString().replace("file://", "")
  readonly property bool opened: root.panelOpen
  readonly property var displayRows: buildRows()
  readonly property int visibleEventCount: countEvents(displayRows)

  function pad2(value) { return value < 10 ? "0" + value : String(value) }

  function dateKey(value) {
    return value.getFullYear() + "-" + pad2(value.getMonth() + 1) + "-" + pad2(value.getDate())
  }

  function dateForKey(value) {
    var parts = String(value || "").split("-")
    if (parts.length !== 3) return new Date(NaN)
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
    return dateKey(date) === String(value) ? date : new Date(NaN)
  }

  function startOfWeek(value) {
    var result = new Date(value.getFullYear(), value.getMonth(), value.getDate())
    result.setDate(result.getDate() - ((result.getDay() + 6) % 7))
    return result
  }

  function rangeFor(mode, value) {
    var start
    var end
    if (mode === "month") {
      start = new Date(value.getFullYear(), value.getMonth(), 1)
      end = new Date(value.getFullYear(), value.getMonth() + 1, 1)
    } else if (mode === "week") {
      start = startOfWeek(value)
      end = new Date(start)
      end.setDate(end.getDate() + 7)
    } else {
      start = new Date(value.getFullYear(), value.getMonth(), value.getDate())
      end = new Date(start)
      end.setDate(end.getDate() + 1)
    }
    return { start: start, end: end }
  }

  function movedAnchor(amount) {
    var next = new Date(anchorDate)
    if (viewMode === "month") return new Date(next.getFullYear(), next.getMonth() + amount, 1)
    next.setDate(next.getDate() + (viewMode === "week" ? amount * 7 : amount))
    return next
  }

  function canMove(amount) {
    var range = rangeFor(viewMode, movedAnchor(amount))
    var start = new Date()
    start.setHours(0, 0, 0, 0)
    var end = new Date(start)
    end.setDate(end.getDate() + 30)
    return range.end > start && range.start <= end
  }

  function formatDate(value, markToday) {
    var date = dateForKey(value)
    if (isNaN(date.getTime())) return String(value || "")
    if (markToday === true && dateKey(date) === dateKey(new Date())) return words("HOY", "TODAY")
    var days = isSpanish
      ? ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"]
      : ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    var months = isSpanish
      ? ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
      : ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return days[date.getDay()] + " " + months[date.getMonth()] + " " + date.getDate()
  }

  function formatClock(value) {
    var match = String(value || "").match(/T(\d{2}):(\d{2})/)
    return match ? match[1] + ":" + match[2] : ""
  }

  function viewTitle() {
    var range = rangeFor(viewMode, anchorDate)
    if (viewMode === "day") return formatDate(dateKey(range.start), true)
    if (viewMode === "month") {
      var monthNames = isSpanish
        ? ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        : ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
      return monthNames[anchorDate.getMonth()] + " " + anchorDate.getFullYear()
    }
    var last = new Date(range.end)
    last.setDate(last.getDate() - 1)
    return formatDate(dateKey(range.start), false) + " – " + formatDate(dateKey(last), false)
  }

  function eventSort(a, b) {
    if (a.allDay !== b.allDay) return a.allDay ? -1 : 1
    var at = String(a.time || "")
    var bt = String(b.time || "")
    if (at !== bt) return at.localeCompare(bt)
    return String(a.title || "").localeCompare(String(b.title || ""))
  }

  function buildRows() {
    var range = rangeFor(viewMode, anchorDate)
    var grouped = {}
    var keys = []
    for (var i = 0; i < events.length; i++) {
      var event = events[i]
      var key = String(event.date || "")
      var eventDate = dateForKey(key)
      if (isNaN(eventDate.getTime()) || eventDate < range.start || eventDate >= range.end) continue
      if (!grouped[key]) {
        grouped[key] = []
        keys.push(key)
      }
      grouped[key].push(event)
    }
    keys.sort()
    var rows = []
    for (var j = 0; j < keys.length; j++) {
      var dayEvents = grouped[keys[j]]
      dayEvents.sort(eventSort)
      rows.push({ kind: "header", key: keys[j], label: formatDate(keys[j], viewMode === "day") })
      for (var k = 0; k < dayEvents.length; k++)
        rows.push({ kind: "event", event: dayEvents[k] })
    }
    return rows
  }

  function countEvents(rows) {
    var count = 0
    for (var i = 0; i < rows.length; i++) if (rows[i].kind === "event") count++
    return count
  }

  function emptyMessage() {
    if (errorMessage !== "") return errorMessage
    if (viewMode === "day") return words("No hay eventos para este día.", "No events on this day.")
    if (viewMode === "month") return words("No hay eventos en este mes.", "No events this month.")
    return words("No hay eventos en esta semana.", "No events this week.")
  }

  function refresh() {
    if (calendarProc.running) return
    loading = true
    errorMessage = ""
    calendarProc.command = ["python3", eventScript, "--lang", uiLanguage]
    calendarProc.running = true
  }

  function applyPayload(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      var nextEvents = Array.isArray(payload.events) ? payload.events.slice(0, 64) : []
      events = nextEvents
      errorMessage = String(payload.error || "")
      updatedAt = String(payload.updated || "")
      var calendars = Array.isArray(payload.calendars) ? payload.calendars.slice(0, 16) : []
      lastCalendarSummary = calendars.join(", ")
    } catch (error) {
      events = []
      errorMessage = words("No se pudo leer el calendario.", "Could not read calendar data.")
      updatedAt = ""
      lastCalendarSummary = ""
    }
  }

  function openEvent(url) {
    var value = String(url || "")
    if (value !== "") Quickshell.execDetached(["xdg-open", value])
  }

  function setMode(mode) {
    viewMode = mode
    if (mode === "day") anchorDate = new Date()
  }

  function move(amount) {
    if (root.canMove(amount)) anchorDate = movedAnchor(amount)
  }

  function goToToday() {
    anchorDate = new Date()
    viewMode = "week"
  }

  function togglePanel() {
    panelOpen = !panelOpen
    if (panelOpen) {
      refresh()
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
  }

  function open() { if (!panelOpen) togglePanel() }

  function close() { closePanel() }

  function toggle() { togglePanel() }

  function closeForPopoutSwitch() { closePanel() }

  function closePanel() { panelOpen = false }

  Component.onCompleted: root.events = []

  Timer {
    interval: 300000
    repeat: true
    running: root.panelOpen
    onTriggered: root.refresh()
  }

  Process {
    id: calendarProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyPayload(text)
    }
    onExited: function(exitCode) {
      root.loading = false
      if (exitCode !== 0 && root.errorMessage === "")
        root.errorMessage = root.words("No se pudo actualizar el calendario.", "Could not refresh calendar data.")
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.panelOpen
    centerOnBar: false
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(440))
    contentHeight: panel.fittedContentHeight(Style.space(540))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.closePanel()
      onTextKey: function(text) {
        if (text === "d" || text === "D") root.setMode("day")
        else if (text === "w" || text === "W") root.setMode("week")
        else if (text === "m" || text === "M") root.setMode("month")
        else if (text === "t" || text === "T") root.goToToday()
        else if (text === "[" || text === "{") root.move(-1)
        else if (text === "]" || text === "}") root.move(1)
        else if (text === "r" || text === "R") root.refresh()
      }
    }

    Flickable {
      id: scroll
      anchors.fill: parent
      anchors.margins: Style.space(16)
      contentWidth: width
      contentHeight: contentColumn.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      interactive: contentHeight > height

      Column {
        id: contentColumn
        width: scroll.width
        spacing: Style.spacing.md

        Row {
          width: parent.width
          spacing: Style.spacing.sm

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "󰃭"
            color: Color.accent
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.subtitle
          }

          Column {
            width: parent.width - headerActions.width - Style.spacing.sm - Style.space(28)
            spacing: 1
            Text {
              textFormat: Text.PlainText
              text: root.words("AGENDA", "AGENDA")
              color: Color.menu.text
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.title
              font.bold: true
              font.letterSpacing: 1.3
            }
            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.loading
                ? root.words("Actualizando…", "Refreshing…")
                : (root.visibleEventCount > 0
                  ? root.visibleEventCount + " " + root.words("eventos en la vista", "events in view")
                  : root.words("Calendario privado", "Private calendar"))
              color: Util.alpha(Color.menu.text, 0.55)
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          Row {
            id: headerActions
            spacing: Style.spacing.xs
            anchors.verticalCenter: parent.verticalCenter

            PanelActionButton {
              size: Style.space(24)
              iconText: "↻"
              foreground: Color.menu.text
              fontFamily: Style.font.menuFamily
              tooltipText: root.words("Actualizar (R)", "Refresh (R)")
              enabled: !root.loading
              onClicked: root.refresh()
            }
            PanelActionButton {
              size: Style.space(24)
              iconText: "×"
              foreground: Color.menu.text
              fontFamily: Style.font.menuFamily
              tooltipText: root.words("Cerrar", "Close")
              onClicked: root.closePanel()
            }
          }
        }

        PanelSeparator { foreground: Color.menu.text }

        ButtonGroup {
          width: parent.width
          focusable: false
          foreground: Color.menu.text
          background: Color.menu.background
          accent: Color.accent
          fontFamily: Style.font.menuFamily
          value: root.viewMode
          options: [
            { value: "day", label: root.words("DÍA", "DAY") },
            { value: "week", label: root.words("SEMANA", "WEEK") },
            { value: "month", label: root.words("MES", "MONTH") }
          ]
          onChanged: root.setMode(value)
        }

        Row {
          width: parent.width
          height: Style.space(30)

          PanelActionButton {
            size: Style.space(28)
            iconText: "‹"
            enabled: root.canMove(-1)
            foreground: Color.menu.text
            fontFamily: Style.font.menuFamily
            tooltipText: root.words("Anterior ([)", "Previous ([)")
            onClicked: root.move(-1)
          }

          Text {
            width: parent.width - Style.space(56)
            height: parent.height
            textFormat: Text.PlainText
            text: root.viewTitle()
            color: Color.menu.text
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.body
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
          }

          PanelActionButton {
            size: Style.space(28)
            iconText: "›"
            enabled: root.canMove(1)
            foreground: Color.menu.text
            fontFamily: Style.font.menuFamily
            tooltipText: root.words("Siguiente (])", "Next (])")
            onClicked: root.move(1)
          }
        }

        Row {
          width: parent.width
          spacing: Style.spacing.sm

          Button {
            text: root.words("Hoy", "Today")
            active: true
            enabled: root.viewMode !== "week" || dateKey(root.anchorDate) !== dateKey(new Date())
            onClicked: root.goToToday()
          }

          Text {
            width: parent.width - Style.space(72) - parent.spacing
            textFormat: Text.PlainText
            text: root.updatedAt !== ""
              ? root.words("Actualizado", "Updated") + " " + root.formatClock(root.updatedAt)
                + (root.lastCalendarSummary !== "" ? "  ·  " + root.lastCalendarSummary : "")
              : ""
            color: Util.alpha(Color.menu.text, 0.45)
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
          }
        }

        Text {
          visible: root.errorMessage !== "" && root.visibleEventCount > 0
          width: parent.width
          textFormat: Text.PlainText
          text: "⚠ " + root.errorMessage
          color: Color.accent
          font.family: Style.font.menuFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.Wrap
        }

        ListView {
          id: eventList
          width: parent.width
          height: Math.max(Style.space(74), Math.min(Style.space(360), contentHeight))
          model: root.displayRows
          spacing: Style.space(6)
          clip: true
          boundsBehavior: Flickable.StopAtBounds
          interactive: contentHeight > height

          delegate: Item {
            required property var modelData
            width: eventList.width
            height: modelData.kind === "header"
              ? Style.space(22)
              : (modelData.event.location || modelData.event.allDay ? Style.space(74) : Style.space(58))

            Text {
              visible: modelData.kind === "header"
              anchors.left: parent.left
              anchors.right: parent.right
              height: parent.height
              textFormat: Text.PlainText
              text: modelData.label
              color: Color.accent
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 1.2
              verticalAlignment: Text.AlignVCenter
            }

            CursorSurface {
              id: eventSurface
              visible: modelData.kind === "event"
              anchors.fill: parent
              foreground: Color.menu.text
              accent: Color.accent
              radius: Style.cornerRadius

              Row {
                anchors.fill: parent
                anchors.leftMargin: Style.space(9)
                anchors.rightMargin: Style.space(9)
                spacing: Style.spacing.sm

                Text {
                  width: Style.space(82)
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  text: modelData.event.allDay ? root.words("TODO EL DÍA", "ALL DAY") : String(modelData.event.time || "")
                  color: modelData.event.allDay ? Color.accent : Util.alpha(Color.menu.text, 0.6)
                  font.family: Style.font.menuFamily
                  font.pixelSize: Style.font.caption
                  font.bold: modelData.event.allDay
                  wrapMode: Text.Wrap
                  maximumLineCount: 2
                }

                Column {
                  width: parent.width - Style.space(82) - parent.spacing
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: 1

                  Text {
                    width: parent.width
                    textFormat: Text.PlainText
                    text: String(modelData.event.title || root.words("Sin título", "Untitled"))
                    color: Color.menu.text
                    font.family: Style.font.menuFamily
                    font.pixelSize: Style.font.body
                    elide: Text.ElideRight
                  }

                  Text {
                    width: parent.width
                    textFormat: Text.PlainText
                    text: String(modelData.event.calendar || "")
                      + (modelData.event.location ? "  ·  " + String(modelData.event.location) : "")
                    color: Util.alpha(Color.menu.text, 0.5)
                    font.family: Style.font.menuFamily
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                  }
                }
              }

              MouseArea {
                anchors.fill: parent
                enabled: modelData.kind === "event" && String(modelData.event.url || "") !== ""
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: root.openEvent(modelData.event.url)
              }
            }
          }
        }

        Text {
          visible: root.visibleEventCount === 0
          width: parent.width
          textFormat: Text.PlainText
          text: root.emptyMessage()
          color: root.errorMessage !== "" ? Color.accent : Util.alpha(Color.menu.text, 0.55)
          font.family: Style.font.menuFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
          horizontalAlignment: Text.AlignHCenter
          topPadding: Style.space(10)
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.words("Pulsa R para actualizar · clic en un evento para abrir su enlace", "Press R to refresh · click an event to open its link")
          color: Util.alpha(Color.menu.text, 0.32)
          font.family: Style.font.menuFamily
          font.pixelSize: Style.font.caption
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.Wrap
        }
      }
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  visible: true

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰃭"
    slotSize: Style.bar.statusSlot
    opticalSize: 17
    tooltipText: root.words("Agenda de calendario", "Calendar agenda")
    active: root.opened
    useActiveColor: true
    activeColor: Color.accent

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.MiddleButton) root.refresh()
      else if (mouseButton === Qt.LeftButton) root.togglePanel()
    }
  }
}
