import logging
import yaml
from pathlib import Path

from m.conf import MIRRORED_KEYS

__all__ = ['load', 'save', 'state_file', 'MIRRORED_KEYS']

logger = logging.getLogger(__name__)

# MIRRORED_KEYS lives on m.conf now — the authoritative list is next to
# the BuyOvhConfig dataclass it describes. Re-exported here so existing
# imports (`from m.state import MIRRORED_KEYS`) keep working.


def state_file():
    return Path.home() / '.buy_ovh' / 'state.yaml'


def load():
    """Return the saved overlay as a dict, filtered to MIRRORED_KEYS.
    Returns {} if the file is absent or unreadable — conf values stand."""
    path = state_file()
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        logger.exception(f"Failed to load state from {path}")
        return {}
    return {k: v for k, v in data.items() if k in MIRRORED_KEYS}


def save(state):
    """Write MIRRORED_KEYS from `state` to ~/.buy_ovh/state.yaml."""
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: state[k] for k in MIRRORED_KEYS if k in state}
    path.write_text(yaml.safe_dump(payload, sort_keys=True))
    logger.info(f"Saved state to {path}")
