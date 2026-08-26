# Glorp's Awtrix Notifier

Home Assistant custom integration that publishes notifications to one or more
[Awtrix](https://blueforcer.github.io/awtrix3/) displays over MQTT, entirely configured from the
HA UI — no YAML.

## Why this exists

Before this integration, everything shown on the house's Awtrix display (`awtrix_salon`) went
through ~10 near-identical automations calling two generic scripts (`script.awtrix_custom`,
`script.awtrix_remove`). Every new rule meant hand-editing `automations.yaml` and `scripts.yaml`,
there was no way to see from the UI whether a rule had fired or why it hadn't, and one automation
was silently publishing to a display prefix that didn't exist. This integration replaces all of
that with one config entry whose **targets** (displays) and **rules** (notifications) are managed
as subentries from the integration's "..." menu, each with its own diagnostic sensors.

See [`docs/superpowers/specs/2026-08-25-glorp-awtrix-notifier-design.md`](docs/superpowers/specs/2026-08-25-glorp-awtrix-notifier-design.md)
for the full design rationale.

## Concepts

- **Target** — one physical Awtrix display: a friendly name plus its MQTT prefix (e.g.
  `awtrix_salon`).
- **Rule** — one notification: when to show it (1-3 triggers: interval, time of day, or entity
  change), an optional condition gating whether it actually shows, its text/icon/color/effect,
  and optionally the same for clearing it again. Text and icon fields accept plain text or a
  Jinja template — a plain string is just a template with no `{{ }}` in it, same as everywhere
  else in Home Assistant.

Each rule is its own device, with diagnostic sensors showing its last action (`show`/`clear`/
`none`), the reason (`ok`, `condition_non_remplie`, `entite_indisponible`, or
`erreur_template:<message>`), and when it last actually sent something.

## Installation

Via HACS: add this repository as a custom repository (category: Integration), then install
"Glorp's Awtrix Notifier".

Manually: copy `custom_components/glorp_awtrix_notifier` into your `config/custom_components/`
directory and restart Home Assistant.

Requires the `mqtt` integration to already be set up. Then go to **Settings -> Devices &
services -> Add integration -> Glorp's Awtrix Notifier**, then use its "..." menu to add at
least one target, then any rules.

## What it does

Each rule tracks its own listeners independently. When a show trigger fires (or the show
condition's entity changes, for immediate reactivity), the rule's show condition is evaluated; if
it passes (or there is none), the text/icon templates are rendered and published to every target
the rule references, as `{prefix}/custom/{slug of the rule name}` — the slug keeps every rule on
its own Awtrix "custom app", so two rules on the same display never collide. Clear triggers work
the same way, publishing an empty payload to the same topic. A rule whose template fails to render
reports the error on its reason sensor instead of publishing anything or crashing.

## Known limitations (v0.1.0)

- Editing a rule (its "reconfigure" flow) re-asks for its trigger(s)/condition from scratch; its
  name, targets, and content fields (text/icon/color/effect/hold/repeat) keep their previous
  values as defaults, everything else needs re-entering.
- Home Assistant has no hook to veto deleting a target subentry that a rule still references from
  its own config flow (unlike device removal, subentry deletion has no such API as of this
  writing). Deleting a referenced target does not crash anything: on the next reload, the
  affected rule runs with whatever targets remain (or is skipped entirely if none do), and a
  warning is logged either way — but nothing in the UI stops you from doing it.
- Targets are plain configuration (name + MQTT prefix) and don't get their own HA device/entities;
  only rules do.

## Development

The decision logic (`decision.py`, deciding `SHOW`/`CLEAR`/`NONE` from a rule's condition) and the
MQTT payload builder (`publisher.py`) are pure functions with no Home Assistant dependency, tested
with plain `pytest`:

```
pip install pytest
pytest tests/
```

`render.py`, `triggers.py`, and `config_flow.py` depend on Home Assistant and are tested manually
on the HAOS VM instead.

## Migrating existing automations

Recreate each existing Awtrix automation as a rule here, keeping the YAML automation in place
until the equivalent rule is confirmed working, then remove the old automation/script. See the
design spec's migration table for the mapping from each current automation to its rule
equivalent.

## Branding

`hacs.json` at the repo root configures how HACS lists this repository; there's no dedicated
brand icon yet (see [`glorp_battery_optimization`](https://github.com/glorp-fr/glorp_battery_optimization)
for how to add one via `icon.png`/`logo.png`).
