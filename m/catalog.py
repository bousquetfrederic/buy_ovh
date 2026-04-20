import logging
import re
import requests

logger = logging.getLogger(__name__)

__all__ = ['build_list', 'fetch_catalog',
           'apply_column_filters', 'column_display_value',
           'COLUMN_KEYS', 'TEXT_COLUMNS', 'NUMERIC_COLUMNS']

# Canonical column identifiers used by the interactive filter bar. Kept in
# m.catalog so catalog-shaped logic (display formatting, filter semantics)
# lives next to the data that produces it.
TEXT_COLUMNS = ('planCode', 'model', 'cpu', 'datacenter',
                'memory', 'storage', 'bandwidth', 'vrack', 'fqn')
NUMERIC_COLUMNS = ('price', 'fee', 'total')
COLUMN_KEYS = TEXT_COLUMNS + NUMERIC_COLUMNS


def column_display_value(plan, key):
    """The string a column shows for this plan. Filters match this string
    rather than the raw code, so what the user sees is what they type against."""
    if key in ('planCode', 'model', 'cpu', 'datacenter', 'fqn'):
        return plan[key]
    if key == 'memory':
        return plan['memory'].split('-')[1]
    if key == 'storage':
        return '-'.join(x for x in plan['storage'].split('-')
                        if len(x) > 1 and x[1] == 'x')
    if key == 'bandwidth':
        return plan['bandwidth'].split('-')[1]
    if key == 'vrack':
        if plan['vrack'] == 'none':
            return 'none'
        return plan['vrack'].split('-')[2]
    if key == 'price':
        return f"{plan['price']:.2f}"
    if key == 'fee':
        return f"{plan['fee']:.2f}"
    if key == 'total':
        return f"{plan['price'] + plan['fee']:.2f}"
    return ''


_NUM_RE = re.compile(r'\s*(<=|>=|<|>|=)?\s*(-?\d+(?:\.\d+)?)\s*$')


def _match_text(pattern, value):
    try:
        return re.search(pattern, value, re.IGNORECASE) is not None
    except re.error:
        return False


def _match_numeric(pattern, value):
    m = _NUM_RE.match(pattern)
    if not m:
        return False
    op = m.group(1) or '<='
    n = float(m.group(2))
    if op == '<=': return value <= n
    if op == '>=': return value >= n
    if op == '<':  return value < n
    if op == '>':  return value > n
    return value == n


def apply_column_filters(plans, filters):
    """Return plans whose displayed column values satisfy `filters`.

    filters: dict {column_key: pattern_string}. Empty or missing patterns
    are skipped. Text columns use case-insensitive regex; numeric columns
    accept <, >, <=, >=, = (bare number means <=)."""
    if not filters or not any(filters.values()):
        return list(plans)
    out = []
    for p in plans:
        ok = True
        for key in TEXT_COLUMNS:
            pat = filters.get(key, '')
            if pat and not _match_text(pat, column_display_value(p, key)):
                ok = False
                break
        if not ok:
            continue
        for key, value in (('price', p['price']),
                           ('fee', p['fee']),
                           ('total', p['price'] + p['fee'])):
            pat = filters.get(key, '')
            if pat and not _match_numeric(pat, value):
                ok = False
                break
        if ok:
            out.append(p)
    return out

# -------------- PRICING ----------------------------------------------------

# OVH quotes prices in 1e-8 of the locale currency (e.g. 1_000_000_000 → 10.00 EUR).
_PRICE_SCALE = 100_000_000


def _apply_promo(entry):
    """Convert an OVH `pricings` row to a currency float, applying any
    percentage promo attached to the row. Non-percentage promos are
    ignored (buy_ovh never implemented those)."""
    base = float(entry['price']) / _PRICE_SCALE
    promos = entry.get('promotions') or []
    pct = next((p for p in promos if p.get('type') == 'percentage'), None)
    if pct is None:
        return base
    return base * (100 - float(pct['value'])) / 100


def _find_pricing(plan, *, mode, phase, capacity):
    """Return the first `pricings` row matching (mode, phase, capacity)
    with strategy=tiered, or None if no such row exists. Malformed rows
    — missing keys, wrong types — are treated as absent rather than
    crashing the whole catalog parse."""
    for entry in plan.get('pricings') or []:
        try:
            if (entry['phase'] == phase
                    and entry['capacities'][0] == capacity
                    and entry['strategy'] == 'tiered'
                    and entry['mode'] == mode):
                return entry
        except (KeyError, IndexError, TypeError):
            continue
    return None


