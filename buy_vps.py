import argparse
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from rich.table import Table

import m.api
import m.bootstrap
from m.config import configFile, config_path
from m.print import console


def _parse_args():
    parser = argparse.ArgumentParser(
        prog='buy_vps',
        description='Browse and order OVH VPS plans (mock).')
    parser.add_argument('--conf', '-c', default='conf.yaml',
                        help='Path to the YAML config file (default: conf.yaml).')
    return parser.parse_args()


ARGS = _parse_args()

APIEndpoint   = configFile.get('APIEndpoint', 'ovh-eu')
ovhSubsidiary = configFile.get('ovhSubsidiary', 'FR')
fakeBuy       = configFile.get('fakeBuy', True)
addVAT        = configFile.get('addVAT', False)

m.bootstrap.setup_logging(configFile, 'buy_vps')
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.info(f"Loaded config from {config_path}")

m.bootstrap.login_if_credentials(configFile, APIEndpoint)


# --- Catalog ---------------------------------------------------------------

# OVH price values are integers in 1e-8 of the locale currency
# (e.g. 649000000 -> 6.49 EUR).
PRICE_DIVISOR = 100_000_000


def _price_for_mode(plan, mode):
    """Return the renew price (in locale currency, normalized to per-month)
    for the given pricing mode, or None when not orderable at that term.

    The catalog mixes interval semantics: some upfront12 rows quote a
    per-month discounted rate (interval=1), others quote a 12-month total
    (interval=12). Normalize so both columns are comparable per-month."""
    for p in plan.get('pricings', []):
        if p.get('mode') != mode or p.get('phase') != 1:
            continue
        if 'renew' not in (p.get('capacities') or []):
            continue
        price = p.get('price')
        if price is None:
            continue
        per_period = float(price) / PRICE_DIVISOR
        interval = p.get('interval') or 1
        if p.get('intervalUnit') == 'month' and interval > 1:
            return per_period / interval
        return per_period
    return None


def fetch_vps_catalog():
    url = m.api.api_url(APIEndpoint) + "order/catalog/public/vps?ovhSubsidiary=" + ovhSubsidiary
    logger.info("Fetching VPS catalog from " + url)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    try:
        vat_rate = 1 + data['locale']['taxRate'] / 100
    except (KeyError, TypeError):
        vat_rate = 1
    currency = (data.get('locale') or {}).get('currencyCode', '')
    plans = []
    for plan in data.get('plans', []):
        # Skip addons (extra IPs, snapshots, additional disks) — only show
        # buyable VPS plans, identified by the vps- planCode prefix.
        pc = plan.get('planCode', '')
        if not pc.startswith('vps-'):
            continue
        # Skip composite/bundled SKUs: any planCode that embeds a second
        # `vps-...` segment (e.g. `vps-elite-8-8-320-vps-2025-model1`) is a
        # base-plan + commercial-offer bundle. The cart enumerates them but
        # checkout returns "You are not allowed" — order the bare component
        # planCode (`vps-2025-modelN` or `vps-elite-...`) instead.
        if '-vps-' in pc:
            continue
        monthly = _price_for_mode(plan, 'default')
        yearly  = _price_for_mode(plan, 'upfront12')
        if monthly is None and yearly is None:
            continue
        if monthly is not None and addVAT:
            monthly *= vat_rate
        if yearly is not None and addVAT:
            yearly *= vat_rate
        plans.append({
            'planCode': plan.get('planCode', ''),
            'invoiceName': plan.get('invoiceName', ''),
            'monthly': monthly,
            'yearly': yearly,
            'currency': currency,
        })
    plans.sort(key=lambda p: (p['monthly'] if p['monthly'] is not None else 1e9,
                              p['planCode']))
    return plans


