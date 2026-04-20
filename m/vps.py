import logging
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)

__all__ = ['fetch_vps_plan_codes', 'build_vps_availability_dict']


def fetch_vps_plan_codes(url, subsidiary):
    """Return the orderable base-VPS planCodes from the public catalog.
    Drops addons (no vps- prefix) and composite/bundled SKUs (embed a
    second vps- segment, see buy_vps.py for the rationale)."""
    r = requests.get(url + "order/catalog/public/vps",
                     params={'ovhSubsidiary': subsidiary}, timeout=30)
    r.raise_for_status()
    out = []
    for plan in r.json().get('plans', []):
        pc = plan.get('planCode', '')
        if not pc.startswith('vps-'):
            continue
        if '-vps-' in pc:
            continue
        out.append(pc)
    return out


def _to_avail_string(status, days, max_preorder_days):
    """Map (linuxStatus, daysBeforeDelivery) to the string the monitor
    diffs on. test_availability treats anything outside
    {unknown, unavailable, comingSoon} as available, so in-stock and
    short-delay preorders look identical to the diff."""
    if status == 'available':
        return "available"
    if status == 'out-of-stock-preorder-allowed':
        if days and days <= max_preorder_days:
            return f"{days}d"
        return "unavailable"
    if status == 'out-of-stock':
        return "unavailable"
    return "unknown"


def _fetch_one(url, subsidiary, plan_code):
    try:
        r = requests.get(url + 'vps/order/rule/datacenter',
                         params={'ovhSubsidiary': subsidiary, 'planCode': plan_code},
                         timeout=30)
        r.raise_for_status()
        return plan_code, r.json().get('datacenters', [])
    except Exception:
        logger.exception("VPS availability fetch failed for " + plan_code)
        return plan_code, None


def build_vps_availability_dict(url, subsidiary, plan_codes=None,
                                concurrency=10, max_preorder_days=30):
    """Return {super_fqn: avail_string} for the linux family across every
    VPS plan, where super_fqn = "<planCode>.linux.<DC>".

    Out-of-stock DCs are emitted as "unavailable" (not omitted) so
    avail_changed_Str can diff a transition from available -> OOS.
    Preorders with daysBeforeDelivery <= max_preorder_days count as
    available (default matches the user's +7d/+30d rule)."""
    logger.debug("Building VPS availability list")
    if plan_codes is None:
        plan_codes = fetch_vps_plan_codes(url, subsidiary)
    out = {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        results = ex.map(lambda pc: _fetch_one(url, subsidiary, pc), plan_codes)
        for pc, dcs in results:
            if dcs is None:
                continue
            for d in dcs:
                dc = d.get('datacenter')
                if not dc:
                    continue
                days = d.get('daysBeforeDelivery') or 0
                fqn = f"{pc}.linux.{dc}"
                out[fqn] = _to_avail_string(d.get('linuxStatus'), days, max_preorder_days)
    return out
