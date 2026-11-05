# Famly for Home Assistant

[![Validate](https://github.com/scaarup/home-assistant-famly/actions/workflows/validate.yml/badge.svg)](https://github.com/scaarup/home-assistant-famly/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/scaarup/home-assistant-famly)](https://github.com/scaarup/home-assistant-famly/releases)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/github/license/scaarup/home-assistant-famly)](LICENSE)

A custom integration that brings your child's day at daycare from [Famly](https://www.famly.co)
into Home Assistant: whether the child is checked in, when they arrived and left, who picks them
up, days off and events, and where the institution is.

> **Unofficial.** This integration talks to the same private API as the Famly web app. It is not
> affiliated with or endorsed by Famly, it needs no paid API access, and it may stop working
> whenever Famly changes the app or its backend. Use it at your own risk.

## Features

One config entry covers your whole Famly account. Every child on the account gets its own device
with these entities:

| Platform | Entity | What it does |
|---|---|---|
| `sensor` | Child (main entity) | Status today: `not_arrived`, `checked_in`, `checked_out` or `on_leave`. |
| `sensor` | Check-in / Check-out | Time of today's check-in and check-out. |
| `sensor` | Picked up by | Who picks up the child today. Pickup time and institution are attributes. |
| `sensor` | Birthday | The child's birthday. |
| `calendar` | Calendar | Check-in and check-out per day, pickups, days off, holidays, closing days and events, 60 days back and 180 days ahead. |
| `device_tracker` | Location | The institution's position while the child is checked in. Name, address, phone and email of the institution are attributes. |
| `image` | Profile picture | The child's profile picture. |

## Requirements

- Home Assistant. Developed and tested on 2026.10; older versions are not tested.
- A Famly account (parent login) with email and password.
- [HACS](https://hacs.xyz) if you want to install through it (optional).

## Installation

### Option 1: HACS (recommended)

Famly is in the default HACS store, so there is no need to add a custom repository.

1. Make sure HACS is installed and set up in Home Assistant.
2. Click this button to open the repository in HACS, then click **Download**:

   [![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=scaarup&repository=home-assistant-famly&category=integration)

   Or search by hand: open **HACS**, search for **Famly**, open it and click **Download**.
3. **Restart Home Assistant** (Settings > System > Restart).
4. Continue with [Setup](#setup).

### Option 2: Manual

1. Download `famly.zip` from the [latest release](https://github.com/scaarup/home-assistant-famly/releases/latest).
2. Unpack it into `config/custom_components/famly/`, so that
   `config/custom_components/famly/manifest.json` exists.
3. Restart Home Assistant.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose **Famly**.
2. Enter the email and password of your Famly account.

The password is sent to Famly once to sign in and is **not stored**. Only the resulting access
token, a device id and an installation id are kept in the config entry. If Famly rejects the token,
Home Assistant asks you to sign in again.

## Limitations

- Private, undocumented API: behaviour can change without notice.
- Accounts that require a second sign-in step (two-factor authentication) are not supported yet;
  setup then reports a clear error.
- Data is polled every 5 minutes.
- The pickup name is read from Famly's own text ("... hentes af NAME" in Danish); in other
  languages the whole text is used.
- The institution's coordinates are looked up once per Home Assistant start from its address,
  using OpenStreetMap Nominatim. The address is sent to that service.
- The device tracker has a position only while the child is checked in; otherwise its state is
  `unknown`.

## Troubleshooting

- **Authentication error / entities unavailable:** the token was rejected. Home Assistant shows a
  repair flow; sign in again.
- **Wrong or missing location:** check the `institution_latitude` / `institution_longitude`
  attributes on the device tracker. They come from the address Famly has for the institution.

Enable debug logging with:

```yaml
logger:
  logs:
    custom_components.famly: debug
```

## Development and releases

Every pull request runs three checks: **hassfest** (Home Assistant's integration validator),
**HACS validation** and **lint** (ruff plus a compile check).

Releases are drafted automatically:

1. Merge pull requests as usual. Label them `enhancement` (new feature, minor bump), `bug` or
   `fix` (patch), or `breaking` (major bump); labels also group the release notes.
   [Release Drafter](https://github.com/release-drafter/release-drafter) keeps a **draft release**
   up to date with every merge to `main`, with the next version number already worked out.
2. When you want to publish, open the draft under *Releases*, check the notes and press **Publish**.
3. Publishing creates the tag `v<version>`; a workflow then writes that version into `manifest.json`
   inside `famly.zip` and uploads it to the release. HACS installs that zip, so the version
   Home Assistant shows always matches the release. The `version` in `manifest.json` on `main` is
   therefore not edited by hand and may lag behind.

## License

[MIT](LICENSE)

## Disclaimer

Famly is a trademark of Famly ApS. This project is independent and not affiliated with Famly.
