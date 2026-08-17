.pragma library

var STRINGS = {
  en: {
    agenda: "AGENDA",
    calendarAndAgenda: "CALENDAR AND AGENDA",
    upcomingEvents: "UPCOMING EVENTS",
    meetingsFor: "MEETINGS: {day}",
    date: "DATE",
    time: "TIME",
    event: "EVENT",
    noEvents: "No events in the next 30 days",
    couldNotRead: "Could not read calendar",
    settings: "SETTINGS",
    language: "LANGUAGE",
    timezone: "TIMEZONE",
    timezonePlaceholder: "System default (e.g. America/Sao_Paulo)"
  },
  es: {
    agenda: "AGENDA",
    calendarAndAgenda: "CALENDARIO Y AGENDA",
    upcomingEvents: "PRÓXIMOS EVENTOS",
    meetingsFor: "REUNIONES: {day}",
    date: "FECHA",
    time: "HORA",
    event: "EVENTO",
    noEvents: "Sin eventos en los próximos 30 días",
    couldNotRead: "No se pudo leer el calendario",
    settings: "AJUSTES",
    language: "IDIOMA",
    timezone: "ZONA HORARIA",
    timezonePlaceholder: "Predeterminada del sistema (ej. America/Sao_Paulo)"
  },
  pt: {
    agenda: "AGENDA",
    calendarAndAgenda: "CALENDÁRIO E AGENDA",
    upcomingEvents: "PRÓXIMOS EVENTOS",
    meetingsFor: "REUNIÕES: {day}",
    date: "DATA",
    time: "HORA",
    event: "EVENTO",
    noEvents: "Nenhum evento nos próximos 30 dias",
    couldNotRead: "Não foi possível ler o calendário",
    settings: "CONFIGURAÇÕES",
    language: "IDIOMA",
    timezone: "FUSO HORÁRIO",
    timezonePlaceholder: "Padrão do sistema (ex. America/Sao_Paulo)"
  }
}

var MONTHS = {
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  es: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
  pt: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
}

// Monday-indexed, matching buildMonthCells' mondayOffset.
var WEEKDAY_LETTERS = {
  en: ["M", "T", "W", "T", "F", "S", "S"],
  es: ["L", "M", "X", "J", "V", "S", "D"],
  pt: ["S", "T", "Q", "Q", "S", "S", "D"]
}

function t(lang, key, params) {
  var table = STRINGS[lang] || STRINGS.en
  var value = table[key] !== undefined ? table[key] : STRINGS.en[key]
  if (params) {
    for (var name in params) value = value.replace("{" + name + "}", params[name])
  }
  return value
}
