import logging

import readchar
from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from m.print import whichColor, console, format_age, resolve_state

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


def _row_data(plan, idx, state):
    vrack = 'none' if plan['vrack'] == 'none' else plan['vrack'].split('-')[2]
    storage = '-'.join(x for x in plan['storage'].split('-')
                       if len(x) > 1 and x[1] == 'x')
    memory = plan['memory'].split('-')[1]
    bandwidth = plan['bandwidth'].split('-')[1]
    row = [str(idx)]
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
    return row


def _price_header(months):
    return '€/mo' if months == 1 else f'€/{months}mo'


def _column_specs(state):
    cols = [('#', 'right')]
    if state['showFqn']:
        cols.append(('FQN', 'left'))
    else:
        cols.append(('Plan', 'left'))
        cols.append(('Model', 'left'))
        if state['showCpu']:
            cols.append(('CPU', 'left'))
        cols.append(('DC', 'center'))
        cols.append(('Mem', 'right'))
        cols.append(('Storage', 'left'))
    if state['showBandwidth']:
        cols.append(('BW', 'right'))
        cols.append(('vRack', 'right'))
    if state['showPrice']:
        cols.append((_price_header(state.get('months', 1)), 'right'))
    if state['showFee']:
        cols.append(('Fee', 'right'))
    if state['showTotalPrice']:
        cols.append(('Total', 'right'))
    return cols


def _build_table(displayedPlans, cursor, scroll_top, window, state):
    # Format every row up-front so column widths are locked to the widest
    # cell across the entire list, not just the visible window. Without this
    # Rich auto-sizes each column based on whatever rows happen to be on
    # screen, and a wider value scrolling in makes the whole table jump.
    specs = _column_specs(state)
    all_rows = [_row_data(p, i, state) for i, p in enumerate(displayedPlans)]
    widths = [max(len(specs[i][0]),
                  max((len(r[i]) for r in all_rows), default=0))
              for i in range(len(specs))]

    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False)
    for (header, justify), w in zip(specs, widths):
        table.add_column(header, justify=justify, no_wrap=True, min_width=w)

    end = min(scroll_top + window, len(displayedPlans))
    for i in range(scroll_top, end):
        plan = displayedPlans[i]
        style = whichColor[resolve_state(plan)]
        if i == cursor:
            style = style + ' reverse'
        table.add_row(*all_rows[i], style=style)
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
    age = format_age(fetched_at)
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

    live = Live(console=console, screen=True, auto_refresh=False,
                redirect_stdout=False, redirect_stderr=False)

    def buy_ask(plan):
        """ENTER path: suspend Live, ask invoice/buy/out, act, then resume."""
        live.stop()
        try:
            console.print(f"\n[bold]{plan['model']}[/]  ({plan['fqn']})")
            choice = input('Last chance : Invoice = I , Buy now = N , '
                           'other = out : ').strip().lower()
            logger.debug('Interactive user chose: ' + choice)
            if choice == 'i':
                buy_fn(plan, False)
                input('Press Enter.')
            elif choice == 'n':
                buy_fn(plan, True)
                input('Press Enter.')
        finally:
            live.start()

    def buy_direct(plan, buyNow):
        """! / ? paths: suspend Live, buy without asking, then resume."""
        live.stop()
        try:
            buy_fn(plan, buyNow)
            input('Press Enter.')
        finally:
            live.start()

    live.start()
    try:
        while True:
            size = console.size
            footer = _footer_bar(state, fetched_at)
            help_panel = _help_overlay() if show_help else None
            # table chrome (header + underline with SIMPLE_HEAVY) + pos line
            reserved = 3 + len(console.render_lines(footer))
            if help_panel is not None:
                reserved += len(console.render_lines(help_panel))
            window = max(3, size.height - reserved)

            if not displayedPlans:
                empty = Text.from_markup('[dim]No servers to display.[/]')
                renderables = [empty, footer]
                if help_panel is not None:
                    renderables.append(help_panel)
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
                renderables = [table, pos, footer]
                if help_panel is not None:
                    renderables.append(help_panel)

            live.update(Group(*renderables), refresh=True)

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
                live.stop()
                try:
                    displayedPlans, fetched_at = refresh_fn()
                finally:
                    live.start()
                cursor = min(cursor, max(0, len(displayedPlans) - 1))
            elif not displayedPlans:
                continue
            elif key in (readchar.key.ENTER, '\r', '\n'):
                buy_ask(displayedPlans[cursor])
            elif key == '!':
                buy_direct(displayedPlans[cursor], True)
            elif key == '?':
                buy_direct(displayedPlans[cursor], False)
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
    finally:
        live.stop()
        logger.info('Leaving interactive mode')
    return exit_reason
