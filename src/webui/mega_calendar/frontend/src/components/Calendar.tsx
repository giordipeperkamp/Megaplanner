import "../styles/Calendar.css"

import adaptivePlugin from "@fullcalendar/adaptive" // premium
import dayGridPlugin from "@fullcalendar/daygrid"
import interactionPlugin, { DateClickArg } from "@fullcalendar/interaction"
import listPlugin from "@fullcalendar/list"
import multiMonthPlugin from "@fullcalendar/multimonth"
import FullCalendar from "@fullcalendar/react"
import resourceDayGridPlugin from "@fullcalendar/resource-daygrid" // premium
import resourceTimeGridPlugin from "@fullcalendar/resource-timegrid" // premium
import resourceTimelinePlugin from "@fullcalendar/resource-timeline" // premium
import timeGridPlugin from "@fullcalendar/timegrid"
import timelinePlugin from "@fullcalendar/timeline" // premium
import rrulePlugin from "@fullcalendar/rrule"; //

import {
  CalendarOptions,
  DateSelectArg,
  EventApi,
  EventChangeArg,
  EventClickArg,
  EventSourceInput,
  ViewApi,
} from "@fullcalendar/core"
import React from "react"
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib"
import { ComponentProps } from "streamlit-component-lib/dist/StreamlitReact"
import styled from "styled-components"
import {
  Callback,
  DateClickComponentValue,
  DateClickValue,
  EventChangeComponentValue,
  EventChangeValue,
  EventClickComponentValue,
  EventClickValue,
  EventsSetComponentValue,
  EventsSetValue,
  SelectComponentValue,
  SelectSubmitComponentValue,
  SelectSubmitValue,
  SelectValue,
  ViewValue,
} from "../types/Calendar.type"

const ENABLED_PLUGINS = [
  adaptivePlugin,
  dayGridPlugin,
  interactionPlugin,
  listPlugin,
  multiMonthPlugin,
  resourceDayGridPlugin,
  resourceTimeGridPlugin,
  resourceTimelinePlugin,
  timeGridPlugin,
  timelinePlugin,
  rrulePlugin,
]

const FullCalendarWrapper = styled.div<{ $customCSS?: string }>`
  ${(props) => props.$customCSS}
`

type MetaOption = {
  id: string
  label: string
}

type MetaConfig = {
  rooms?: MetaOption[]
  doctors?: MetaOption[]
  defaultTitle?: string
  locationLabel?: string
}

type SelectionFormState = {
  title: string
  date: string
  start: string
  end: string
  roomId?: string
  doctorId?: string
  coords: { x: number; y: number }
}

type Props = ComponentProps<{
  events?: EventSourceInput
  options?: CalendarOptions
  custom_css?: string
  callbacks?: Callback[]
  license_key?: string
  meta?: MetaConfig
}>