def fetch_one_availability(plan_code):
    """Per-plan availability via /vps/order/rule/datacenter. Returns
    {'linux': {dc: days}, 'windows': {dc: days}} where days=0 means
    in-stock and days>0 means preorder with that delivery delay. Or None
    on failure."""
    base = m.api.api_url(APIEndpoint)
    try:
        r = requests.get(base + 'vps/order/rule/datacenter',
                         params={'ovhSubsidiary': ovhSubsidiary, 'planCode': plan_code},
                         timeout=30)
        r.raise_for_status()
    except Exception:
        logger.exception("availability fetch failed for " + plan_code)
        return None
    out = {'linux': {}, 'windows': {}}
    for d in r.json().get('datacenters', []):
        days = d.get('daysBeforeDelivery') or 0
        for fam, key in (('linux', 'linuxStatus'), ('windows', 'windowsStatus')):
            st = d.get(key)
            if st == 'available':
                out[fam][d['datacenter']] = 0
            elif st == 'out-of-stock-preorder-allowed':
                out[fam][d['datacenter']] = days or 1
    return out


def fetch_availabilities(plan_codes, concurrency=10):
    """Bulk wrapper around fetch_one_availability with a thread pool."""
    out = {}
    total = len(plan_codes)
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(fetch_one_availability, pc): pc for pc in plan_codes}
        for i, f in enumerate(as_completed(futures), 1):
            out[futures[f]] = f.result()
            print(f'  availability {i}/{total}', end='\r', flush=True)
    print(' ' * 40, end='\r')
    return out


def _is_windows_os(os_name):
    return 'windows' in (os_name or '').lower()


def render_table(plans):
    table = Table(title=f"VPS plans ({ovhSubsidiary}{' incl. VAT' if addVAT else ''})")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("planCode", overflow="fold")
    table.add_column("name", overflow="fold")
    table.add_column("monthly", justify="right")
    table.add_column("yearly (per mo)", justify="right")
    table.add_column("yearly (12 mo)", justify="right")
    table.add_column("available")
    for i, p in enumerate(plans):
        m_str = f"{p['monthly']:.2f} {p['currency']}" if p['monthly'] is not None else "-"
        if p['yearly'] is not None:
            y_str = f"{p['yearly']:.2f} {p['currency']}"
            yt_str = f"{p['yearly'] * 12:.2f} {p['currency']}"
        else:
            y_str = yt_str = "-"
        avail = p.get('available_dcs')
        if avail is None:
            a_str = '[dim]?[/dim]'
        else:
            def _fmt(dc, days, suffix=''):
                tag = f"+{days}d" if days else ''
                return f"{dc}{tag}{suffix}"
            linux = avail.get('linux', {})
            windows = avail.get('windows', {})
            win_only = {dc: d for dc, d in windows.items() if dc not in linux}
            parts = []
            in_stock_lin = [_fmt(dc, 0) for dc, d in linux.items() if d == 0]
            preorder_lin = [_fmt(dc, d) for dc, d in linux.items() if d > 0]
            in_stock_win = [_fmt(dc, 0, '(W)') for dc, d in win_only.items() if d == 0]
            preorder_win = [_fmt(dc, d, '(W)') for dc, d in win_only.items() if d > 0]
            if in_stock_lin:
                parts.append('[green]' + ' '.join(in_stock_lin) + '[/green]')
            if in_stock_win:
                parts.append('[yellow]' + ' '.join(in_stock_win) + '[/yellow]')
            if preorder_lin or preorder_win:
                parts.append('[dim]' + ' '.join(preorder_lin + preorder_win) + '[/dim]')
            a_str = ' '.join(parts) if parts else '[red]out of stock[/red]'
        table.add_row(str(i), p['planCode'], p['invoiceName'], m_str, y_str, yt_str, a_str)
    console.print(table)


# --- Cart -------------------------------------------------------------------

# Single unauthenticated cart kept for the session, used only to enumerate
# orderable offers (mode/duration/price) per planCode without needing login.
_DISCOVERY_CART = None
DEFAULT_DC = 'GRA'
DEFAULT_OS = 'Debian 12'

