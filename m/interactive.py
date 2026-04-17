import logging
from datetime import datetime

import readchar
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import m.availability
from m.print import whichColor, console

__all__ = ['run']

logger = logging.getLogger(__name__)


HELP_LINES = [
    ('↑/↓  j/k',    'move cursor'),
    ('PgUp/PgDn',   'page up / down'),
    ('g / G',       'top / bottom'),
    ('Enter',       'buy or invoice (ask)'),
    ('!',           'buy now'),
    ('?',           'invoice'),
    ('r',           'refresh catalog'),
    ('c',           'toggle CPU column'),
    ('f',           'toggle FQN view'),
    ('b',           'toggle Bandwidth/vRack'),
    ('u / U',       'toggle Unavailable / Unknown'),
    ('$',           'toggle Fake-buy'),
    ('h',           'toggle this help'),
    (':',           'drop to command prompt'),
    ('q  Esc',      'quit'),
]


def _format_age(fetched_at):
    if fetched_at is None:
        return ''
    delta = datetime.now() - fetched_at
    secs = int(delta.total_seconds())
    if secs < 60:
        return f'{secs}s ago'
    if secs < 3600:
        return f'{secs // 60}m ago'
    if secs < 86400:
        return f'{secs // 3600}h ago'
    return f'{secs // 86400}d ago'


def _resolve_state(plan):
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


def _build_table(displayedPlans, cursor, scroll_top, window, state):
    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False)
    table.add_column('#', justify='right', no_wrap=True)
    if state['showFqn']:
        table.add_column('FQN', no_wrap=True)
    else:
        table.add_column('Plan', no_wrap=True)
        table.add_column('Model', no_wrap=True)
        if state['showCpu']:
            table.add_column('CPU', no_wrap=True)
        table.add_column('DC', justify='center', no_wrap=True)
        table.add_column('Mem', justify='right', no_wrap=True)
        table.add_column('Storage', no_wrap=True)
    if state['showBandwidth']:
        table.add_column('BW', justify='right', no_wrap=True)
        table.add_column('vRack', justify='right', no_wrap=True)
    if state['showPrice']:
        table.add_column('€/mo', justify='right', no_wrap=True)
    if state['showFee']:
        table.add_column('Fee', justify='right', no_wrap=True)
    if state['showTotalPrice']:
        table.add_column('Total', justify='right', no_wrap=True)

    end = min(scroll_top + window, len(displayedPlans))
    for i in range(scroll_top, end):
        plan = displayedPlans[i]
        vrack = 'none' if plan['vrack'] == 'none' else plan['vrack'].split('-')[2]
        storage = '-'.join(x for x in plan['storage'].split('-')
                           if len(x) > 1 and x[1] == 'x')
        memory = plan['memory'].split('-')[1]
        bandwidth = plan['bandwidth'].split('-')[1]
        style = whichColor[_resolve_state(plan)]
        if i == cursor:
            style = style + ' reverse'

        row = [str(i)]
        if state['showFqn']:
            row.append(plan['fqn'])
        else:
            row.append(plan['planCode'])
            row.append(plan['model'])
            if state['showCpu']:
                row.append(plan['cpu'])
            row.append(plan['datacenter'])
            row.append(memory)
            row.append(storage)
        if state['showBandwidth']:
            row.append(bandwidth)
            row.append(vrack)
        if state['showPrice']:
            row.append(f"{plan['price']:.2f}")
        if state['showFee']:
            row.append(f"{plan['fee']:.2f}")
        if state['showTotalPrice']:
            row.append(f"{plan['fee'] + plan['price']:.2f}")
        table.add_row(*row, style=style)
    return table


def _toggle(key, label, on):
    # Active toggles render bright; inactive ones are dimmed so the
    # footer doubles as a status bar.
    if on:
        return f'[bold bright_cyan]{key}[/] [bright_white]{label}[/]'
    return f'[dim]{key} {label}[/]'


def _footer_bar(state, fetched_at):
    nav = [
        '[bold]↑↓[/] move',
        '[bold]↵[/] buy/invoice',
        '[bold]![/] now',
        '[bold]?[/] invoice',
        '[bold]r[/] refresh',
    ]
    toggles = [
        _toggle('c', 'CPU', state['showCpu']),
        _toggle('f', 'FQN', state['showFqn']),
        _toggle('b', 'BW', state['showBandwidth']),
        _toggle('u', 'unavail', state['showUnavailable']),
        _toggle('U', 'unknown', state['showUnknown']),
    ]
    tail = ['[bold]h[/] help', '[bold]:[/] prompt', '[bold]q[/] quit']
    if state['fakeBuy']:
        fake = '[black on yellow] $ FAKE BUY [/]'
    else:
        fake = '[white on red] $ REAL BUY [/]'
    age = _format_age(fetched_at)
    age_part = f'[bright_black]fetched {age}[/]    ' if age else ''
    line = age_part + '   '.join(nav) + '    ' + '  '.join(toggles) + '    ' + \
           '   '.join(tail) + '    ' + fake
    return Panel(Text.from_markup(line),
                 border_style='bright_black', box=box.ROUNDED, padding=(0, 1))


