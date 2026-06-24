"""Typed configuration objects.

Before this module the four entry-point scripts carried a MAIN_DEFAULTS
dict, a loadConfigMain helper that mutated globals(), and — in buy_ovh —
a parallel MIRRORED_KEYS constant that described which of those globals
round-tripped to the interactive state dict and the persisted state
file. That pattern made adding a new flag a four-place edit and made
refetch impossible to unit-test without monkey-patching a module.

Two dataclasses cover the current scripts:

- BuyOvhConfig: everything buy_ovh / the interactive UI reads, plus the
  few flags the UI mutates at runtime (show*, fakeBuy, addVAT, months,
  quickLook). A subset — MIRRORED_KEYS — round-trips to ~/.buy_ovh/state.yaml.
- MonitorConfig: what monitor_ovh's loop reads, including the email and
  autoBuy blocks. No UI state.

Both are plain mutable dataclasses: the UI mutates the buy_ovh instance
directly, and monitor_ovh mutates autoBuy rules in place across cycles.
"""
from dataclasses import dataclass, field, fields
from typing import Any

import copy
import sys

__all__ = ['BuyOvhConfig', 'MonitorConfig', 'MIRRORED_KEYS',
           'KNOWN_YAML_KEYS', 'warn_unknown_keys']

# Keys round-tripped between the buy_ovh Config and ~/.buy_ovh/state.yaml.
# The interactive UI mutates these; everything else on BuyOvhConfig is
# conf-only. Kept here (not m/state.py) so the authoritative list lives
# next to the dataclass it describes; m.state re-exports it for the
# persistence API.
MIRRORED_KEYS = ('showCpu', 'showFqn', 'showBandwidth',
                 'showPrice', 'showFee', 'showTotalPrice',
                 'showUnavailable', 'showUnknown',
                 'fakeBuy', 'addVAT', 'months')


def _assign_from_yaml(instance, cf: dict, yaml_aliases: dict,
                      skip: frozenset = frozenset()) -> None:
    """Copy values from `cf` onto dataclass `instance` for every field
    present in the YAML (under its own name or its alias). Fields named
    in `skip` are never populated from YAML — used for ephemeral
    session state that should not be surprised by a stray conf entry."""
    for f in fields(instance):
        if f.name in skip:
            continue
        yaml_key = yaml_aliases.get(f.name, f.name)
        if yaml_key in cf:
            setattr(instance, f.name, cf[yaml_key])


@dataclass
class BuyOvhConfig:
    """Everything buy_ovh and the interactive UI read. Fields with
    _mirrored=True (see MIRRORED_KEYS) round-trip to state.yaml."""
    # --- API / catalog ---
    APIEndpoint: str = 'ovh-eu'
    ovhSubsidiary: str = 'FR'
    acceptable_dc: list = field(default_factory=list)

    # --- Cart ---
    fakeBuy: bool = True
    months: int = 1
    addVAT: bool = False

    # --- Catalog filters (conf-level) ---
    filterName: str = ''
    filterDisk: str = ''
    filterMemory: str = ''
    maxPrice: float = 0

    # --- UI-level column toggles (persisted via MIRRORED_KEYS) ---
    showBandwidth: bool = True
    showCpu: bool = True
    showFee: bool = False
    showFqn: bool = False
    showPrice: bool = True
    showTotalPrice: bool = False
    showUnavailable: bool = True
    showUnknown: bool = True

    # --- Ephemeral session state (not persisted, not from YAML) ---
    # Manual "ignore conf filters" override, toggled from the interactive UI.
    # Intentionally not mirrored: never persisted, never read from conf,
    # always starts False.
    quickLook: bool = False
    # Per-column regex filters owned by the interactive UI. Mutated in
    # place across refetches so a config reload doesn't clobber them.
    columnFilters: dict = field(default_factory=dict)

    _YAML_ALIASES = {'acceptable_dc': 'datacenters'}
    # Session-only fields — intentionally untouched by conf.yaml so a
    # user can't accidentally pin them there.
    _EPHEMERAL = frozenset({'quickLook', 'columnFilters'})

    @classmethod
    def from_yaml(cls, cf: dict) -> 'BuyOvhConfig':
        inst = cls()
        _assign_from_yaml(inst, cf, cls._YAML_ALIASES, cls._EPHEMERAL)
        return inst

    def apply_state_overlay(self, overlay: dict) -> None:
        """Overwrite MIRRORED_KEYS fields from `overlay`. Unknown keys
        and non-mirrored keys are silently skipped — the overlay is
        written by an older/newer version so we tolerate drift."""
        for k in MIRRORED_KEYS:
            if k in overlay:
                setattr(self, k, overlay[k])

    def mirrored_state(self) -> dict:
        """The subset persisted to state.yaml."""
        return {k: getattr(self, k) for k in MIRRORED_KEYS}


