import io
import logging
import re
import select
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout

import readchar
from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from m.catalog import column_display_value
from m.print import console, format_age, resolve_state, whichColor

__all__ = ['run', 'render_list', 'parse_command']

logger = logging.getLogger(__name__)


@contextmanager
def _cbreak_mode():
    """Hold the terminal in cbreak mode for the entire interactive session.
    Toggling termios per-keystroke used to let auto-repeat leak bytes into
    the cooked (echoing) state between reads — the terminal would echo raw
    escape sequences like '^[[B' on-screen. Setting it once for the whole
    run stops that. Yields False on non-POSIX so the caller knows to fall
    back to readchar.readkey()."""
    try:
        import termios
        import tty
    except ImportError:
        yield False
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _readkey(cbreak):
    """readchar.readkey() blocks after ESC waiting for an escape sequence,
    so a bare Esc press never returns until the user hits another key. And
    we can't just peek with select() around readchar's readchar(), because
    sys.stdin's BufferedReader may already hold the rest of the sequence
    while select() on the fd sees nothing pending.

    Bypass Python's buffering by reading directly from the fd via os.read.
    The terminal is already in cbreak mode for the whole interactive run
    (see _cbreak_mode). After an ESC we wait 50 ms for a continuation byte;
    if none arrives the user really did hit Esc. Falls back to
    readchar.readkey() on non-POSIX platforms."""
    if not cbreak:
        return readchar.readkey()
    import os

    fd = sys.stdin.fileno()
    b = os.read(fd, 1)
    if not b:
        return ''
    c1 = b.decode('utf-8', 'replace')
    if c1 == '\x03':
        raise KeyboardInterrupt
    if c1 != '\x1b':
        return c1
    if not select.select([fd], [], [], 0.05)[0]:
        return '\x1b'
    seq = b''
    while select.select([fd], [], [], 0.005)[0]:
        chunk = os.read(fd, 32)
        if not chunk:
            break
        seq += chunk
    return c1 + seq.decode('utf-8', 'replace')


HELP_LINES = [
    ('↑/↓  j/k',         'move cursor'),
    ('PgUp/PgDn',        'page up / down'),
    ('g / G',            'top / bottom'),
    ('1-9 then ! / ?',   'buy (!) / invoice (?) N times'),
    ('! / ?',            'buy now / invoice (once)'),
    ('/',                'enter filter mode'),
    (':',                'enter buy-command mode'),
    ('X',                'clear all filters'),
    ('r',                'refresh catalog'),
    ('R',                'reload config from disk'),
    ('M',                'cycle commitment term 1 → 12 → 24 months'),
    ('T',                'toggle VAT in prices'),
    ('c / f / b',        'toggle CPU / FQN / BW columns'),
    ('u / U',            'toggle Unavailable / Unknown rows'),
    ('$',                'toggle Fake-buy'),
    ('Q',                'toggle Quick-look (ignore conf name/disk/memory/price filters)'),
    ('h',                'toggle this help'),
    ('q  Esc',           'quit'),
]

FILTER_HELP_LINES = [
    ('← / →   Tab / S-Tab', 'previous / next column'),
    ('type',                'edit regex (numeric col: <N, >=N, =N)'),
    ('Backspace',           'delete one char'),
    ('Ctrl-U',              'clear the focused cell'),
    ('Enter',               'apply and leave filter mode'),
    ('Esc',                 'cancel changes'),
]

COMMAND_HELP_LINES = [
    ('!N',     'buy row N now'),
    ('?N',     'request invoice for row N'),
    ('NxM',    'multiplier — e.g. !3x2 buys row 3 twice'),
    ('N*M',    'same as NxM'),
    ('space',  'separate multiple tokens, e.g. !3 ?5x2'),
    ('Enter',  'run the whole command line'),
    ('Esc',    'cancel'),
    ('Ctrl-U', 'clear the line'),
]

_COMMAND_TOKEN_RE = re.compile(r'^([!?])(\d+)(?:[x*](\d+))?$')


