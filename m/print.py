from datetime import datetime

from rich.console import Console

import m.availability

__all__ = ['whichColor', 'console', 'format_age', 'resolve_state']

console = Console()

# Availability state -> rich style. Kept as a dict so external callers can
# look up a style for a given state.
whichColor = {
    'unknown':     'cyan',
    'low':         'yellow',
    'high':        'bold green',
    'unavailable': 'red',
    'comingSoon':  'blue',
    'autobuy':     'bold magenta',
}


def format_age(fetched_at):
    if fetched_at is None:
        return ''
    secs = int((datetime.now() - fetched_at).total_seconds())
    if secs < 60:
        return f'{secs}s ago'
    if secs < 3600:
        return f'{secs // 60}m ago'
    if secs < 86400:
        return f'{secs // 3600}h ago'
    return f'{secs // 86400}d ago'


def resolve_state(plan):
    if plan['autobuy']:
        return 'autobuy'
    avail = plan['availability']
    if not m.availability.test_availability(avail, False, True):
        return avail
    if avail.endswith('low') or avail.endswith('H'):
        return 'low'
    if avail.endswith('high'):
        return 'high'
    return 'unknown'