@dataclass
class MonitorConfig:
    """What monitor_ovh's loop reads. No UI, so no show*, no quickLook."""
    # --- API / catalog ---
    APIEndpoint: str = 'ovh-eu'
    ovhSubsidiary: str = 'FR'
    acceptable_dc: list = field(default_factory=list)

    # --- Cart ---
    fakeBuy: bool = True
    months: int = 1
    addVAT: bool = False

    # --- Catalog filters ---
    filterName: str = ''
    filterDisk: str = ''
    filterMemory: str = ''
    maxPrice: float = 0

    # --- Loop cadence ---
    sleepsecs: int = 60

    # --- Display toggles used by the catalog builder ---
    showBandwidth: bool = True

    # --- Email gating ---
    email_on: bool = False
    email_at_startup: bool = False
    email_auto_buy: bool = False
    email_added_removed: bool = False
    email_availability_monitor: str = ''
    email_availability_monitor_vps: str = ''
    email_catalog_monitor: bool = False
    email_exception: bool = False

    # --- Autobuy rules (list of dicts; num decremented in place per match) ---
    autoBuy: list = field(default_factory=list)

    _YAML_ALIASES = {'acceptable_dc': 'datacenters',
                     'autoBuy': 'auto_buy'}

    @classmethod
    def from_yaml(cls, cf: dict) -> 'MonitorConfig':
        inst = cls()
        _assign_from_yaml(inst, cf, cls._YAML_ALIASES)
        # email_* flags are only honored when email_on is set — otherwise
        # keep their defaults so accidentally leaving flags in conf.yaml
        # under email_on:false is a no-op.
        if not inst.email_on:
            defaults = cls()
            for f in fields(cls):
                if f.name.startswith('email_') and f.name != 'email_on':
                    setattr(inst, f.name, getattr(defaults, f.name))
        # auto_buy rules are mutated in place across cycles (num--), so
        # deep-copy to avoid poisoning the YAML dict.
        inst.autoBuy = copy.deepcopy(inst.autoBuy)
        return inst


# Keys consumed directly by entry points / helpers without going through a
# dataclass (API credentials, logging, email server settings). Listed here
# so the unknown-key check below doesn't flag them.
_DIRECT_YAML_KEYS = frozenset({
    'APIKey', 'APISecret', 'APIConsumerKey',
    'logFile', 'logLevel',
    'email_server_port', 'email_server_name', 'email_server_login',
    'email_server_password', 'email_sender', 'email_receiver',
})


def _known_yaml_keys() -> frozenset:
    """Every key any tool understands: both dataclasses' fields, their YAML
    aliases, and the keys consumed directly by helpers/entry points. The
    conf.yaml is shared across all tools, so validation is against the
    union -- a key used only by monitor_ovh is still 'known' to buy_ovh."""
    keys = set(_DIRECT_YAML_KEYS)
    for cls in (BuyOvhConfig, MonitorConfig):
        keys.update(f.name for f in fields(cls))
        keys.update(cls._YAML_ALIASES.values())
        # An aliased field's own name is never a valid YAML key
        # (datacenters, not acceptable_dc) -- drop it so that typo is caught.
        keys.difference_update(cls._YAML_ALIASES.keys())
    return frozenset(keys)


KNOWN_YAML_KEYS = _known_yaml_keys()


def warn_unknown_keys(cf: dict) -> list:
    """Warn (stderr) about any conf key no tool recognizes, and return the
    sorted list of unknown keys. Catches typos (showFees -> showFee) and
    stale keys that were removed from the code but left in conf.yaml.
    Runs before logging is configured, so it prints rather than logs."""
    unknown = sorted(set(cf) - KNOWN_YAML_KEYS)
    if unknown:
        print("Warning: ignoring unrecognized config key(s): "
              + ", ".join(unknown), file=sys.stderr)
    return unknown
