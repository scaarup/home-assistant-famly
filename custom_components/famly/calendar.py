"""Calendar per child: check-in/out, pickups, days off and events."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FamlyConfigEntry
from .entity import FamlyChildEntity


async def async_setup_entry(hass: HomeAssistant, entry: FamlyConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FamlyCalendar(coordinator, cid) for cid in coordinator.data)


def _hhmm(value: datetime) -> str:
    return dt_util.as_local(value).strftime("%H:%M")


class FamlyCalendar(FamlyChildEntity, CalendarEntity):
    _attr_translation_key = "calendar"

    def __init__(self, coordinator, child_id: str) -> None:
        super().__init__(coordinator, child_id)
        self._attr_unique_id = f"{child_id}_calendar"

    def _all(self) -> list[CalendarEvent]:
        """Check-in/out as one block per day, pickups, events, days off and closing days."""
        out: list[CalendarEvent] = []
        events = self._child.get("events", [])
        default_inst = next((e["subtitle"] for e in reversed(events) if e["kind"] == "pickup" and e["subtitle"]), None)
        by_day: dict = {}
        for e in events:
            by_day.setdefault(e["date"], []).append(e)
        for day, evs in by_day.items():
            ins = [e["start"] for e in evs if e["kind"] == "check_in" and e["start"]]
            outs = [e["start"] for e in evs if e["kind"] == "check_out" and e["start"]]
            pickups = [e for e in evs if e["kind"] == "pickup" and e["start"]]
            who = pickups[-1]["picked_up_by"] if pickups else None
            if ins:
                t_in = min(ins)
                t_out = max(outs) if outs and max(outs) > t_in else None
                first = (self._child.get("name") or {}).get("firstName") or ""
                place = None
                for e in evs:
                    if e["kind"] == "check_in":
                        m = re.search(r"checkede ind i (.+)$", e["title"])
                        place = m.group(1).strip() if m else place
                inst = (pickups[-1]["subtitle"] if pickups else None) or default_inst
                where = inst or place
                summary = f"{first} checkede ind i {where}" if where else f"{first} checkede ind"
                summary += f" {_hhmm(t_in)}" + (f", ud {_hhmm(t_out)}" if t_out else "")
                parts = [place if inst and place else None, f"Hentet af {who}" if who and t_out else None]
                desc = " · ".join(p for p in parts if p) or None
                out.append(CalendarEvent(
                    start=t_in, end=t_out or t_in + timedelta(minutes=30),
                    summary=summary.strip(), description=desc))
            for p in pickups:
                out.append(CalendarEvent(
                    start=p["start"], end=p["start"] + timedelta(minutes=30),
                    summary=p["title"], description=p["subtitle"] or None))
            for e in evs:
                if e["kind"] == "leave" or (e["kind"] == "event" and not e["start"]):
                    out.append(CalendarEvent(
                        start=day, end=day + timedelta(days=1),
                        summary=e["title"], description=e["subtitle"] or None))
                elif e["kind"] == "event":
                    out.append(CalendarEvent(
                        start=e["start"], end=e["end"] or e["start"] + timedelta(hours=1),
                        summary=e["title"], description=e["subtitle"] or None))
        return out

    @staticmethod
    def _bounds(ev: CalendarEvent) -> tuple[datetime, datetime]:
        s, e = ev.start, ev.end
        if not isinstance(s, datetime):
            s = dt_util.start_of_local_day(s)
            e = dt_util.start_of_local_day(e)
        return s, e

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = [ev for ev in self._all() if self._bounds(ev)[1] > now]
        return min(upcoming, key=lambda ev: self._bounds(ev)[0], default=None)

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [ev for ev in self._all()
                if self._bounds(ev)[0] < end_date and self._bounds(ev)[1] > start_date]