def parse_command(line):
    """Public alias so non-interactive callers (e.g. the `buy` CLI subcommand)
    can reuse the exact same grammar as interactive command mode."""
    return _parse_command(line)


def render_list(displayedPlans, state):
    """One-shot, non-interactive render of the plan list to the shared
    console — used by the `list` CLI subcommand. Matches interactive column
    choices but drops the filter bar, cursor, footer, and any Live chrome."""
    cols = _visible_columns(state)
    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False)
    for header, justify, _key in cols:
        table.add_column(header, justify=justify, no_wrap=True)
    for i, plan in enumerate(displayedPlans):
        style = whichColor[resolve_state(plan)]
        table.add_row(*_row_data(plan, i, cols), style=style)
    console.print(table)


def _parse_command(line):
    """Parse a buy command line into ops + errors.
    Each token is `[!?]N[xM|*M]`. Returns (ops, errors) where ops is a list
    of (buyNow, index, times) and errors is a list of human-readable strings
    for tokens that didn't parse."""
    ops = []
    errors = []
    for tok in line.split():
        m = _COMMAND_TOKEN_RE.match(tok)
        if not m:
            errors.append(f'bad token: {tok!r} (expected !N, ?N, !NxM, ...)')
            continue
        sign, n, mult = m.groups()
        ops.append((sign == '!', int(n), int(mult) if mult else 1))
    return ops, errors


def _visible_columns(state):
    """Return a list of (header, justify, filter_key) tuples in display
    order. filter_key is None for the row-number column."""
    cols = [('#', 'right', None)]
    if state['showFqn']:
        cols.append(('FQN', 'left', 'fqn'))
    else:
        cols.append(('Plan', 'left', 'planCode'))
        cols.append(('Model', 'left', 'model'))
        if state['showCpu']:
            cols.append(('CPU', 'left', 'cpu'))
        cols.append(('DC', 'center', 'datacenter'))
        cols.append(('Mem', 'right', 'memory'))
        cols.append(('Storage', 'left', 'storage'))
    if state['showBandwidth']:
        cols.append(('BW', 'right', 'bandwidth'))
        cols.append(('vRack', 'right', 'vrack'))
    if state['showPrice']:
        header = '€/mo' if state.get('months', 1) == 1 else f"€/{state['months']}mo"
        cols.append((header, 'right', 'price'))
    if state['showFee']:
        cols.append(('Fee', 'right', 'fee'))
    if state['showTotalPrice']:
        cols.append(('Total', 'right', 'total'))
    return cols


def _row_data(plan, idx, cols):
    row = [str(idx)]
    for _header, _justify, key in cols[1:]:
        row.append(column_display_value(plan, key))
    return row


def _filter_cell_text(pat, focused):
    if focused:
        return Text((pat or '') + '▌', style='black on bright_yellow')
    if pat:
        return Text(pat, style='bold bright_white on grey23')
    return Text('—', style='dim')


def _filter_cell_raw(pat, focused):
    """Raw string used only for width calculation; matches cell length."""
    if focused:
        return (pat or '') + '▌'
    return pat or '—'


def _build_table(displayedPlans, cursor, scroll_top, window, state,
                 cols, filters, focus_key, editing):
    # Format every row up-front so column widths are locked to the widest
    # value across headers + all rows + filter cells. Without this, scrolling
    # a wider value into the window resizes the whole table.
    all_rows = [_row_data(p, i, cols) for i, p in enumerate(displayedPlans)]
    filter_strs = []
    for _h, _j, key in cols:
        pat = filters.get(key, '') if key else ''
        filter_strs.append(_filter_cell_raw(pat, editing and key == focus_key))

    widths = []
    for i, (header, _justify, _key) in enumerate(cols):
        w = max(len(header), len(filter_strs[i]),
                max((len(r[i]) for r in all_rows), default=0))
        widths.append(w)

    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False)
    for (header, justify, _key), w in zip(cols, widths):
        table.add_column(header, justify=justify, no_wrap=True, min_width=w)

    # Filter bar row, always shown so the current filter set is visible.
    filter_cells = []
    for _h, _j, key in cols:
        pat = filters.get(key, '') if key else ''
        filter_cells.append(_filter_cell_text(pat, editing and key == focus_key))
    table.add_row(*filter_cells)

    end = min(scroll_top + window, len(displayedPlans))
    for i in range(scroll_top, end):
        plan = displayedPlans[i]
        style = whichColor[resolve_state(plan)]
        if i == cursor:
            style = style + ' reverse'
        table.add_row(*all_rows[i], style=style)
    return table


