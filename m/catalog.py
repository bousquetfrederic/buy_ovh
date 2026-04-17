import logging
import re
import requests

logger = logging.getLogger(__name__)

__all__ = ['build_list', 'apply_column_filters', 'column_display_value',
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

# -------------- EXTRACT THE PRICE AND FEES INCLUDING PROMOTION ----------------------------------------------------
def getPriceValue(price):
    myPrice = float(price['price'])/100000000
    allPromo = price['promotions']
    if allPromo:
        allPercentPromo = [x for x in allPromo if x['type']=='percentage']
        # take only the first one
        if allPercentPromo:
            myPromo = float(100-allPercentPromo[0]['value'])/100
        else:
            myPromo = 1
    else:
        myPromo = 1
    return myPrice * myPromo

def getPlanPrice(plan, mode):
    try:
        allPlanPrices = [x for x in plan['pricings']
                         if x['phase'] == 1
                         and x['capacities'][0] == 'renew'
                         and x['strategy'] == 'tiered'
                         and x['mode'] == mode]
        return getPriceValue(allPlanPrices[0])
    except (KeyError, IndexError, TypeError):
        return 0

def getPlanFee(plan, mode):
    try:
        allPlanFees = [x for x in plan['pricings']
                       if x['phase'] == 0
                       and x['capacities'][0] == 'installation'
                       and x['strategy'] == 'tiered'
                       and x['mode']  == mode]
        return getPriceValue(allPlanFees[0])
    except (KeyError, IndexError, TypeError):
        return 0


def priceWithFallback(plan, mode, months):
    # Addon-only fallback: when the plan supports the requested commitment
    # but an addon doesn't list that mode, estimate the cost as default
    # × months. Bundled addons have default=0 so this is a no-op for them.
    # The plan itself is handled separately (plans without the mode are
    # dropped, not faked).
    price = getPlanPrice(plan, mode)
    if price == 0 and mode != 'default':
        default_price = getPlanPrice(plan, 'default')
        if default_price > 0:
            return default_price * months
    return price

# -------------- BUILD LIST OF SERVERS ---------------------------------------------------------------------------
def build_list(url,
               avail, ovhSubsidiary,
               filterName, filterDisk, filterMemory, acceptable_dc, maxPrice,
               addVAT, months,
               bandwidthAndVRack):
    logger.debug("Building Server list")
    response = requests.get(url + "order/catalog/public/eco?ovhSubsidiary=" + ovhSubsidiary)
    API_catalog = response.json()

    allPlans = API_catalog['plans']
    myPlans = []

    if months == 12:
        pricingMode = 'upfront12'
    elif months == 24:
        pricingMode = 'upfront24'
    else:
        pricingMode = 'default'

    allAddonsDict = {}
    for addon in API_catalog['addons']:
        planCode = addon["planCode"]
        allAddonsDict[planCode] = {k: v for k, v in addon.items() if k != "planCode"}

    try:
        vatRate = 1 + (API_catalog['locale']['taxRate']) / 100
    except (KeyError, TypeError):
        logger.exception("Could not read VAT from the catalog")
        if addVAT:
            print("Could not read VAT from the catalog")
        vatRate = 1
    logger.debug("VAT Rate=" + str(vatRate))

    for plan in allPlans:
        planCode = plan['planCode']
        invoiceNameSplit = plan['invoiceName'].split('|')
        model = invoiceNameSplit[0]
        if len(invoiceNameSplit) > 1:
            cpu = invoiceNameSplit[1][1:]
            # remove extra space at the end of the model name
            model = model[:-1]
        else:
            cpu = "unknown"
        # only consider plans passing the name filter, which is a regular expression
        # Either model (from invoice name) of plan code must match
        if not (bool(re.search(filterName, model))
                or bool(re.search(filterName, plan['planCode']))):
            continue

        # find the price and fee
        planFee = getPlanFee(plan, pricingMode)
        planPrice = getPlanPrice(plan, pricingMode)
        # If the plan has no entry for the requested commitment (e.g. some
        # 2026 KS plans ship without upfront24), it can't be bought at that
        # term — drop it from the list rather than fake a price.
        if planPrice == 0 and pricingMode != 'default':
            continue

        allStorages = []
        allMemories = []
        allBandwidths = []
        allVRack = []

        # find mandatory addons
        for family in plan['addonFamilies']:
            if family['name'] == "storage":
                allStorages = family['addons']
            elif family['name'] == "memory":
                allMemories = family['addons']
            elif family['name'] == "bandwidth":
                allBandwidths = family['addons']
            elif family['name'] == "vrack":
                allVRack = family['addons']

        # vRack is not always present
        if not allVRack:
            allVRack = ['none']

        allDatacenters = []

        # same for datacenters
        for config in plan['configurations']:
            if config['name'] == "dedicated_datacenter":
                allDatacenters = config['values']
                # filter and sort datacenters per acceptable_dc
                if acceptable_dc:
                    filteredDatacenters = [x for x in allDatacenters if x in acceptable_dc]
                    sortedDatacenters = sorted(filteredDatacenters, key=lambda x: acceptable_dc.index(x))
                else:
                    sortedDatacenters = allDatacenters

        # build a list of all possible combinations
        for da in sortedDatacenters:
            for me in allMemories:
                memoryPlan = allAddonsDict[me]
                # apply the memory filter
                if not bool(re.search(filterMemory,memoryPlan['product'])):
                    continue
                memoryFee = getPlanFee(memoryPlan, pricingMode)
                memoryPrice = priceWithFallback(memoryPlan, pricingMode, months)
                for st in allStorages:
                    storagePlan = allAddonsDict[st]
                    # apply the disk filter
                    if not bool(re.search(filterDisk,storagePlan['product'])):
                        continue
                    storageFee = getPlanFee(storagePlan, pricingMode)
                    storagePrice = priceWithFallback(storagePlan, pricingMode, months)
                    for ba in allBandwidths:
                        bandwidthPlan = allAddonsDict[ba]
                        bandwidthPrice = priceWithFallback(bandwidthPlan, pricingMode, months)
                        for vr in allVRack:
                            thisPrice = planPrice + memoryPrice + storagePrice
                            thisFee = planFee + memoryFee + storageFee
                            # if showBandwidth is false, drop the plans with a bandwidth that costs money
                            if not bandwidthAndVRack and bandwidthPrice > 0.0:
                                continue
                            thisPrice = thisPrice + bandwidthPrice
                            if vr != 'none':
                                vRackPlan = allAddonsDict[vr]
                                vRackPrice = priceWithFallback(vRackPlan, pricingMode, months)
                                # if showBandwidth is false, drop the plans with a vRack that costs money
                                if not bandwidthAndVRack and vRackPrice > 0.0:
                                    continue
                                # not sure if there is setup fee for the vRack?
                                thisPrice = thisPrice + vRackPrice
                            if addVAT:
                                # apply the VAT to the price
                                thisFee = round(thisFee * vatRate, 2)
                                thisPrice = round(thisPrice * vatRate, 2)
                            # apply the max price filter if different from 0
                            # maxPrice is always per month; scale it to match
                            # the period covered by the current price.
                            if maxPrice > 0 and thisPrice > maxPrice * months:
                                continue
                            myFqn = planCode + "." + memoryPlan['product'] + "." + storagePlan['product'] + "." + da
                            if myFqn in avail:
                                myavailability = avail[myFqn]
                            else:
                                myavailability = 'unknown'
                            # Add the plan to the list
                            myPlans.append(
                                { 'planCode' : planCode,
                                'model' : model,
                                'cpu' : cpu,
                                'datacenter' : da,
                                'storage' : st,
                                'memory' : me,
                                'bandwidth' : ba,
                                'vrack' : vr,
                                'fqn' : myFqn, # for auto buy
                                'price' : thisPrice,
                                'fee' : thisFee,
                                'availability' : myavailability
                                })
    return sorted(myPlans, key=lambda x: x['planCode'])

