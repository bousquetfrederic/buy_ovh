import logging
import webbrowser
from datetime import datetime, timedelta

import readchar
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import m.api
from m.print import console

__all__ = ['run']

logger = logging.getLogger(__name__)


MAIN_HELP_LINES = [
    ('↑/↓  j/k', 'move cursor'),
    ('Enter',    'open selection'),
    ('h',        'toggle this help'),
    ('q  Esc',   'quit'),
]

SUB_HELP_LINES = [
    ('↑/↓  j/k', 'move cursor'),
    ('PgUp/PgDn', 'page up / down'),
    ('g / G',    'top / bottom'),
    ('r',        'refresh'),
    ('o / Enter', 'open URL in browser (orders)'),
    ('h',        'toggle this help'),
    ('q  Esc',   'back to main menu'),
]


def _help_overlay(lines, title='Keys'):
    body = [Text.from_markup(f'[bold cyan]{k:<12}[/] {v}') for k, v in lines]
    return Panel(Group(*body), title=title, title_align='left',
                 border_style='cyan', box=box.ROUNDED)


def _format_age(fetched_at):
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


def _footer(label, fetched_at=None):
    age = _format_age(fetched_at)
    left = f'[bright_black]{label}[/]'
    right = f'[bright_black]fetched {age}[/]' if age else ''
    line = left + ('    ' + right if right else '')
    return Panel(Text.from_markup(line),
                 border_style='bright_black', box=box.ROUNDED, padding=(0, 1))


# ------------------ MAIN MENU ------------------

MENU_ITEMS = [
    ('servers',      'Servers'),
    ('unpaid',       'Unpaid orders'),
    ('undelivered',  'Undelivered orders'),
    ('quit',         'Quit'),
]


def _render_menu(cursor, show_help):
    table = Table(box=box.SIMPLE_HEAVY, pad_edge=False, expand=False,
                  show_edge=False, show_header=False)
    table.add_column('label')
    for i, (_, label) in enumerate(MENU_ITEMS):
        style = 'bold white on grey23' if i == cursor else ''
        table.add_row(label, style=style)
    renderables = [Panel(table, title='manage_ovh', title_align='left',
                         border_style='bright_black', box=box.ROUNDED,
                         padding=(0, 1)),
                   _footer('↑↓ move   ↵ open   h help   q quit')]
    if show_help:
        renderables.append(_help_overlay(MAIN_HELP_LINES))
    return Group(*renderables)


def _main_menu():
    cursor = 0
    show_help = False
    while True:
        console.clear()
        console.print(_render_menu(cursor, show_help))

        try:
            key = readchar.readkey()
        except KeyboardInterrupt:
            return 'quit'

        if key in (readchar.key.UP, 'k'):
            cursor = (cursor - 1) % len(MENU_ITEMS)
        elif key in (readchar.key.DOWN, 'j'):
            cursor = (cursor + 1) % len(MENU_ITEMS)
        elif key in ('q', readchar.key.ESC):
            return 'quit'
        elif key == 'h':
            show_help = not show_help
        elif key in (readchar.key.ENTER, '\r', '\n'):
            return MENU_ITEMS[cursor][0]


# ------------------ ORDERS VIEW ------------------

def _fetch_orders(status_list, days_back):
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    since = today - timedelta(days=days_back)
    try:
        return m.api.get_orders_per_status(since, tomorrow, status_list, False)
    except KeyboardInterrupt:
        return []


def _orders_table(orders, cursor, scroll_top, window):
    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False)
    table.add_column('#', justify='right', no_wrap=True)
    table.add_column('Description', no_wrap=True)
    table.add_column('Location', no_wrap=True)
    table.add_column('Expires', no_wrap=True)
    end = min(scroll_top + window, len(orders))
    for i in range(scroll_top, end):
        o = orders[i]
        style = 'reverse' if i == cursor else ''
        table.add_row(str(i), o['description'], o['location'], o['date'],
                      style=style)
    return table