const CalendarFC: React.FC<Props> = ({
  args: { events, options, custom_css, callbacks, license_key, meta },
}) => {
  const metaConfig: MetaConfig = meta || {}
  const [selectionForm, setSelectionForm] =
    React.useState<SelectionFormState | null>(null)
  const popoverRef = React.useRef<HTMLDivElement | null>(null)

  const getViewValue = (view: ViewApi): ViewValue => ({
    type: view.type,
    title: view.title,
    activeStart: view.activeStart.toISOString(),
    activeEnd: view.activeEnd.toISOString(),
    currentStart: view.currentStart.toISOString(),
    currentEnd: view.currentEnd.toISOString(),
  })

  const coordsFromEvent = (evt?: MouseEvent) => {
    if (!evt) {
      return undefined
    }
    const target = evt.target as HTMLElement | null
    const rect = target?.getBoundingClientRect()
    return {
      clientX: evt.clientX,
      clientY: evt.clientY,
      pageX: evt.pageX,
      pageY: evt.pageY,
      rect: rect
        ? {
            top: rect.top + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
            height: rect.height,
          }
        : undefined,
    }
  }

  const openSelectionPopover = (args: {
    start: Date
    end: Date
    jsEvent?: MouseEvent
  }) => {
    const { start, end, jsEvent } = args
    const dateStr = start.toISOString().slice(0, 10)
    const startStr = start.toISOString().slice(11, 16)
    const endStr = end.toISOString().slice(11, 16)
    const offsetX = jsEvent ? jsEvent.clientX + 12 : window.innerWidth / 2 - 150
    const offsetY = jsEvent ? jsEvent.clientY + 12 : window.innerHeight / 2 - 120
    setSelectionForm({
      title: metaConfig.defaultTitle || "Spreekuur",
      date: dateStr,
      start: startStr,
      end: endStr,
      roomId: metaConfig.rooms?.[0]?.id,
      doctorId: undefined,
      coords: {
        x: Math.min(offsetX, window.innerWidth - 360),
        y: Math.min(offsetY, window.innerHeight - 260),
      },
    })
  }

  const handleDateClick = (arg: DateClickArg) => {
    const jsEvent = (arg as any)?.jsEvent as MouseEvent | undefined
    const endDate = new Date(arg.date.getTime() + 60 * 60 * 1000)
    openSelectionPopover({ start: arg.date, end: endDate, jsEvent })
    const dateClick: DateClickValue = {
      allDay: arg.allDay,
      date: arg.date.toISOString(),
      view: getViewValue(arg.view),
      resource: arg.resource?.toJSON(),
    }

    const componentValue: DateClickComponentValue = {
      callback: "dateClick",
      dateClick,
    }

    Streamlit.setComponentValue(componentValue)
  }

  const handleEventClick = (arg: EventClickArg) => {
    const eventClick: EventClickValue = {
      event: arg.event.toJSON(),
      view: getViewValue(arg.view),
    }

    const componentValue: EventClickComponentValue = {
      callback: "eventClick",
      eventClick,
    }

    Streamlit.setComponentValue(componentValue)
  }

  const handleEventChange = (arg: EventChangeArg) => {
    const eventChange: EventChangeValue = {
      oldEvent: arg.oldEvent.toJSON(),
      event: arg.event.toJSON(),
      relatedEvents: arg.relatedEvents.map((related) => related.toJSON()),
    }

    const componentValue: EventChangeComponentValue = {
      callback: "eventChange",
      eventChange,
    }

    Streamlit.setComponentValue(componentValue)
  }

  const handleEventsSet = (events: EventApi[]) => {
    const eventsSet: EventsSetValue = {
      events: events.map((event) => ({
        ...event.toJSON(),
        resourceId: event.getResources()[0]?.id,
      })),
    }

    const componentValue: EventsSetComponentValue = {
      callback: "eventsSet",
      eventsSet,
    }

    Streamlit.setComponentValue(componentValue)
  }

  const handleSelect = (arg: DateSelectArg) => {
    const jsEvent = (arg as any)?.jsEvent as MouseEvent | undefined
    openSelectionPopover({ start: arg.start, end: arg.end, jsEvent })
    const select: SelectValue = {
      allDay: arg.allDay,
      start: arg.start.toISOString(),
      end: arg.end.toISOString(),
      view: getViewValue(arg.view),
      resource: arg.resource?.toJSON(),
      coords: coordsFromEvent(jsEvent),
    }

    const componentValue: SelectComponentValue = {
      callback: "select",
      select,
    }

    Streamlit.setComponentValue(componentValue)
  }

  const handleSubmitSelection = () => {
    if (!selectionForm) {
      return
    }
    const payload: SelectSubmitValue = {
      title: selectionForm.title.trim(),
      date: selectionForm.date,
      start: selectionForm.start,
      end: selectionForm.end,
      roomId: selectionForm.roomId || undefined,
      doctorId: selectionForm.doctorId || undefined,
    }

    const componentValue: SelectSubmitComponentValue = {
      callback: "selectSubmit",
      selectSubmit: payload,
    }

    Streamlit.setComponentValue(componentValue)
    setSelectionForm(null)
  }

  React.useEffect(() => {
    const keyHandler = (evt: KeyboardEvent) => {
      if (evt.key === "Escape") {
        setSelectionForm(null)
      }
    }
    window.addEventListener("keydown", keyHandler)
    return () => window.removeEventListener("keydown", keyHandler)
  }, [])

  React.useEffect(() => {
    if (!selectionForm) {
      return
    }
    const clickHandler = (evt: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(evt.target as Node)
      ) {
        setSelectionForm(null)
      }
    }
    window.addEventListener("mousedown", clickHandler)
    return () => window.removeEventListener("mousedown", clickHandler)
  }, [selectionForm])

  React.useEffect(() => {
    Streamlit.setFrameHeight()
  }, [])

  const rooms = metaConfig.rooms || []
  const doctors = metaConfig.doctors || []

  return (
    <FullCalendarWrapper $customCSS={custom_css}>
      <FullCalendar
        plugins={ENABLED_PLUGINS}
        initialEvents={events}
        schedulerLicenseKey={license_key}
        dateClick={
          callbacks?.includes("dateClick") ? handleDateClick : undefined
        }
        eventClick={
          callbacks?.includes("eventClick") ? handleEventClick : undefined
        }
        eventChange={
          callbacks?.includes("eventChange") ? handleEventChange : undefined
        }
        eventsSet={
          callbacks?.includes("eventsSet") ? handleEventsSet : undefined
        }
        select={callbacks?.includes("select") ? handleSelect : undefined}
        {...options}
      />
      {selectionForm && (
        <div
          className="mp-planner-popover"
          style={{ top: selectionForm.coords.y, left: selectionForm.coords.x }}
          ref={popoverRef}
        >
          <div className="mp-popover-card">
            <header>
              <div>
                <strong>Nieuwe sessie</strong>
                {metaConfig.locationLabel && (
                  <span className="mp-popover-sub">
                    {metaConfig.locationLabel}
                  </span>
                )}
              </div>
              <button
                className="mp-popover-close"
                aria-label="Sluiten"
                onClick={() => setSelectionForm(null)}
              >
                ×
              </button>
            </header>
            <div className="mp-popover-body">
              <label>
                Titel
                <input
                  type="text"
                  value={selectionForm.title}
                  onChange={(evt) =>
                    setSelectionForm((prev) =>
                      prev ? { ...prev, title: evt.target.value } : prev
                    )
                  }
                />
              </label>
              <label>
                Datum
                <input
                  type="date"
                  value={selectionForm.date}
                  onChange={(evt) =>
                    setSelectionForm((prev) =>
                      prev ? { ...prev, date: evt.target.value } : prev
                    )
                  }
                />
              </label>
              <div className="mp-popover-grid">
                <label>
                  Start
                  <input
                    type="time"
                    value={selectionForm.start}
                    onChange={(evt) =>
                      setSelectionForm((prev) =>
                        prev ? { ...prev, start: evt.target.value } : prev
                      )
                    }
                  />
                </label>
                <label>
                  Einde
                  <input
                    type="time"
                    value={selectionForm.end}
                    onChange={(evt) =>
                      setSelectionForm((prev) =>
                        prev ? { ...prev, end: evt.target.value } : prev
                      )
                    }
                  />
                </label>
              </div>
              <label>
                Kamer
                <select
                  value={selectionForm.roomId || ""}
                  onChange={(evt) =>
                    setSelectionForm((prev) =>
                      prev ? { ...prev, roomId: evt.target.value } : prev
                    )
                  }
                >
                  <option value="">Selecteer kamer</option>
                  {rooms.map((room) => (
                    <option key={room.id} value={room.id}>
                      {room.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Arts
                <select
                  value={selectionForm.doctorId || ""}
                  onChange={(evt) =>
                    setSelectionForm((prev) =>
                      prev ? { ...prev, doctorId: evt.target.value } : prev
                    )
                  }
                >
                  <option value="">(optioneel)</option>
                  {doctors.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <footer>
              <button className="ghost" onClick={() => setSelectionForm(null)}>
                Annuleren
              </button>
              <button className="primary" onClick={handleSubmitSelection}>
                Opslaan
              </button>
            </footer>
          </div>
        </div>
      )}
    </FullCalendarWrapper>
  )
}

export default withStreamlitConnection(CalendarFC)