def plan_price(plan, mode):
    """Return the monthly/term price for `plan` in `mode`, or None if the
    plan has no offer at that commitment. Callers use None to drop plans
    from the list rather than fake a price."""
    entry = _find_pricing(plan, mode=mode, phase=1, capacity='renew')
    return _apply_promo(entry) if entry is not None else None


def plan_fee(plan, mode):
    """Return the installation fee for `plan` in `mode`, or 0.0 when no
    fee row exists. (Unlike price, a missing fee is not a reason to drop
    the plan — plenty of plans ship with no installation charge.)"""
    entry = _find_pricing(plan, mode=mode, phase=0, capacity='installation')
    return _apply_promo(entry) if entry is not None else 0.0


def addon_price_with_fallback(addon, mode, months):
    """Return the addon's price in `mode`, falling back to default×months
    when `mode` is absent but the plan quotes a monthly default.

    Distinguishes two flavors of 0:
     - a bundled addon whose default quote is 0.0 (free memory tier, etc.)
       stays 0.0, because default is found and multiplied;
     - an addon that doesn't list any renew pricing at all returns 0.0
       because there's nothing to charge.
    """
    entry = _find_pricing(addon, mode=mode, phase=1, capacity='renew')
    if entry is not None:
        return _apply_promo(entry)
    if mode == 'default':
        return 0.0
    default_entry = _find_pricing(addon, mode='default', phase=1, capacity='renew')
    if default_entry is None:
        return 0.0
    return _apply_promo(default_entry) * months

# -------------- CATALOG PARSING -----------------------------------------------

