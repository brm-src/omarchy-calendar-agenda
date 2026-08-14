import Quickshell
import Quickshell.Io
import QtQuick
import qs.Commons

Item {
  id: root

  property var events: []
  property string errorMessage: ""
  readonly property string eventScript: Qt.resolvedUrl("calendar_events.py").toString().replace("file://", "")

  function refresh() {
    if (!calendarProc.running) calendarProc.running = true
  }

  function openEvent(url) {
    if (!url) return
    Util.execDetached("xdg-open " + Util.shellQuote(url))
  }

  function applyPayload(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      events = payload.events || []
      errorMessage = payload.error || ""
    } catch (e) {
      events = []
      errorMessage = "No se pudo leer el calendario"
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

  Variants {
    model: Quickshell.screens

    PanelWindow {
      required property var modelData
      screen: modelData
      visible: true
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "io.github.brm-src.calendar-agenda"
      WlrLayershell.layer: WlrLayer.Bottom
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      mask: Region { x: card.x; y: card.y; width: card.width; height: card.height }

      Rectangle {
        id: card
        width: 350
        height: content.implicitHeight + 24
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 66
        anchors.rightMargin: 26
        radius: 14
        color: Util.alpha(Color.background, 0.96)
        border.width: 1
        border.color: Util.alpha(Color.accent, 0.82)
        visible: root.events.length > 0 || root.errorMessage !== ""

        Column {
          id: content
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.margins: 12
          spacing: 6

          Text {
            width: parent.width
            text: "AGENDA"
            color: Color.accent
            font.family: Style.font.family
            font.pixelSize: 12
            font.bold: true
            font.letterSpacing: 1.4
          }

          Rectangle { width: parent.width; height: 1; color: Util.alpha(Color.accent, 0.40) }

          Row {
            width: parent.width
            spacing: 10
            Text { width: 60; text: "FECHA"; color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
            Text { width: 42; text: "HORA"; color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
            Text { text: "EVENTO"; color: Util.alpha(Color.foreground, 0.52); font.family: Style.font.family; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.7 }
          }

          Repeater {
            model: root.events
            delegate: Rectangle {
              id: eventRow
              width: content.width
              height: 31
              radius: 8
              color: eventMouse.containsMouse ? Util.alpha(Color.accent, 0.20) : Util.alpha(Color.foreground, 0.06)

              Row {
                anchors.fill: parent
                anchors.leftMargin: 9
                anchors.rightMargin: 9
                spacing: 10
                Text {
                  width: 60
                  anchors.verticalCenter: parent.verticalCenter
                  text: modelData.day
                  color: Color.accent
                  font.family: Style.font.family
                  font.pixelSize: 11
                  font.bold: true
                  elide: Text.ElideRight
                }
                Text {
                  width: 42
                  anchors.verticalCenter: parent.verticalCenter
                  text: modelData.time
                  color: Color.foreground
                  font.family: Style.font.family
                  font.pixelSize: 12
                  font.bold: true
                }
                Text {
                  width: parent.width - 60 - 42 - 10 - 10
                  anchors.verticalCenter: parent.verticalCenter
                  text: modelData.title
                  color: Color.foreground
                  font.family: Style.font.family
                  font.pixelSize: 12
                  elide: Text.ElideRight
                  maximumLineCount: 1
                }
              }

              MouseArea {
                id: eventMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openEvent(String(modelData.url || ""))
              }
            }
          }

          Text {
            visible: root.events.length === 0
            text: root.errorMessage !== "" ? root.errorMessage : "Sin eventos en los próximos 30 días"
            color: Util.alpha(Color.foreground, 0.64)
            font.family: Style.font.family
            font.pixelSize: 12
            wrapMode: Text.Wrap
            width: parent.width
          }
        }
      }
    }
  }
}