def _toggle(key, label, on):
    if on:
        return f'[bold bright_cyan]{key}[/] [bright_white]{label}[/]'
    return f'[dim]{key} {label}[/]'


def _footer_bar(state, fetched_at, count_buffer, mode, fetching=False):
    """Footer is a Panel with a few short logical lines:
      - meta line: status (age / 'fetching…'), multiplier, fake/real badge
                   (fake/real is right-aligned via Table.grid)
      - nav line:  the keys you press to *do* things
      - toggles:   nav mode only — flags you flip on/off
    Breaking it into distinct rows means each category lives on its own line
    instead of wrapping whenever the terminal happens to be narrow."""
    if state['fakeBuy']:
        fake_markup = '[black on yellow] $ FAKE BUY [/]'
    else:
        fake_markup = '[white on red] $ REAL BUY [/]'
    if fetching:
        status = '[black on bright_yellow] fetching… [/]'
    else:
        age = format_age(fetched_at)
        status = f'[bright_black]fetched {age}[/]' if age else ''
    multiplier = (f'[black on bright_yellow] × {count_buffer} [/]'
                  if count_buffer else '')
    meta_left = '   '.join(b for b in (status, multiplier) if b)
    meta = Table.grid(expand=True)
    meta.add_column(justify='left')
    meta.add_column(justify='right')
    meta.add_row(Text.from_markup(meta_left) if meta_left else Text(''),
                 Text.from_markup(fake_markup))

    if mode == 'filter':
        nav = '   '.join([
            '[bold]←→[/] column',
            '[bold]Tab[/] next',
            '[bold]type[/] regex',
            '[bold]↵[/] apply',
            '[bold]Esc[/] cancel',
            '[bold]^U[/] clear cell',
            '[bold]h[/] help',
        ])
        rows = [meta, Text.from_markup(nav)]
    elif mode == 'command':
        nav = '   '.join([
            '[bold]type[/] !N ?N !NxM ...',
            '[bold]↵[/] run',
            '[bold]Esc[/] cancel',
            '[bold]^U[/] clear',
            '[bold]h[/] help',
        ])
        rows = [meta, Text.from_markup(nav)]
    else:
        months = state.get('months', 1)
        term_label = '1mo' if months == 1 else f'{months}mo'
        nav = '   '.join([
            '[bold]↑↓[/] move',
            '[bold]![/] buy',
            '[bold]?[/] invoice',
            '[bold]:[/] command',
            '[bold]/[/] filter',
            '[bold]X[/] clear',
            '[bold]r[/] refresh',
            f'[bold]M[/] {term_label}',
            '[bold]h[/] help',
            '[bold]R[/] reload',
            '[bold]q[/] quit',
        ])
        toggles = '  '.join([
            _toggle('c', 'CPU', state['showCpu']),
            _toggle('f', 'FQN', state['showFqn']),
            _toggle('b', 'BW', state['showBandwidth']),
            _toggle('T', 'VAT', state.get('addVAT', False)),
            _toggle('u', 'unavail', state['showUnavailable']),
            _toggle('U', 'unknown', state['showUnknown']),
            _toggle('$', 'fake', state['fakeBuy']),
            _toggle('Q', 'QuickLook', state.get('quickLook', False)),
        ])
        rows = [meta, Text.from_markup(nav), Text.from_markup(toggles)]
    return Panel(Group(*rows),
                 border_style='bright_black', box=box.ROUNDED, padding=(0, 1))


