"""Profile picture per child."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FamlyConfigEntry
from .entity import FamlyChildEntity


async def async_setup_entry(hass: HomeAssistant, entry: FamlyConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FamlyProfileImage(hass, coordinator, cid) for cid in coordinator.data)


class FamlyProfileImage(FamlyChildEntity, ImageEntity):
    _attr_translation_key = "profile_image"

    def __init__(self, hass: HomeAssistant, coordinator, child_id: str) -> None:
        FamlyChildEntity.__init__(self, coordinator, child_id)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{child_id}_profile_image"
        self._last_url: str | None = None
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def image_url(self) -> str | None:
        url = (self._child.get("profileImage") or {}).get("url")
        if url != self._last_url:
            self._last_url = url
            self._attr_image_last_updated = dt_util.utcnow()
        return url
