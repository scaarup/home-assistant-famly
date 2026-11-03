"""Fælles basis: én HA-enhed pr. barn."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FamlyCoordinator
from .const import DOMAIN


class FamlyChildEntity(CoordinatorEntity[FamlyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FamlyCoordinator, child_id: str) -> None:
        super().__init__(coordinator)
        self._child_id = child_id
        name = coordinator.data[child_id]["name"]["fullName"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, child_id)}, name=name, manufacturer="Famly",
        )

    @property
    def _child(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._child_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._child_id in self.coordinator.data