def _help_overlay(mode):
    if mode == 'filter':
        lines, title = FILTER_HELP_LINES, 'Filter keys'
    elif mode == 'command':
        lines, title = COMMAND_HELP_LINES, 'Buy-command syntax'
    else:
        lines, title = HELP_LINES, 'Keys'
    rendered = [Text.from_markup(f'[bold cyan]{k:<22}[/] {v}')
                for k, v in lines]
    return Panel(Group(*rendered), title=title, title_align='left',
                 border_style='cyan', box=box.ROUNDED)


def _printable(key):
    return len(key) == 1 and key.isprintable()


def run(displayedPlans, state, buy_fn, refilter_fn,
        refresh_fn=None, reload_fn=None, fetched_at=None):
    """
    state: dict of toggle flags the caller reads back on return. Keys:
      showCpu, showFqn, showBandwidth, showPrice, showFee, showTotalPrice,
      showUnavailable, showUnknown, fakeBuy, addVAT, months, filters.
    `filters` is a mutable {column_key: pattern} dict owned by the caller;
    interactive mutates it in place.
    buy_fn(plan, buyNow): called once per buy, N times for a N-multiplier.
    refilter_fn(): returns a freshly filtered displayedPlans for the current
      state and filters.
    refresh_fn(): re-fetches availabilities/catalog with the current state
      (months/addVAT written back to globals by the caller) and returns
      (displayedPlans, fetched_at).
    reload_fn(): re-reads the config file (mutating state in place) and
      returns (displayedPlans, fetched_at).
    """
    logger.info('Entering interactive mode')

    cursor = 0
    scroll_top = 0
    show_help = False
    mode = 'nav'
    count_buffer = ''
    filters = state.setdefault('filters', {})
    filter_snapshot = dict(filters)
    focus_idx = 0
    buy_message = None
    command_buffer = ''

    def filterable():
        return [c for c in _visible_columns(state) if c[2] is not None]

    live = Live(console=console, screen=True, auto_refresh=False,
                redirect_stdout=False, redirect_stderr=False)

    def buy_many(plan, buyNow, times):
        # Keep the Live display up; capture everything the buy path prints
        # into a buffer and surface it as an overlay panel. The next key
        # press dismisses the panel.
        nonlocal buy_message
        render(message=Text.from_markup(
            f'[bold]Buying[/] {plan.get("model", "")} '
            f'in {plan.get("datacenter", "")}…'))
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            for _ in range(times):
                try:
                    buy_fn(plan, buyNow)
                except Exception:
                    logger.exception('Buy failed inside interactive')
        out = buf.getvalue().rstrip() or '(no output)'
        buy_message = Text(out)

    def run_command(line):
        """Parse and run a buy-command line. Errors and output go to the
        same yellow buy panel as a single-row buy."""
        nonlocal buy_message
        ops, errors = _parse_command(line)
        if not ops and not errors:
            return
        render(message=Text.from_markup(f'[bold]Running[/] {line}…'))
        buf = io.StringIO()
        for e in errors:
            buf.write(e + '\n')
        with redirect_stdout(buf), redirect_stderr(buf):
            for buyNow, n, times in ops:
                if n < 0 or n >= len(displayedPlans):
                    max_idx = len(displayedPlans) - 1
                    print(f'index {n} out of range (0-{max_idx})')
                    continue
                plan = displayedPlans[n]
                for _ in range(times):
                    try:
                        buy_fn(plan, buyNow)
                    except Exception:
                        logger.exception('Buy failed inside interactive command')
        out = buf.getvalue().rstrip() or '(no output)'
        buy_message = Text(out)

    def render(fetching=False, message=None):
        """Paint the current state to the Live display. Used both by the main
        loop and by key handlers that want to show a 'fetching…' hint before
        synchronously waiting on the network."""
        nonlocal cursor, scroll_top, focus_idx
        cols = _visible_columns(state)
        fcols = filterable()
        if fcols:
            focus_idx = min(focus_idx, len(fcols) - 1)
        focus_key = fcols[focus_idx][2] if (fcols and mode == 'filter') else None

        size = console.size
        footer = _footer_bar(state, fetched_at, count_buffer, mode, fetching)
        help_panel = _help_overlay(mode) if show_help else None
        msg = message if message is not None else buy_message
        if msg is not None:
            buy_panel = Panel(
                Group(msg, Text.from_markup('[dim]Press any key to dismiss[/]')),
                title='Buy', title_align='left',
                border_style='bright_yellow', box=box.ROUNDED)
        else:
            buy_panel = None
        if mode == 'command':
            cmd_line = Text('> ', style='bold') + Text(
                command_buffer + '▌', style='black on bright_yellow')
            hint = Text.from_markup(
                '[dim]e.g. [/][bold]!3 ?5x2 !10*3[/]  '
                '[dim]— Enter run, Esc cancel, ^U clear, h help[/]')
            cmd_panel = Panel(Group(cmd_line, hint),
                              title='Buy command', title_align='left',
                              border_style='cyan', box=box.ROUNDED)
        else:
            cmd_panel = None
        # chrome: header row + header underline (2 lines) + filter row +
        # position line = 4, plus footer and optional help/buy/cmd panels.
        reserved = 4 + len(console.render_lines(footer))
        if help_panel is not None:
            reserved += len(console.render_lines(help_panel))
        if buy_panel is not None:
            reserved += len(console.render_lines(buy_panel))
        if cmd_panel is not None:
            reserved += len(console.render_lines(cmd_panel))
        window = max(3, size.height - reserved)

        if cursor < 0:
            cursor = 0
        if displayedPlans and cursor >= len(displayedPlans):
            cursor = len(displayedPlans) - 1
        if cursor < scroll_top:
            scroll_top = cursor
        elif cursor >= scroll_top + window:
            scroll_top = cursor - window + 1
        max_scroll = max(0, len(displayedPlans) - window)
        scroll_top = max(0, min(scroll_top, max_scroll))

        table = _build_table(displayedPlans, cursor, scroll_top, window,
                             state, cols, filters, focus_key,
                             mode == 'filter')
        if displayedPlans:
            pos = Text.from_markup(
                f'[bright_black]{cursor + 1}/{len(displayedPlans)}'
                f'   (rows {scroll_top + 1}-'
                f'{scroll_top + min(window, len(displayedPlans) - scroll_top)})[/]')
        else:
            pos = Text.from_markup(
                '[dim]No servers match the current filters. '
                'Press [bold]/[/] to edit or [bold]X[/] to clear.[/]')
        renderables = [table, pos, footer]
        if cmd_panel is not None:
            renderables.append(cmd_panel)
        if buy_panel is not None:
            renderables.append(buy_panel)
        if help_panel is not None:
            renderables.append(help_panel)
        live.update(Group(*renderables), refresh=True)
        return window

    def do_fetch(fn):
        """Keep the table on screen while the fetch runs; only the footer
        changes to a 'fetching…' hint."""
        nonlocal displayedPlans, fetched_at
        render(fetching=True)
        try:
            displayedPlans, fetched_at = fn()
        except Exception:
            logger.exception('Fetch inside interactive failed')

    cbreak_cm = _cbreak_mode()
    cbreak = cbreak_cm.__enter__()
    live.start()
    try:
        while True:
            window = render()

            try:
                key = _readkey(cbreak)
            except KeyboardInterrupt:
                break

            # Dismiss a buy-result overlay on any key, without acting on it.
            if buy_message is not None:
                buy_message = None
                continue

            # ---------------- FILTER MODE ----------------
            if mode == 'filter':
                fcols = filterable()
                fkey = fcols[focus_idx][2] if fcols else None
                if key == readchar.key.ESC:
                    filters.clear()
                    filters.update(filter_snapshot)
                    displayedPlans = refilter_fn()
                    mode = 'nav'
                elif key in (readchar.key.ENTER, readchar.key.CR, readchar.key.LF):
                    displayedPlans = refilter_fn()
                    mode = 'nav'
                elif key in (readchar.key.RIGHT, readchar.key.TAB):
                    if fcols:
                        focus_idx = (focus_idx + 1) % len(fcols)
                elif key in (readchar.key.LEFT, readchar.key.SHIFT_TAB):
                    if fcols:
                        focus_idx = (focus_idx - 1) % len(fcols)
                elif key == readchar.key.BACKSPACE:
                    if fkey and filters.get(fkey):
                        filters[fkey] = filters[fkey][:-1]
                        if not filters[fkey]:
                            del filters[fkey]
                        displayedPlans = refilter_fn()
                elif key == readchar.key.CTRL_U:
                    if fkey and fkey in filters:
                        del filters[fkey]
                        displayedPlans = refilter_fn()
                elif _printable(key) and fkey is not None:
                    filters[fkey] = filters.get(fkey, '') + key
                    displayedPlans = refilter_fn()
                continue

            # ---------------- COMMAND MODE ----------------
            if mode == 'command':
                if key == readchar.key.ESC:
                    command_buffer = ''
                    mode = 'nav'
                elif key in (readchar.key.ENTER, readchar.key.CR, readchar.key.LF):
                    line = command_buffer
                    command_buffer = ''
                    mode = 'nav'
                    if line.strip():
                        run_command(line)
                elif key == readchar.key.BACKSPACE:
                    command_buffer = command_buffer[:-1]
                elif key == readchar.key.CTRL_U:
                    command_buffer = ''
                elif _printable(key):
                    command_buffer += key
                continue

            # ---------------- NAV MODE ----------------
            # Numeric prefix buffer: digits accumulate until !/? consumes them.
            if key.isdigit():
                count_buffer += key
                continue
            if key in ('!', '?'):
                times = int(count_buffer) if count_buffer else 1
                count_buffer = ''
                if displayedPlans:
                    buy_many(displayedPlans[cursor], key == '!', times)
                continue
            # Any other keystroke cancels a pending multiplier.
            count_buffer = ''

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
                cursor = len(displayedPlans) - 1 if displayedPlans else 0
            elif key in ('q', readchar.key.ESC):
                break
            elif key == 'h':
                show_help = not show_help
            elif key == '/':
                if filterable():
                    filter_snapshot = dict(filters)
                    mode = 'filter'
            elif key == ':':
                command_buffer = ''
                mode = 'command'
            elif key == 'X':
                if filters:
                    filters.clear()
                    displayedPlans = refilter_fn()
            elif key == 'r' and refresh_fn is not None:
                do_fetch(refresh_fn)
            elif key == 'R' and reload_fn is not None:
                do_fetch(reload_fn)
            elif key == 'M' and refresh_fn is not None:
                state['months'] = {1: 12, 12: 24, 24: 1}.get(state.get('months', 1), 1)
                do_fetch(refresh_fn)
            elif key == 'T' and refresh_fn is not None:
                state['addVAT'] = not state.get('addVAT', False)
                do_fetch(refresh_fn)
            elif key == 'c':
                state['showCpu'] = not state['showCpu']
            elif key == 'f':
                state['showFqn'] = not state['showFqn']
            elif key == 'b':
                state['showBandwidth'] = not state['showBandwidth']
            elif key == 'u':
                state['showUnavailable'] = not state['showUnavailable']
                displayedPlans = refilter_fn()
            elif key == 'U':
                state['showUnknown'] = not state['showUnknown']
                displayedPlans = refilter_fn()
            elif key == '$':
                state['fakeBuy'] = not state['fakeBuy']
            elif key == 'Q' and refresh_fn is not None:
                state['quickLook'] = not state.get('quickLook', False)
                do_fetch(refresh_fn)
    finally:
        live.stop()
        cbreak_cm.__exit__(None, None, None)
        logger.info('Leaving interactive mode')