def fetch_catalog(url, ovhSubsidiary):
    """Fetch the eco (dedicated-server) catalog for the given subsidiary.
    Thin wrapper around requests.get so tests can patch one seam."""
    response = requests.get(
        url + "order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    return response.json()


def _pricing_mode(months):
    if months == 12:
        return 'upfront12'
    if months == 24:
        return 'upfront24'
    return 'default'


def _addons_by_code(catalog):
    """Map planCode → addon dict (minus planCode itself, which becomes the key)."""
    return {addon['planCode']: {k: v for k, v in addon.items() if k != 'planCode'}
            for addon in catalog['addons']}


def _vat_rate(catalog, addVAT):
    """Return (1 + taxRate/100) from the catalog's locale, or 1 when
    the catalog doesn't expose a tax rate. The warning is printed only
    when the user actually asked for VAT — silent otherwise."""
    try:
        return 1 + catalog['locale']['taxRate'] / 100
    except (KeyError, TypeError):
        logger.exception("Could not read VAT from the catalog")
        if addVAT:
            print("Could not read VAT from the catalog")
        return 1


def _parse_invoice_name(invoice_name):
    """'MODEL |CPU ' (OVH's format) → (model, cpu). Missing cpu segment
    yields ('MODEL', 'unknown')."""
    parts = invoice_name.split('|')
    if len(parts) > 1:
        # trim the trailing space baked into OVH's model column
        return parts[0][:-1], parts[1][1:]
    return parts[0], 'unknown'


def _addon_families(plan):
    """Extract the four mandatory addon lists. Missing families return
    empty lists; a missing vrack family is later coerced to ['none']."""
    out = {'storage': [], 'memory': [], 'bandwidth': [], 'vrack': []}
    for family in plan.get('addonFamilies') or []:
        if family['name'] in out:
            out[family['name']] = family['addons']
    return out


def _datacenters_for_plan(plan, acceptable_dc):
    """Plan's DCs restricted to the user's acceptable_dc list and
    sorted to match its order. When acceptable_dc is empty, return the
    plan's list unchanged."""
    dcs = []
    for config in plan.get('configurations') or []:
        if config['name'] == 'dedicated_datacenter':
            dcs = config['values']
            break
    if not acceptable_dc:
        return dcs
    filtered = [x for x in dcs if x in acceptable_dc]
    return sorted(filtered, key=acceptable_dc.index)

# -------------- CROSS-PRODUCT EXPANSION --------------------------------------

def _expand_plan(plan, addons, mode, months,
                 acceptable_dc, filterName, filterDisk, filterMemory,
                 maxPrice, addVAT, vat_rate,
                 bandwidthAndVRack, avail):
    """Turn one OVH plan into the full list of {plan}×{dc}×{mem}×{storage}×
    {bw}×{vrack} variants that pass all the filters. Returns []  when the
    plan has no offer at this commitment or no combination survives the
    filters."""
    planCode = plan['planCode']
    model, cpu = _parse_invoice_name(plan['invoiceName'])

    # Name filter: match either invoice model or plan code.
    if not (re.search(filterName, model) or re.search(filterName, planCode)):
        return []

    price = plan_price(plan, mode)
    # Plans without an offer at this commitment are dropped rather than
    # priced at 0 — the cart API would reject them anyway.
    if price is None:
        return []
    fee = plan_fee(plan, mode)

    families = _addon_families(plan)
    memories = families['memory']
    storages = families['storage']
    bandwidths = families['bandwidth']
    vracks = families['vrack'] or ['none']
    dcs = _datacenters_for_plan(plan, acceptable_dc)

    out = []
    for da in dcs:
        for me in memories:
            memory_addon = addons[me]
            if not re.search(filterMemory, memory_addon['product']):
                continue
            mem_price = addon_price_with_fallback(memory_addon, mode, months)
            mem_fee = plan_fee(memory_addon, mode)
            for st in storages:
                storage_addon = addons[st]
                if not re.search(filterDisk, storage_addon['product']):
                    continue
                st_price = addon_price_with_fallback(storage_addon, mode, months)
                st_fee = plan_fee(storage_addon, mode)
                for ba in bandwidths:
                    bw_price = addon_price_with_fallback(addons[ba], mode, months)
                    # Paid bandwidth is dropped when the flag is off; bundled
                    # (price==0) bandwidth always passes.
                    if not bandwidthAndVRack and bw_price > 0.0:
                        continue
                    for vr in vracks:
                        vr_price = 0.0
                        if vr != 'none':
                            vr_price = addon_price_with_fallback(addons[vr], mode, months)
                            if not bandwidthAndVRack and vr_price > 0.0:
                                continue

                        total_price = price + mem_price + st_price + bw_price + vr_price
                        total_fee = fee + mem_fee + st_fee
                        if addVAT:
                            total_price = round(total_price * vat_rate, 2)
                            total_fee = round(total_fee * vat_rate, 2)

                        # maxPrice is per-month; scale to the current term.
                        if maxPrice > 0 and total_price > maxPrice * months:
                            continue

                        fqn = f"{planCode}.{memory_addon['product']}.{storage_addon['product']}.{da}"
                        out.append({
                            'planCode': planCode,
                            'model': model,
                            'cpu': cpu,
                            'datacenter': da,
                            'storage': st,
                            'memory': me,
                            'bandwidth': ba,
                            'vrack': vr,
                            'fqn': fqn,
                            'price': total_price,
                            'fee': total_fee,
                            'availability': avail.get(fqn, 'unknown'),
                        })
    return out


def build_list(url,
               avail, ovhSubsidiary,
               filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
               addVAT, months,
               bandwidthAndVRack):
    """Top-level: fetch OVH's catalog, expand every plan into its
    {dc×mem×storage×bw×vrack} variants, apply the user's filters, and
    return the resulting list sorted by planCode.

    Public signature kept stable — `buy_ovh.py` and `monitor_ovh.py` both
    call this with positional args."""
    logger.debug("Building Server list")
    catalog = fetch_catalog(url, ovhSubsidiary)
    mode = _pricing_mode(months)
    addons = _addons_by_code(catalog)
    vat_rate = _vat_rate(catalog, addVAT)
    logger.debug("VAT Rate=" + str(vat_rate))

    plans_out = []
    for plan in catalog['plans']:
        plans_out.extend(_expand_plan(
            plan, addons, mode, months,
            acceptable_dc, filterName, filterDisk, filterMemory,
            maxPrice, addVAT, vat_rate,
            bandwidthAndVRack, avail))
    return sorted(plans_out, key=lambda x: x['planCode'])
