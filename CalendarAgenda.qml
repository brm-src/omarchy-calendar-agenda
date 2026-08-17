import Quickshell
import Quickshell.Io
import Quickshell.Wayland

import QtQuick
import qs.Commons
import qs.Ui

import "i18n.js" as I18n

Item {
  id: root

  property var events: []
  property string errorMessage: ""
  property bool collapsed: false
  property bool expanded: false
  property bool settingsOpen: false
  property string settingsError: ""
  property string selectedDate: ""
  property date shownMonth: new Date()
  readonly property var activeWindow: ToplevelManager.activeToplevel
  readonly property bool desktopVisible: !activeWindow
  property var calendarNames: []
  property string language: "en"
  property string timezone: ""
  readonly property string eventScript: Qt.resolvedUrl("calendar_events.py").toString().replace("file://", "")
  readonly property var monthNames: I18n.MONTHS[root.language] || I18n.MONTHS.en
  readonly property var weekdayNames: I18n.WEEKDAY_LETTERS[root.language] || I18n.WEEKDAY_LETTERS.en
  readonly property var calendarCells: buildMonthCells(shownMonth)
  readonly property var displayedEvents: selectedDate === ""
    ? events
    : events.filter(function(event) { return String(event.date || "") === selectedDate })
  readonly property int visibleEventCount: expanded ? displayedEvents.length : Math.min(displayedEvents.length, 4)

  function pad2(value) { return value < 10 ? "0" + value : String(value) }

  function dateKey(value) {
    return value.getFullYear() + "-" + pad2(value.getMonth() + 1) + "-" + pad2(value.getDate())
  }

  function buildMonthCells(month) {
    var first = new Date(month.getFullYear(), month.getMonth(), 1)
    var mondayOffset = (first.getDay() + 6) % 7
    var cells = []
    for (var i = 0; i < 42; i++) {
      var value = new Date(month.getFullYear(), month.getMonth(), 1 + i - mondayOffset)
      cells.push({
        date: dateKey(value),
        day: value.getDate(),
        inMonth: value.getMonth() === month.getMonth()
      })
    }
    return cells
  }

  function eventOnDate(date) {
    for (var i = 0; i < events.length; i++) {
      if (String(events[i].date || "") === date) return true
    }
    return false
  }

  function todayDate(date) {
    var now = new Date()
    return date === dateKey(now)
  }

  function selectedDayLabel() {
    for (var i = 0; i < events.length; i++) {
      if (String(events[i].date || "") === selectedDate) return String(events[i].day || selectedDate)
    }
    return selectedDate
  }

  function monthLabel() {
    return monthNames[shownMonth.getMonth()] + " " + shownMonth.getFullYear()
  }

  function moveMonth(delta) {
    shownMonth = new Date(shownMonth.getFullYear(), shownMonth.getMonth() + delta, 1)
  }

  function refresh() {
    if (!calendarProc.running) calendarProc.running = true
  }

  function openEvent(url) {
    if (!url) return
    Quickshell.execDetached(["xdg-open", url])
  }

  function openDay(date) {
    var value = String(date || "")
    if (!value) return
    var parts = value.split("-")
    if (parts.length !== 3) return
    var next = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]) + 1)
    var start = parts.join("") + "T000000"
    var end = next.getFullYear() + pad2(next.getMonth() + 1) + pad2(next.getDate()) + "T000000"
    Quickshell.execDetached(["xdg-open", "https://calendar.google.com/calendar/u/0/r/eventedit?dates=" + start + "/" + end])
  }

  function selectDay(date) {
    if (eventOnDate(date)) {
      selectedDate = selectedDate === date ? "" : date
      expanded = true
      collapsed = false
    } else {
      openDay(date)
    }
  }

  function applyPayload(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      events = payload.events || []
      errorMessage = payload.error || ""
      calendarNames = payload.calendars || []
      language = payload.language || root.language
      timezone = payload.timezone !== undefined ? payload.timezone : root.timezone
      if (selectedDate !== "" && !eventOnDate(selectedDate)) selectedDate = ""
    } catch (e) {
      events = []
      calendarNames = []
      errorMessage = I18n.t(root.language, "couldNotRead")
    }
  }

  function toggleExpanded() {
    expanded = !expanded
    if (expanded) collapsed = false
  }

  function toggleSettings() {
    settingsOpen = !settingsOpen
    if (settingsOpen) collapsed = false
  }

  function applySettings(lang, tz) {
    settingsProc.command = ["python3", root.eventScript, "--set", "language=" + lang, "timezone=" + tz]
    settingsProc.running = true
  }

  function applySettingsResult(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      if (payload.ok) {
        settingsError = ""
        refresh()
      } else {
        settingsError = String(payload.error || "")
      }
    } catch (e) {
      settingsError = ""
    }
  }

  Component.onCompleted: refresh()

  Timer {
    interval: 300000
    repeat: true
    running: true
    onTriggered: root.refresh()
  }

  Process {
    id: calendarProc
    command: ["python3", root.eventScript]
    stdout: StdioCollector {
      onStreamFinished: root.applyPayload(text)
    }
  }

  Process {
    id: settingsProc
    stdout: StdioCollector {
      onStreamFinished: root.applySettingsResult(text)
    }
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      required property var modelData
      screen: modelData
      visible: root.desktopVisible
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "io.github.brm-src.calendar-agenda"
      WlrLayershell.layer: WlrLayer.Bottom
      WlrLayershell.keyboardFocus: root.settingsOpen ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
      mask: Region {
        x: card.x
        y: card.y
        width: card.visible ? card.width : 0
        height: card.visible ? card.height : 0
      }

      BorderSurface {
        id: card
        width: root.expanded ? 420 : 360
        height: content.implicitHeight + Style.space(24)
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Style.bar.sizeHorizontal + Style.space(12)
        anchors.rightMargin: Style.gapsOut
        radius: Style.cornerRadius
        color: Color.background
        borderSpec: Border.surfaceSpec("menu", "border", Color.accent, 1)
        visible: root.desktopVisible && (root.events.length > 0 || root.errorMessage !== "")
        clip: true

        Column {
          id: content
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.margins: Style.spacing.md
          spacing: Style.spacing.sm

          Row {
            id: header
            width: parent.width
            height: Style.space(26)

            Text {
              width: parent.width - headerActions.width - Style.spacing.sm
              anchors.verticalCenter: parent.verticalCenter
              text: I18n.t(root.language, "agenda")
              color: Color.accent
              font.family: Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
              font.letterSpacing: 1.2
            }

            Row {
              id: headerActions
              spacing: Style.spacing.xs

              PanelActionButton {
                size: Style.space(24)
                iconText: root.settingsOpen ? "×" : "⚙"
                foreground: Color.foreground
                hoverColor: Color.accent

                onClicked: {
                  root.toggleSettings()
                  if (root.settingsOpen) timezoneField.text = root.timezone
                }
              }

              PanelActionButton {
                size: Style.space(24)
                iconText: root.collapsed ? "▸" : (root.expanded ? "−" : "+")
                foreground: Color.foreground
                hoverColor: Color.accent

                onClicked: {
                  if (root.collapsed) root.collapsed = false
                  else root.toggleExpanded()
                }
              }

              PanelActionButton {
                size: Style.space(24)
                iconText: "↻"
                foreground: Color.foreground
                hoverColor: Color.accent

                onClicked: root.refresh()
              }
            }
          }

          Rectangle { width: parent.width; height: 1; color: Util.alpha(Color.accent, 0.40) }

          Rectangle {
            visible: root.collapsed
            width: parent.width
            height: 34
            radius: Style.cornerRadius
            color: Util.alpha(Color.foreground, 0.06)

            Row {
              anchors.fill: parent
              anchors.leftMargin: Style.spacing.sm
              anchors.rightMargin: Style.spacing.sm
              spacing: Style.spacing.sm

              Text {
                width: 62
                anchors.verticalCenter: parent.verticalCenter
                text: root.displayedEvents.length > 0 ? root.displayedEvents[0].day : ""
                color: Color.accent
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: 84
                anchors.verticalCenter: parent.verticalCenter
                text: root.displayedEvents.length > 0 ? root.displayedEvents[0].time : ""
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
              }

              Text {
                width: parent.width - 62 - 84 - parent.spacing * 2
                anchors.verticalCenter: parent.verticalCenter
                text: root.displayedEvents.length > 0
                  ? (root.displayedEvents[0].allDay ? "• " + root.displayedEvents[0].title : root.displayedEvents[0].title)
                  : root.errorMessage
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }
            }
          }

          Column {
            visible: !root.collapsed
            width: parent.width
            spacing: Style.spacing.sm

            Row {
              width: parent.width
              height: Style.space(20)
              visible: !root.settingsOpen

              Text {
                width: parent.width
                text: root.expanded && root.selectedDate !== ""
                  ? I18n.t(root.language, "meetingsFor", {day: root.selectedDayLabel()})
                  : (root.expanded ? I18n.t(root.language, "calendarAndAgenda") : I18n.t(root.language, "upcomingEvents"))
                color: Color.foreground
                opacity: 0.68
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 0.7
              }


            }

            Column {
              visible: root.expanded && !root.settingsOpen
              width: parent.width
              spacing: Style.spacing.xs

              Row {
                width: parent.width
                height: Style.space(24)

                PanelActionButton {
                  id: monthPrevious
                  size: Style.space(22)
                  iconText: "‹"
                  foreground: Color.foreground
                  hoverColor: Color.accent

                  onClicked: root.moveMonth(-1)
                }

                Text {
                  width: parent.width - monthNext.width - monthPrevious.width
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.monthLabel()
                  color: Color.foreground
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  font.bold: true
                  horizontalAlignment: Text.AlignHCenter
                }

                PanelActionButton {
                  id: monthNext
                  size: Style.space(22)
                  iconText: "›"
                  foreground: Color.foreground
                  hoverColor: Color.accent

                  onClicked: root.moveMonth(1)
                }
              }

              Grid {
                id: weekdayGrid
                width: parent.width
                columns: 7
                columnSpacing: Style.spacing.xs

                Repeater {
                  model: root.weekdayNames
                  Text {
                    required property string modelData
                    width: (weekdayGrid.width - Style.spacing.xs * 6) / 7
                    height: Style.space(16)
                    text: modelData
                    color: Color.foreground
                    opacity: 0.48
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                  }
                }
              }

              Grid {
                id: calendarGrid
                width: parent.width
                columns: 7
                columnSpacing: Style.spacing.xs
                rowSpacing: Style.spacing.xs

                Repeater {
                  model: root.calendarCells
                  Rectangle {
                    required property var modelData
                    width: (calendarGrid.width - Style.spacing.xs * 6) / 7
                    height: Style.space(24)
                    radius: Style.cornerRadius
                    color: dayMouse.containsMouse || root.selectedDate === modelData.date
                      ? Util.alpha(Color.accent, 0.36)
                      : (root.todayDate(modelData.date)
                      ? Color.accent
                      : (root.eventOnDate(modelData.date) ? Util.alpha(Color.accent, 0.20) : "transparent"))
                    border.width: root.eventOnDate(modelData.date) && !root.todayDate(modelData.date) ? 1 : 0
                    border.color: Util.alpha(Color.accent, 0.65)

                    Text {
                      anchors.centerIn: parent
                      text: modelData.day
                      color: root.todayDate(modelData.date) || root.selectedDate === modelData.date
                        ? Color.background
                        : (modelData.inMonth ? Color.foreground : Util.alpha(Color.foreground, 0.28))
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                      font.bold: root.todayDate(modelData.date) || root.eventOnDate(modelData.date)
                    }

                    MouseArea {
                      id: dayMouse
                      anchors.fill: parent
                      hoverEnabled: true
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.selectDay(modelData.date)
                    }
                  }
                }
              }
            }

            Row {
              width: parent.width
              visible: root.displayedEvents.length > 0 && !root.settingsOpen
              spacing: Style.spacing.sm
              Text { width: 62; text: I18n.t(root.language, "date"); color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
              Text { width: 84; text: I18n.t(root.language, "time"); color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
              Text { text: I18n.t(root.language, "event"); color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
            }

            Repeater {
              model: root.settingsOpen ? 0 : root.visibleEventCount
              delegate: Rectangle {
                required property int index
                id: eventRow
                width: parent.width
                height: 31
                radius: Style.cornerRadius
                color: eventMouse.containsMouse ? Util.alpha(Color.accent, 0.20) : Util.alpha(Color.foreground, 0.06)

                Row {
                  anchors.fill: parent
                  anchors.leftMargin: Style.spacing.sm
                  anchors.rightMargin: Style.spacing.sm
                  spacing: Style.spacing.sm

                  Text {
                    width: 62
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.displayedEvents[index].day
                    color: Color.accent
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    elide: Text.ElideRight
                  }

                  Text {
                    width: 84
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.displayedEvents[index].time
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }

                  Text {
                    width: parent.width - 62 - 84 - parent.spacing * 2
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.displayedEvents[index].allDay ? "• " + root.displayedEvents[index].title : root.displayedEvents[index].title
                    textFormat: Text.PlainText
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    elide: Text.ElideRight
                    maximumLineCount: 1
                  }
                }

                MouseArea {
                  id: eventMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.openEvent(String(root.displayedEvents[index].url || ""))
                }
              }
            }

            Text {
              visible: root.displayedEvents.length === 0 && !root.settingsOpen
              text: root.errorMessage !== "" ? root.errorMessage : I18n.t(root.language, "noEvents")
              textFormat: Text.PlainText
              color: Util.alpha(Color.foreground, 0.64)
              font.family: Style.font.family
              font.pixelSize: Style.font.body
              wrapMode: Text.Wrap
              width: parent.width
            }

            Column {
              visible: root.settingsOpen
              width: parent.width
              spacing: Style.spacing.sm

              PanelSectionHeader { text: I18n.t(root.language, "language") }

              ButtonGroup {
                options: [
                  {value: "en", label: "EN"},
                  {value: "es", label: "ES"},
                  {value: "pt", label: "PT"}
                ]
                value: root.language
                onChanged: function(v) {
                  root.language = v
                  root.applySettings(v, root.timezone)
                }
              }

              PanelSectionHeader { text: I18n.t(root.language, "timezone") }

              TextField {
                id: timezoneField
                width: parent.width
                placeholderText: I18n.t(root.language, "timezonePlaceholder")
                onEditingFinished: {
                  root.timezone = text.trim()
                  root.applySettings(root.language, root.timezone)
                }
              }

              Text {
                visible: root.settingsError !== ""
                text: root.settingsError
                textFormat: Text.PlainText
                color: Color.urgent
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                wrapMode: Text.Wrap
                width: parent.width
              }
            }
          }
        }
      }
    }
  }
}