# Canonical commitment duration per pricing mode. The cart endpoint's
# /vps?planCode= offers list reports a `duration` that is the *billing
# interval*, not the commitment — POSTing it back as-is is rejected for
# some plans (e.g. vps-2025-model1 upfront12 only accepts P1Y, not P1M).
# These are the durations the cart actually requires.
MODE_DURATION = {
    'default':        'P1M',
    'upfront6':       'P6M',
    'upfront12':      'P1Y',
    'upfront24':      'P2Y',
    'degressivity12': 'P1M',
    'degressivity24': 'P1M',
}

# How many months a single payment in this mode covers — used to compute
# the upfront total from the per-period price returned by the offer.
MODE_COMMIT_MONTHS = {
    'default': 1, 'upfront6': 6, 'upfront12': 12, 'upfront24': 24,
    'degressivity12': 1, 'degressivity24': 1,
}

DURATION_MONTHS = {'P1M': 1, 'P6M': 6, 'P1Y': 12, 'P2Y': 24}


def _get_discovery_cart():
    global _DISCOVERY_CART
    if _DISCOVERY_CART is None:
        url = m.api.api_url(APIEndpoint) + 'order/cart'
        r = requests.post(url, json={'ovhSubsidiary': ovhSubsidiary}, timeout=30)
        r.raise_for_status()
        _DISCOVERY_CART = r.json()['cartId']
        logger.info('Discovery cart: ' + _DISCOVERY_CART)
    return _DISCOVERY_CART


def discover_offers(plan_code):
    """Return {pricingMode: {price_per_month, currency, billing_interval_months}}
    for renew offers orderable for this planCode. The offers endpoint reports
    one price per mode; we normalize it to a per-month figure so upfront
    modes (P1Y interval) and monthly-billed modes (P1M interval) compare."""
    cid = _get_discovery_cart()
    url = m.api.api_url(APIEndpoint) + f'order/cart/{cid}/vps'
    r = requests.get(url, params={'planCode': plan_code}, timeout=30)
    r.raise_for_status()
    out = {}
    for offer in r.json():
        if offer.get('planCode') != plan_code:
            continue
        for p in offer.get('prices', []):
            if 'renew' not in (p.get('capacities') or []):
                continue
            mode = p.get('pricingMode')
            if mode in out:
                continue
            price = p.get('price') or {}
            value = price.get('value')
            if value is None:
                continue
            period = DURATION_MONTHS.get(p.get('duration'), 1)
            out[mode] = {
                'price_per_month': value / period,
                'currency': price.get('currencyCode', ''),
                'billing_period_months': period,
            }
    return out


def pick_offer(offers, term):
    """Map UI term ('m' monthly, 'y' yearly) to a (mode, offer). For yearly
    prefer upfront12 (single payment for 12 months) over degressivity12
    (12-month commit billed monthly)."""
    if term == 'm':
        return ('default', offers['default']) if 'default' in offers else (None, None)
    for mode in ('upfront12', 'degressivity12'):
        if mode in offers:
            return mode, offers[mode]
    return None, None


_REQUIRED_CONFIG_CACHE = {}


def discover_required_config(plan_code, mode, duration):
    """Return {label: [allowedValues]} for this plan, e.g. the list of valid
    vps_datacenter and vps_os values. Cached per planCode (the allowed
    values are intrinsic to the plan, not the pricing mode)."""
    if plan_code in _REQUIRED_CONFIG_CACHE:
        return _REQUIRED_CONFIG_CACHE[plan_code]
    base = m.api.api_url(APIEndpoint)
    cart = requests.post(base + 'order/cart',
                         json={'ovhSubsidiary': ovhSubsidiary},
                         timeout=30).json()
    cid = cart['cartId']
    item = requests.post(base + f'order/cart/{cid}/vps',
                         json={'planCode': plan_code, 'duration': duration,
                               'pricingMode': mode, 'quantity': 1},
                         timeout=30).json()
    item_id = item['itemId']
    rc = requests.get(base + f'order/cart/{cid}/item/{item_id}/requiredConfiguration',
                      timeout=30).json()
    out = {entry.get('label'): (entry.get('allowedValues') or []) for entry in rc}
    _REQUIRED_CONFIG_CACHE[plan_code] = out
    return out


