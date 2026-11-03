"""Famly: børn og profilbilleder fra Famly-appens API (efterligner browseren)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FamlyApi, FamlyApiError, FamlyAuthError
from .const import (
    CALENDAR_DAYS_AHEAD,
    CALENDAR_DAYS_BACK,
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_ID,
    CONF_INSTALLATION_ID,
    DOMAIN,
    PLATFORMS,
    UPDATE_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)


class FamlyCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data: {barne-id: child-dict}."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: FamlyApi) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, config_entry=entry,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MIN),
        )
        self.api = api
        self.institutions: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            me = await self.api.async_get_context()
        except FamlyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FamlyApiError as err:
            raise UpdateFailed(str(err)) from err
        children = FamlyApi.children_from_context(me)
        today = dt_util.now().date()
        for cid, child in children.items():
            try:
                child["events"] = await self.api.async_get_calendar(
                    cid, today - timedelta(days=CALENDAR_DAYS_BACK), today + timedelta(days=CALENDAR_DAYS_AHEAD)
                )
            except FamlyAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except FamlyApiError as err:
                raise UpdateFailed(str(err)) from err
        for child in children.values():
            iid = child.get("institutionId")
            if iid and iid not in self.institutions:
                try:
                    self.institutions[iid] = await self.api.async_get_institution(iid)
                except FamlyAuthError as err:
                    raise ConfigEntryAuthFailed(str(err)) from err
                except FamlyApiError as err:
                    _LOGGER.warning("Institution %s kunne ikke hentes: %s", iid, err)
            child["institution"] = self.institutions.get(iid)
        return children


type FamlyConfigEntry = ConfigEntry[FamlyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FamlyConfigEntry) -> bool:
    api = FamlyApi(
        async_get_clientsession(hass),
        installation_id=entry.data[CONF_INSTALLATION_ID],
        device_id=entry.data[CONF_DEVICE_ID],
        access_token=entry.data[CONF_ACCESS_TOKEN],
    )
    coordinator = FamlyCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FamlyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
