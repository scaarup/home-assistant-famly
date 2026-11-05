"""Sensors per child: status today, check-in/out, pickup, birthday."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FamlyConfigEntry
from .entity import FamlyChildEntity

STATUSES = ["not_arrived", "checked_in", "checked_out", "on_leave"]


async def async_setup_entry(hass: HomeAssistant, entry: FamlyConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    ents = []
    for cid in coordinator.data:
        ents += [FamlyStatus(coordinator, cid), FamlyCheckTime(coordinator, cid, "check_in"),
                 FamlyCheckTime(coordinator, cid, "check_out"), FamlyPickup(coordinator, cid),
                 FamlyBirthday(coordinator, cid)]
    async_add_entities(ents)


class _Today(FamlyChildEntity, SensorEntity):
    def _today(self, kind: str) -> list[dict[str, Any]]:
        today = dt_util.now().date()
        return [e for e in self._child.get("events", []) if e["date"] == today and e["kind"] == kind]


class FamlyStatus(_Today):
    """The child's main entity: named after the child, the state is today's status."""

    _attr_name = None
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, coordinator, child_id: str) -> None:
        super().__init__(coordinator, child_id)
        self._attr_unique_id = f"{child_id}_status"

    @property
    def native_value(self) -> str:
        if self._today("leave"):
            return "on_leave"
        ins = [e["start"] for e in self._today("check_in") if e["start"]]
        outs = [e["start"] for e in self._today("check_out") if e["start"]]
        if not ins:
            return "not_arrived"
        if outs and max(outs) >= max(ins):
            return "checked_out"
        return "checked_in"

    @property
    def extra_state_attributes(self) -> dict:
        leave = self._today("leave")
        return {"leave_type": leave[0]["leave_type"] if leave else None,
                "leave_note": leave[0]["subtitle"] if leave else None}


class FamlyCheckTime(_Today):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, child_id: str, kind: str) -> None:
        super().__init__(coordinator, child_id)
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{child_id}_{kind}"

    @property
    def native_value(self) -> datetime | None:
        times = [e["start"] for e in self._today(self._kind) if e["start"]]
        return (max(times) if self._kind == "check_out" else min(times)) if times else None


class FamlyPickup(_Today):
    _attr_translation_key = "pickup"

    def __init__(self, coordinator, child_id: str) -> None:
        super().__init__(coordinator, child_id)
        self._attr_unique_id = f"{child_id}_pickup"

    @property
    def native_value(self) -> str | None:
        p = self._today("pickup")
        return p[-1]["picked_up_by"] if p else None

    @property
    def extra_state_attributes(self) -> dict:
        p = self._today("pickup")
        return {"pickup_time": p[-1]["start"].isoformat() if p and p[-1]["start"] else None,
                "institution": p[-1]["subtitle"] if p else None}


class FamlyBirthday(FamlyChildEntity, SensorEntity):
    _attr_translation_key = "birthday"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, child_id: str) -> None:
        super().__init__(coordinator, child_id)
        self._attr_unique_id = f"{child_id}_birthday"

    @property
    def native_value(self) -> date | None:
        raw = self._child.get("birthday")
        try:
            return date.fromisoformat(raw[:10]) if raw else None
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        return {"institution_id": self._child.get("institutionId")}
