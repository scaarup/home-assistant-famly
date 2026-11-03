"""Config flow: login med Famly-konto (e-mail + adgangskode). Kun access-token gemmes, aldrig adgangskoden."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FamlyApi, FamlyApiError, FamlyAuthError, FamlyChallengeError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_INSTALLATION_ID,
    DOMAIN,
)


class FamlyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = FamlyApi(async_get_clientsession(self.hass))
            try:
                token = await api.async_authenticate(user_input[CONF_EMAIL].strip(), user_input["password"])
                await api.async_get_context()
            except FamlyChallengeError:
                errors["base"] = "challenge_unsupported"
            except FamlyAuthError:
                errors["base"] = "invalid_auth"
            except FamlyApiError:
                errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Famly ({user_input[CONF_EMAIL].strip()})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                        CONF_ACCESS_TOKEN: token,
                        CONF_DEVICE_ID: api.device_id,
                        CONF_INSTALLATION_ID: api.installation_id,
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required("password"): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_sign_in_again("reauth_confirm", self._get_reauth_entry(), user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_sign_in_again("reconfigure", self._get_reconfigure_entry(), user_input)

    async def _async_sign_in_again(
        self, step_id: str, entry: ConfigEntry, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = FamlyApi(
                async_get_clientsession(self.hass),
                installation_id=entry.data[CONF_INSTALLATION_ID],
                device_id=entry.data[CONF_DEVICE_ID],
            )
            try:
                token = await api.async_authenticate(entry.data[CONF_EMAIL], user_input["password"])
                await api.async_get_context()
            except FamlyChallengeError:
                errors["base"] = "challenge_unsupported"
            except FamlyAuthError:
                errors["base"] = "invalid_auth"
            except FamlyApiError:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_ACCESS_TOKEN: token, CONF_DEVICE_ID: api.device_id}
                )
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
