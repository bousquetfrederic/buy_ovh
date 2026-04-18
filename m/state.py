import logging
import yaml
from pathlib import Path

__all__ = ['load', 'save', 'state_file', 'MIRRORED_KEYS']

logger = logging.getLogger(__name__)

# Togglable UI flags mirrored between conf.yaml, the buy_ovh.py globals,
# and the interactive state dict. Saved to ~/.buy_ovh/state.yaml on
# interactive exit and re-applied at startup so the next run picks up
# where the user left off. conf.yaml still provides the baseline — state
# is a thin overlay on top of the loaded config.
MIRRORED_KEYS = ('showCpu', 'showFqn', 'showBandwidth',
                 'showPrice', 'showFee', 'showTotalPrice',
                 'showUnavailable', 'showUnknown',
                 'fakeBuy', 'addVAT', 'months')


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