def _orders_view(title, status_list, days_back):
    console.clear()
    console.print(f'[dim]Fetching {title.lower()}…[/]')
    orders = _fetch_orders(status_list, days_back)
    fetched_at = datetime.now()

    cursor = 0
    scroll_top = 0
    show_help = False

    while True:
        size = console.size
        reserved = 7 + (len(SUB_HELP_LINES) + 2 if show_help else 0)
        window = max(3, size.height - reserved)

        if not orders:
            body = Panel(Text('No orders.', style='dim'),
                         border_style='bright_black', box=box.ROUNDED,
                         title=title, title_align='left')
            renderables = [body, _footer('r refresh   h help   q back',
                                          fetched_at)]
            if show_help:
                renderables.append(_help_overlay(SUB_HELP_LINES))
            console.clear()
            console.print(Group(*renderables))
        else:
            if cursor >= len(orders):
                cursor = len(orders) - 1
            if cursor < 0:
                cursor = 0
            if cursor < scroll_top:
                scroll_top = cursor
            elif cursor >= scroll_top + window:
                scroll_top = cursor - window + 1
            scroll_top = max(0, min(scroll_top,
                                    max(0, len(orders) - window)))

            table = _orders_table(orders, cursor, scroll_top, window)
            url_line = Text.from_markup(
                f'[bright_black]URL[/]  {orders[cursor]["url"]}')
            pos = Text.from_markup(
                f'[bright_black]{cursor + 1}/{len(orders)}[/]')
            footer = _footer('↑↓ move   ↵/o open URL   r refresh   '
                             'h help   q back', fetched_at)
            renderables = [
                Panel(table, title=title, title_align='left',
                      border_style='bright_black', box=box.ROUNDED,
                      padding=(0, 0)),
                url_line, pos, footer,
            ]
            if show_help:
                renderables.append(_help_overlay(SUB_HELP_LINES))
            console.clear()
            console.print(Group(*renderables))

        try:
            key = readchar.readkey()
        except KeyboardInterrupt:
            return

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
            cursor = len(orders) - 1 if orders else 0
        elif key in ('q', readchar.key.ESC):
            return
        elif key == 'h':
            show_help = not show_help
        elif key == 'r':
            console.clear()
            console.print(f'[dim]Refreshing {title.lower()}…[/]')
            orders = _fetch_orders(status_list, days_back)
            fetched_at = datetime.now()
            cursor = min(cursor, max(0, len(orders) - 1))
        elif orders and key in ('o', readchar.key.ENTER, '\r', '\n'):
            webbrowser.open(orders[cursor]['url'])


# ------------------ SERVERS VIEW ------------------

def _fetch_servers():
    try:
        return m.api.get_servers_list(False)
    except KeyboardInterrupt:
        return []


def _servers_table(servers, cursor, scroll_top, window):
    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  pad_edge=False, expand=False, show_edge=False,
                  show_lines=True)
    table.add_column('#', justify='right', no_wrap=True)
    table.add_column('Name', style='bold', no_wrap=True)
    table.add_column('DC', justify='center', no_wrap=True)
    table.add_column('CPU', no_wrap=True)
    table.add_column('RAM', justify='right', no_wrap=True)
    table.add_column('Disks')
    end = min(scroll_top + window, len(servers))
    for i in range(scroll_top, end):
        s = servers[i]
        style = 'reverse' if i == cursor else ''
        table.add_row(str(i), s['name'], s['datacenter'], s['cpu'],
                      s['memory'], '\n'.join(s['disks']), style=style)
    return table


def _servers_view():
    console.clear()
    console.print('[dim]Fetching servers…[/]')
    servers = _fetch_servers()
    fetched_at = datetime.now()

    cursor = 0
    scroll_top = 0
    show_help = False

    while True:
        size = console.size
        reserved = 7 + (len(SUB_HELP_LINES) + 2 if show_help else 0)
        # each server row is 2 lines because of show_lines=True
        window = max(2, (size.height - reserved) // 2)

        if not servers:
            body = Panel(Text('No servers.', style='dim'),
                         border_style='bright_black', box=box.ROUNDED,
                         title='Servers', title_align='left')
            renderables = [body, _footer('r refresh   h help   q back',
                                          fetched_at)]
            if show_help:
                renderables.append(_help_overlay(SUB_HELP_LINES))
            console.clear()
            console.print(Group(*renderables))
        else:
            if cursor >= len(servers):
                cursor = len(servers) - 1
            if cursor < 0:
                cursor = 0
            if cursor < scroll_top:
                scroll_top = cursor
            elif cursor >= scroll_top + window:
                scroll_top = cursor - window + 1
            scroll_top = max(0, min(scroll_top,
                                    max(0, len(servers) - window)))

            table = _servers_table(servers, cursor, scroll_top, window)
            pos = Text.from_markup(
                f'[bright_black]{cursor + 1}/{len(servers)}[/]')
            footer = _footer('↑↓ move   r refresh   h help   q back',
                              fetched_at)
            renderables = [
                Panel(table, title='Servers', title_align='left',
                      border_style='bright_black', box=box.ROUNDED,
                      padding=(0, 0)),
                pos, footer,
            ]
            if show_help:
                renderables.append(_help_overlay(SUB_HELP_LINES))
            console.clear()
            console.print(Group(*renderables))

        try:
            key = readchar.readkey()
        except KeyboardInterrupt:
            return

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
            cursor = len(servers) - 1 if servers else 0
        elif key in ('q', readchar.key.ESC):
            return
        elif key == 'h':
            show_help = not show_help
        elif key == 'r':
            console.clear()
            console.print('[dim]Refreshing servers…[/]')
            servers = _fetch_servers()
            fetched_at = datetime.now()
            cursor = min(cursor, max(0, len(servers) - 1))


# ------------------ ENTRY ------------------

def run():
    logger.info('Entering manage UI')
    with console.screen():
        try:
            while True:
                choice = _main_menu()
                if choice == 'quit':
                    return
                if choice == 'servers':
                    _servers_view()
                elif choice == 'unpaid':
                    _orders_view('Unpaid orders', ['notPaid'], days_back=14)
                elif choice == 'undelivered':
                    _orders_view('Undelivered orders', ['delivering'],
                                 days_back=30)
        finally:
            logger.info('Leaving manage UI')
