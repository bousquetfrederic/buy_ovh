import time
from datetime import datetime

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import m.availability

__all__ = ['whichColor', 'print_plan_list', 'print_prompt', 'print_and_sleep',
           'print_orders', 'print_servers', 'print_help_legend',
           'clear_screen', 'console']

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

def clear_screen():
    console.clear()


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


# ----------------- PRINT LIST OF SERVERS -----------------------------------------------------
def print_plan_list(plans, showCpu, showFqn, showBandwidth,
                    showPrice, showFee, showTotalPrice):
    if not plans:
        console.print(Panel(Text('No availability.', style='bold red'),
                            border_style='red', box=box.ROUNDED, expand=False))
        return

    table = Table(box=box.SIMPLE_HEAVY,
                  header_style='bold white on grey15',
                  row_styles=['', 'on grey7'],
                  pad_edge=False, expand=False, show_edge=False)
    table.add_column('#', justify='right', no_wrap=True)
    if showFqn:
        table.add_column('FQN', no_wrap=True)
    else:
        table.add_column('Plan', no_wrap=True)
        table.add_column('Model', no_wrap=True)
        if showCpu:
            table.add_column('CPU', no_wrap=True)
        table.add_column('DC', justify='center', no_wrap=True)
        table.add_column('Mem', justify='right', no_wrap=True)
        table.add_column('Storage', no_wrap=True)
    if showBandwidth:
        table.add_column('BW', justify='right', no_wrap=True)
        table.add_column('vRack', justify='right', no_wrap=True)
    if showPrice:
        table.add_column('€/mo', justify='right', no_wrap=True)
    if showFee:
        table.add_column('Fee', justify='right', no_wrap=True)
    if showTotalPrice:
        table.add_column('Total', justify='right', no_wrap=True)

    for idx, plan in enumerate(plans):
        if plan['vrack'] == 'none':
            vrack = 'none'
        else:
            vrack = plan['vrack'].split('-')[2]
        storage = '-'.join(x for x in plan['storage'].split('-')
                           if len(x) > 1 and x[1] == 'x')
        memory = plan['memory'].split('-')[1]
        bandwidth = plan['bandwidth'].split('-')[1]
        state = _resolve_state(plan)
        style = whichColor[state]

        row = [str(idx)]
        if showFqn:
            row.append(plan['fqn'])
        else:
            row.append(plan['planCode'])
            row.append(plan['model'])
            if showCpu:
                row.append(plan['cpu'])
            row.append(plan['datacenter'])
            row.append(memory)
            row.append(storage)
        if showBandwidth:
            row.append(bandwidth)
            row.append(vrack)
        if showPrice:
            row.append(f"{plan['price']:.2f}")
        if showFee:
            row.append(f"{plan['fee']:.2f}")
        if showTotalPrice:
            row.append(f"{plan['fee'] + plan['price']:.2f}")

        table.add_row(*row, style=style)

    console.print(table)


# ----------------- PRINT PROMPT (top-style header) --------------------------------------------
def print_prompt(acceptable_dc, filterMemory, filterName, filterDisk,
                 maxPrice, coupon, months,
                 fakeBuy=False, loggedIn=True, loop=False):
    dcs = ' '.join(acceptable_dc) if acceptable_dc else '—'
    filt = ' / '.join(x for x in [filterName, filterDisk, filterMemory] if x) or '—'

    line1 = Text.from_markup(
        f"[bold]DCs[/]: {dcs}    [bold]Filter[/]: {filt}"
    )
    extras = []
    if maxPrice > 0:
        extras.append(f"[bold]Max[/]: €{maxPrice}")
    if coupon:
        extras.append(f"[bold]Coupon[/]: {coupon}")
    if months > 1:
        extras.append(f"[bold]Term[/]: {months}M")
    line2 = Text.from_markup('    '.join(extras)) if extras else None

    flags = []
    flags.append(Text(' LOOP ', style='black on green') if loop
                 else Text(' IDLE ', style='black on grey50'))
    flags.append(Text(' LOGGED IN ', style='black on bright_blue') if loggedIn
                 else Text(' OFFLINE ', style='white on red'))
    if fakeBuy:
        flags.append(Text(' FAKE BUY ', style='black on yellow'))
    flag_line = Text('  ').join(flags)

    body = Group(line1, line2, flag_line) if line2 else Group(line1, flag_line)

    title = Text.assemble(
        ('  BUY_OVH  ', 'bold white on dark_cyan'),
        ('   ', ''),
        (datetime.now().strftime('%H:%M:%S'), 'bright_black'),
    )
    console.print(Panel(body, title=title, title_align='left',
                        border_style='bright_black', box=box.ROUNDED,
                        padding=(0, 1)))


# ----------------- SLEEP x SECONDS ------------------------------------------------------------
def print_and_sleep(showMessage, sleepsecs):
    if not showMessage:
        time.sleep(sleepsecs)
        return
    bar_width = 30
    try:
        for i in range(sleepsecs, 0, -1):
            filled = int(bar_width * (sleepsecs - i) / max(sleepsecs, 1))
            bar = '█' * filled + '░' * (bar_width - filled)
            console.print(
                f'[dim]⟲[/] [cyan]{bar}[/] [bold cyan]{i:>3}s[/] '
                f'[dim](CTRL-C to stop and buy/quit)[/]',
                end='\r', soft_wrap=True, highlight=False)
            time.sleep(1)
    finally:
        # wipe the line so subsequent output starts clean
        console.print(' ' * (bar_width + 60), end='\r', highlight=False)


# ----------------- PRINT LIST OF ORDERS -------------------------------------------------------
def print_orders(orderList, printDate=False):
    if not orderList:
        console.print('[dim]No orders.[/]')
        return
    table = Table(box=box.SIMPLE_HEAVY, header_style='bold white on grey15')
    table.add_column('#', justify='right', no_wrap=True)
    table.add_column('Description', no_wrap=True)
    table.add_column('Location', no_wrap=True)
    if printDate:
        table.add_column('Expires', no_wrap=True)
    for idx, order in enumerate(orderList):
        row = [str(idx), order['description'], order['location']]
        if printDate:
            row.append(order['date'])
        table.add_row(*row)
    console.print(table)


# ------------------ PRINT SERVER SPECS --------------------------------------------------------
def print_servers(server_list):
    if not server_list:
        console.print('[dim]No servers.[/]')
        return
    table = Table(box=box.SIMPLE_HEAVY, header_style='bold white on grey15',
                  show_lines=True)
    table.add_column('Name', style='bold')
    table.add_column('DC', justify='center')
    table.add_column('CPU')
    table.add_column('RAM', justify='right')
    table.add_column('Disks')
    for s in server_list:
        table.add_row(s['name'], s['datacenter'], s['cpu'], s['memory'],
                      '\n'.join(s['disks']))
    console.print(table)


# ------------------ HELP-SCREEN COLOUR LEGEND -------------------------------------------------
def print_help_legend():
    legend = [
        ('high',        'Available HIGH'),
        ('low',         'Available LOW'),
        ('unavailable', 'Unavailable'),
        ('comingSoon',  'Coming Soon'),
        ('unknown',     'Availability unknown'),
        ('autobuy',     'Auto-buy candidate'),
    ]
    for state, label in legend:
        console.print(Text(label, style=whichColor[state]))
