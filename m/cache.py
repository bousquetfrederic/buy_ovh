import json
import logging
from datetime import datetime
from pathlib import Path

__all__ = ['save_list', 'load_list', 'cache_file']

logger = logging.getLogger(__name__)


def cache_file():
    return Path.home() / '.buy_ovh' / 'last_list.json'


def save_list(plans, fetched_at):
    """Persist the displayed plan list with its fetch timestamp to
    ~/.buy_ovh/last_list.json so a later `buy_ovh.py buy` can reuse the
    exact rows the user just saw."""
    path = cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'fetched_at': fetched_at.isoformat(),
        'plans': plans,
    }
    path.write_text(json.dumps(payload))
    logger.info(f"Saved plan list cache to {path}")


def load_list():
    """Return (plans, fetched_at) from the cache, or (None, None) if the
    file is missing or unreadable."""
    path = cache_file()
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text())
        return payload['plans'], datetime.fromisoformat(payload['fetched_at'])
    except Exception:
        logger.exception(f"Failed to load plan list cache from {path}")
        return None, None