def _help_overlay():
    lines = [Text.from_markup(f'[bold cyan]{k:<12}[/] {v}') for k, v in HELP_LINES]
    return Panel(Group(*lines), title='Keys', title_align='left',
                 border_style='cyan', box=box.ROUNDED)


def run(displayedPlans, state, buy_fn, refilter_fn,
        refresh_fn=None, fetched_at=None):
    """
    state: dict of toggle flags the caller reads back after return.
           Keys: showCpu, showFqn, showBandwidth, showPrice, showFee,
                 showTotalPrice, showUnavailable, showUnknown, fakeBuy.
    buy_fn(plan, buyNow): called when user buys or invoices a plan.
    refilter_fn(): returns a freshly-filtered displayedPlans list, using
                   the current state dict plus caller's plans/filters.
    refresh_fn(): re-fetches availabilities/catalog and returns
                  (new displayedPlans, new fetched_at datetime).
    fetched_at: datetime of the most recent fetch, used for the age label.

    Returns 'prompt' when the user wants the command prompt (':'),
    or 'quit' on q/Esc/Ctrl-C.
    """
    logger.info('Entering interactive mode')
    exit_reason = 'quit'

    cursor = 0
    scroll_top = 0
    show_help = False

    with console.screen():
        try:
            while True:
                size = console.size
                reserved = 7 + (len(HELP_LINES) + 2 if show_help else 0)
                window = max(3, size.height - reserved)

                if not displayedPlans:
                    empty = Text.from_markup('[dim]No servers to display.[/]')
                    renderables = [empty, _footer_bar(state, fetched_at)]
                    if show_help:
                        renderables.append(_help_overlay())
                    console.clear()
                    console.print(Group(*renderables))
                else:
                    if cursor < 0:
                        cursor = 0
                    if cursor >= len(displayedPlans):
                        cursor = len(displayedPlans) - 1
                    if cursor < scroll_top:
                        scroll_top = cursor
                    elif cursor >= scroll_top + window:
                        scroll_top = cursor - window + 1
                    max_scroll = max(0, len(displayedPlans) - window)
                    scroll_top = max(0, min(scroll_top, max_scroll))

                    table = _build_table(displayedPlans, cursor, scroll_top,
                                         window, state)
                    pos = Text.from_markup(
                        f'[bright_black]{cursor + 1}/{len(displayedPlans)}'
                        f'   (rows {scroll_top + 1}-{scroll_top + min(window, len(displayedPlans) - scroll_top)})[/]')
                    renderables = [table, pos, _footer_bar(state, fetched_at)]
                    if show_help:
                        renderables.append(_help_overlay())

                    console.clear()
                    console.print(Group(*renderables))

                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    break

                if key in (readchar.key.UP, 'k'):
                    cursor -= 1
                elif key in (readchar.key.DOWN, 'j'):
                    cursor += 1
                elif key == readchar.key.PAGE_UP:
                    cursor -= window
                elif key == readchar.key.PAGE_DOWN:
                    cursor += window
                elif key in (readchar.key.HOME, 'g'):
                    cursor = 0
                elif key in (readchar.key.END, 'G'):
                    cursor = len(displayedPlans) - 1
                elif key in ('q', readchar.key.ESC):
                    exit_reason = 'quit'
                    break
                elif key == ':':
                    exit_reason = 'prompt'
                    break
                elif key == 'h':
                    show_help = not show_help
                elif key == 'r' and refresh_fn is not None:
                    displayedPlans, fetched_at = refresh_fn()
                    cursor = min(cursor, max(0, len(displayedPlans) - 1))
                elif not displayedPlans:
                    # without rows, none of the below keys make sense
                    continue
                elif key in (readchar.key.ENTER, '\r', '\n'):
                    plan = displayedPlans[cursor]
                    console.print(f"\n[bold]{plan['model']}[/]  ({plan['fqn']})")
                    choice = input('Last chance : Invoice = I , Buy now = N , other = out : ').strip().lower()
                    logger.debug('Interactive user chose: ' + choice)
                    if choice == 'i':
                        buy_fn(plan, False)
                        input('Press Enter.')
                    elif choice == 'n':
                        buy_fn(plan, True)
                        input('Press Enter.')
                elif key == '!':
                    plan = displayedPlans[cursor]
                    buy_fn(plan, True)
                    input('Press Enter.')
                elif key == '?':
                    plan = displayedPlans[cursor]
                    buy_fn(plan, False)
                    input('Press Enter.')
                elif key == 'c':
                    state['showCpu'] = not state['showCpu']
                elif key == 'f':
                    state['showFqn'] = not state['showFqn']
                elif key == 'b':
                    state['showBandwidth'] = not state['showBandwidth']
                elif key == 'u':
                    state['showUnavailable'] = not state['showUnavailable']
                    displayedPlans = refilter_fn()
                    cursor = min(cursor, max(0, len(displayedPlans) - 1))
                elif key == 'U':
                    state['showUnknown'] = not state['showUnknown']
                    displayedPlans = refilter_fn()
                    cursor = min(cursor, max(0, len(displayedPlans) - 1))
                elif key == '$':
                    state['fakeBuy'] = not state['fakeBuy']
                # unknown keys: ignored
        finally:
            logger.info('Leaving interactive mode')
    return exit_reason
