"""Client for Famly's internal GraphQL API (the same calls as the web app). No HA imports."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import GRAPHQL_URL, USER_AGENT

AUTH_QUERY = """
mutation Authenticate($email: EmailAddress!, $password: Password!, $deviceId: DeviceId, $legacy: Boolean) {
  me { authenticateWithPassword(email: $email, password: $password, deviceId: $deviceId, legacy: $legacy) {
    __typename ...R } }
}
fragment R on AuthenticationResult {
  status
  ... on AuthenticationFailed { errorDetails errorTitle }
  ... on AuthenticationSucceeded { accessToken deviceId }
  ... on AuthenticationChallenged {
    loginId deviceId expiresAt
    choices { hmac requiresTwoFactor context { id target { __typename
      ... on PersonContextTarget { person { name { fullName } } children { id institutionId name { fullName } } }
      ... on InstitutionSet { title } } } }
  }
}
"""

CONTEXT_QUERY = """
query GetCurrentContext {
  me { currentContext { ...C } availableContexts { ...C } }
}
fragment C on UserContext { id target { __typename
  ... on PersonContextTarget { person { name { fullName } } children { id institutionId birthday name { firstName lastName fullName } profileImage { url } } }
  ... on InstitutionSet { title } } }
"""


class FamlyAuthError(Exception):
    """Wrong login, or the token was rejected or has expired."""


class FamlyChallengeError(FamlyAuthError):
    """Famly requires an extra step (2FA / choosing a context). Not supported yet."""

    def __init__(self, challenge: dict[str, Any]) -> None:
        super().__init__("challenged")
        self.challenge = challenge


AUTH_ERROR_HINTS = ("authenticat", "authoriz", "unauthor", "expired", "not logged in", "access token")
AUTH_ERROR_CODES = {"UNAUTHENTICATED", "UNAUTHORIZED", "FORBIDDEN", "TOKEN_EXPIRED"}


def is_auth_error(errors: Any) -> bool:
    """Does the GraphQL error list look like a rejected or expired login?"""
    for err in errors or []:
        if not isinstance(err, dict):
            continue
        code = str((err.get("extensions") or {}).get("code", "")).upper()
        text = " ".join(str(err.get(k, "")) for k in ("message", "debug")).lower()
        if code in AUTH_ERROR_CODES or any(hint in text for hint in AUTH_ERROR_HINTS):
            return True
    return False


class FamlyApiError(Exception):
    """Network problem or unexpected response."""


@dataclass
class FamlyApi:
    session: aiohttp.ClientSession
    installation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    access_token: str | None = None

    def _headers(self, route: str) -> dict[str, str]:
        h = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Origin": "https://app.famly.co",
            "Referer": "https://app.famly.co/",
            "x-famly-platform": "docker",
            "x-famly-installationid": self.installation_id,
            "x-famly-route": route,
            "x-famly-request-uuid": str(uuid.uuid4()),
        }
        if self.access_token:
            h["x-famly-accesstoken"] = self.access_token
        return h

    async def _post(self, op: str, query: str, variables: dict, route: str) -> dict:
        payload = {"operationName": op, "variables": variables, "query": query}
        try:
            async with self.session.post(
                f"{GRAPHQL_URL}?{op}", json=payload, headers=self._headers(route),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise FamlyAuthError("token rejected")
                if resp.status != 200:
                    raise FamlyApiError(f"HTTP {resp.status}")
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FamlyApiError(str(err)) from err
        if body.get("errors"):
            if is_auth_error(body["errors"]):
                raise FamlyAuthError(str(body["errors"])[:200])
            raise FamlyApiError(str(body["errors"])[:200])
        if body.get("data") is None:
            # No data and no errors: with a token this almost always means the token was rejected.
            if self.access_token and op != "Authenticate":
                raise FamlyAuthError("empty response")
            raise FamlyApiError("empty response")
        return body["data"]

    async def async_authenticate(self, email: str, password: str) -> str:
        """Sign in and return the access token."""
        data = await self._post(
            "Authenticate", AUTH_QUERY,
            {"email": email, "password": password, "deviceId": self.device_id, "legacy": False},
            "/login",
        )
        res = data["me"]["authenticateWithPassword"]
        kind = res["__typename"]
        if kind == "AuthenticationSucceeded":
            self.access_token = res["accessToken"]
            self.device_id = res.get("deviceId") or self.device_id
            return self.access_token
        if kind == "AuthenticationChallenged":
            raise FamlyChallengeError(res)
        raise FamlyAuthError(res.get("errorDetails") or res.get("status") or kind)

    async def async_get_context(self) -> dict[str, Any]:
        data = await self._post("GetCurrentContext", CONTEXT_QUERY, {}, "/account")
        if not data.get("me"):
            raise FamlyAuthError("no user in response")
        return data["me"]

    @staticmethod
    def children_from_context(me: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Collect children from all contexts, de-duplicated by child id."""
        out: dict[str, dict[str, Any]] = {}
        ctxs = [me.get("currentContext"), *(me.get("availableContexts") or [])]
        for ctx in ctxs:
            target = (ctx or {}).get("target") or {}
            for child in target.get("children") or []:
                out.setdefault(child["id"], child)
        return out

    async def async_get_calendar(self, child_id: str, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch a child's calendar (check-in/out, pickup, leave, events)."""
        url = f"https://app.famly.co/api/v2/calendar?type=RANGE&day={start}&to={end}&childId={child_id}"
        h = self._headers("/account/childProfile/:childId/activity")
        h["content-type"] = "application/json"
        try:
            async with self.session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status in (401, 403):
                    raise FamlyAuthError("token rejected")
                if resp.status != 200:
                    raise FamlyApiError(f"HTTP {resp.status}")
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FamlyApiError(str(err)) from err
        return parse_calendar(body)


    async def async_get_institution(self, institution_id: str) -> dict[str, Any]:
        data = await self._post(
            "GetInstitutionInfo", INSTITUTION_QUERY, {"institutionId": institution_id}, "/account"
        )
        inst = parse_institution(data)
        inst["coords"] = await _geocode(self.session, inst)
        return inst


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_calendar(body: Any) -> list[dict[str, Any]]:
    """Flat, time-sorted event list. kind: check_in | check_out | pickup | leave | event."""
    out: list[dict[str, Any]] = []
    periods = body if isinstance(body, list) else [body]
    for period in periods:
        for day in period.get("days", []):
            local_day = date.fromisoformat(day["day_localdate"])
            for ev in day.get("events", []):
                embed = ev.get("embed") or {}
                otype = (ev.get("originator") or {}).get("type", "")
                if otype.endswith("ChildCheckin"):
                    etype = embed.get("type")
                    kind = {"CHECK_IN": "check_in", "CHECK_OUT": "check_out"}.get(etype, "pickup")
                elif otype.endswith("ChildLeave"):
                    kind = "leave"
                else:
                    kind = "event"
                title = ev.get("title") or ""
                who = None
                if kind == "pickup":
                    m = re.search(r"hentes af (.+)$", title)
                    who = m.group(1).strip() if m else title
                out.append({
                    "kind": kind, "date": local_day, "title": title,
                    "subtitle": ev.get("subtitle") or "", "start": _dt(ev.get("from")),
                    "end": _dt(ev.get("to")), "picked_up_by": who,
                    "leave_type": embed.get("leaveType"), "otype": otype,
                })
    out.sort(key=lambda e: (e["date"], e["start"].isoformat() if e["start"] else ""))
    return out


INSTITUTION_QUERY = """
query GetInstitutionInfo($institutionId: InstitutionId!) {
  institutions(institutionId: $institutionId) {
    institutionId title timeZone
    details { address { city street zip country } phone email }
    __typename
  }
}
"""


def parse_institution(data: dict[str, Any]) -> dict[str, Any]:
    inst = (data.get("institutions") or [{}])
    inst = inst[0] if isinstance(inst, list) else inst
    details = inst.get("details") or {}
    addr = details.get("address") or {}
    return {
        "id": inst.get("institutionId"), "title": inst.get("title"), "time_zone": inst.get("timeZone"),
        "street": addr.get("street"), "zip": addr.get("zip"), "city": addr.get("city"),
        "country": addr.get("country"), "phone": details.get("phone"), "email": details.get("email"),
    }


def _address_queries(inst: dict[str, Any]) -> list[str]:
    street, zp, city, country = (inst.get(k) or "" for k in ("street", "zip", "city", "country"))
    base = f"{street}, {zp} {city}".strip(" ,")
    return [q for q in (f"{base}, {country}".strip(" ,"), base) if street]


async def _geocode(session: aiohttp.ClientSession, inst: dict[str, Any]) -> tuple[float, float] | None:
    """Address -> (lat, lon) via OpenStreetMap Nominatim. Called once per institution."""
    for q in _address_queries(inst):
        try:
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": "1"},
                headers={"User-Agent": "home-assistant-famly (custom integration)"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    if res:
                        return float(res[0]["lat"]), float(res[0]["lon"])
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError):
            continue
    return None