def build_vps_cart(plan_code, mode, duration, dc, os_name, fake):
    """Create an assigned cart, add the VPS item, and configure the
    required vps_datacenter (+ optional vps_os). Returns cart_id, or 0 in
    fake mode."""
    if fake:
        print(f"[fake] would create cart: {plan_code} duration={duration} mode={mode} "
              f"dc={dc} os={os_name or '(none)'}")
        time.sleep(1)
        return 0
    if not m.api.is_logged_in():
        raise m.api.NotLoggedIn("Need to be logged in to build the cart.")
    client = m.api.client
    cart = client.post("/order/cart", ovhSubsidiary=ovhSubsidiary)
    cart_id = cart['cartId']
    logger.debug("Created cart " + cart_id)
    client.post(f"/order/cart/{cart_id}/assign")
    item = client.post(f"/order/cart/{cart_id}/vps",
                       duration=duration,
                       planCode=plan_code,
                       pricingMode=mode,
                       quantity=1)
    item_id = item['itemId']
    logger.debug(f"Added {plan_code} as item {item_id}")
    client.post(f"/order/cart/{cart_id}/item/{item_id}/configuration",
                label='vps_datacenter', value=dc)
    if os_name:
        client.post(f"/order/cart/{cart_id}/item/{item_id}/configuration",
                    label='vps_os', value=os_name)
    return cart_id


def checkout_vps_cart(cart_id, buy_now, fake):
    if fake:
        print(f"[fake] would checkout cart, autopay={buy_now}")
        time.sleep(1)
        return
    client = m.api.client
    client.post(f"/order/cart/{cart_id}/checkout",
                autoPayWithPreferredPaymentMethod=buy_now,
                waiveRetractationPeriod=buy_now)
    logger.info("Cart checkout successful")


