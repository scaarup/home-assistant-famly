"""Device tracker pr. barn: institutionens position, mens barnet er checket ind."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FamlyConfigEntry
from .entity import FamlyChildEntity


async def async_setup_entry(hass: HomeAssistant, entry: FamlyConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FamlyTracker(coordinator, cid) for cid in coordinator.data)


class FamlyTracker(FamlyChildEntity, TrackerEntity):
    _attr_translation_key = "location"
    _attr_source_type = SourceType.GPS
    _attr_location_accuracy = 100

    def __init__(self, coordinator, child_id: str) -> None:
        super().__init__(coordinator, child_id)
        self._attr_unique_id = f"{child_id}_location"

    @property
    def _inst(self) -> dict[str, Any]:
        return self._child.get("institution") or {}

    def _checked_in(self) -> bool:
        today = dt_util.now().date()
        evs = [e for e in self._child.get("events", []) if e["date"] == today and e["start"]]
        if any(e["kind"] == "leave" for e in evs):
            return False
        ins = [e["start"] for e in evs if e["kind"] == "check_in"]
        outs = [e["start"] for e in evs if e["kind"] == "check_out"]
        return bool(ins) and not (outs and max(outs) >= max(ins))

    @property
    def latitude(self) -> float | None:
        c = self._inst.get("coords")
        return c[0] if c and self._checked_in() else None

    @property
    def longitude(self) -> float | None:
        c = self._inst.get("coords")
        return c[1] if c and self._checked_in() else None

    @property
    def extra_state_attributes(self) -> dict:
        i = self._inst
        c = i.get("coords")
        return {
            "institution": i.get("title"),
            "address": ", ".join(p for p in (i.get("street"), f"{i.get('zip') or ''} {i.get('city') or ''}".strip()) if p) or None,
            "phone": i.get("phone"), "email": i.get("email"),
            "institution_latitude": c[0] if c else None, "institution_longitude": c[1] if c else None,
        }