def _prompt(label, default):
    try:
        ans = input(f"  {label} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return ans or default


def order(plan, intent, term):
    """intent: 'i' invoice (no autopay) or 'b' buy now (autopay).
    term:   'm' monthly or 'y' yearly."""
    label = ('invoice' if intent == 'i' else 'buy') + ' ' + \
            ('monthly' if term == 'm' else 'yearly')
    print(f"-> {label}: {plan['planCode']} ({plan['invoiceName']})")
    try:
        offers = discover_offers(plan['planCode'])
    except Exception as e:
        logger.exception("Offer discovery failed")
        print("Failed to discover offers:", e)
        return
    mode, offer = pick_offer(offers, term)
    if not offer:
        print(f"  no orderable {'yearly' if term == 'y' else 'monthly'} offer "
              f"for {plan['planCode']} (available modes: {sorted(offers) or 'none'})")
        return
    duration = MODE_DURATION.get(mode, 'P1M')
    commit_months = MODE_COMMIT_MONTHS.get(mode, 1)
    per_month = offer['price_per_month']
    cur = offer['currency']
    upfront = per_month * commit_months
    print(f"  offer: mode={mode} duration={duration} "
          f"{per_month:.2f} {cur}/mo, paid {upfront:.2f} {cur} for {commit_months} months")
    try:
        cfg = discover_required_config(plan['planCode'], mode, duration)
    except Exception as e:
        logger.exception("Required-config discovery failed")
        print("Failed to discover allowed values:", e)
        cfg = {}
    dc_choices = cfg.get('vps_datacenter') or []
    os_choices = cfg.get('vps_os') or []
    os_default = DEFAULT_OS if DEFAULT_OS in os_choices else (os_choices[0] if os_choices else DEFAULT_OS)
    if os_choices:
        print(f"  OS: {', '.join(os_choices)}")
    os_name = _prompt("OS (blank = none)", os_default)
    if os_name is None:
        return
    if os_name.lower() in ('none', ''):
        os_name = ''
    print("  refreshing availability...")
    fresh = fetch_one_availability(plan['planCode'])
    if fresh is not None:
        plan['available_dcs'] = fresh
    avail = plan.get('available_dcs') or {}
    fam = 'windows' if _is_windows_os(os_name) else 'linux'
    fam_avail = avail.get(fam) or {}
    in_stock = sorted([dc for dc, d in fam_avail.items() if d == 0])
    preorder = sorted([(dc, d) for dc, d in fam_avail.items() if d > 0], key=lambda x: x[1])
    if dc_choices:
        in_stock = [d for d in in_stock if d in dc_choices]
        preorder = [(dc, d) for dc, d in preorder if dc in dc_choices]
    if in_stock:
        print(f"  in stock for {fam}: {', '.join(in_stock)}")
        if preorder:
            print(f"  preorder ({fam}): {', '.join(f'{dc}+{d}d' for dc, d in preorder)}")
        dc_default = DEFAULT_DC if DEFAULT_DC in in_stock else in_stock[0]
    elif preorder:
        print(f"  [warning] no immediate stock for {fam}; preorder available: "
              f"{', '.join(f'{dc}+{d}d' for dc, d in preorder)}")
        dc_default = preorder[0][0]
    else:
        print(f"  [warning] no DC has {fam} stock right now; checkout will likely fail.")
        if dc_choices:
            print(f"  all DCs: {', '.join(dc_choices)}")
        dc_default = (DEFAULT_DC if DEFAULT_DC in dc_choices
                      else (dc_choices[0] if dc_choices else DEFAULT_DC))
    dc = _prompt("datacenter", dc_default)
    if dc is None:
        return
    buy_now = intent == 'b'
    try:
        cart_id = build_vps_cart(plan['planCode'], mode, duration,
                                 dc.upper(), os_name, fakeBuy)
        checkout_vps_cart(cart_id, buy_now, fakeBuy)
        print("Done." if fakeBuy else f"Done. cart={cart_id}")
    except Exception as e:
        logger.exception("Order failed")
        print("Failed:", e)


# --- REPL -------------------------------------------------------------------

HELP = ("Enter '<index> <i|b><m|y>' to order "
        "(i=invoice, b=buy now; m=monthly, y=yearly — e.g. 'iy' = invoice yearly), "
        "'l' to redisplay, 'q' to quit.")


def main():
    try:
        plans = fetch_vps_catalog()
    except Exception as e:
        sys.exit(f"Failed to fetch VPS catalog: {e}")
    if not plans:
        sys.exit("No VPS plans matched the filters.")
    try:
        pattern = input("Filter (regex on planCode/name, Enter for all): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if pattern:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            sys.exit(f"Invalid regex: {e}")
        plans = [p for p in plans if rx.search(p['planCode']) or rx.search(p['invoiceName'])]
        if not plans:
            sys.exit(f"No plans match {pattern!r}.")
    print(f"Fetching availability for {len({p['planCode'] for p in plans})} plans...")
    avails = fetch_availabilities(sorted({p['planCode'] for p in plans}))
    for p in plans:
        p['available_dcs'] = avails.get(p['planCode'])
    render_table(plans)
    print(HELP)
    if fakeBuy:
        print("(fakeBuy=True — nothing will be purchased)")
    while True:
        try:
            line = input("vps> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line in ('q', 'quit', 'exit'):
            return
        if line in ('l', 'list'):
            render_table(plans)
            continue
        if line in ('h', '?', 'help'):
            print(HELP)
            continue
        parts = line.split()
        if len(parts) != 2 or not parts[0].isdigit() or len(parts[1]) != 2 \
                or parts[1][0] not in ('i', 'b') or parts[1][1] not in ('m', 'y'):
            print("Unrecognized. " + HELP)
            continue
        idx = int(parts[0])
        if idx < 0 or idx >= len(plans):
            print(f"index {idx} out of range (0-{len(plans)-1})")
            continue
        order(plans[idx], parts[1][0], parts[1][1])


if __name__ == '__main__':
    main()
