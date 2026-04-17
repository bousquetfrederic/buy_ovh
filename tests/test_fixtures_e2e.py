"""Fixture-driven end-to-end tests.

Unlike test_monitor_ovh.py, which stubs out m.catalog.build_list and
m.availability.build_availability_dict wholesale, these tests patch the
single HTTP seam (`requests.get`) and let the real parsing, price
computation, filtering, and autobuy-matching run against canned
OVH-shaped JSON.

Purpose: catch regressions in catalog.py / availability.py / autobuy.py
when OVH's response shape or our price math changes.
"""
from unittest.mock import patch

import pytest

from m.autobuy import add_auto_buy, is_auto_buy
from m.availability import build_availability_dict
from m.catalog import build_list


# ---------------- Fixture builders ----------------
# Prices are given in euros; we scale to OVH's 1e8 units internally.

_SCALE = 100000000


def _pricing(mode, euros, phase=1, capacity='renew', promo_pct=None):
    promos = []
    if promo_pct is not None:
        promos = [{'type': 'percentage', 'value': promo_pct}]
    return {
        'phase': phase,
        'capacities': [capacity],
        'strategy': 'tiered',
        'mode': mode,
        'price': int(euros * _SCALE),
        'promotions': promos,
    }


def _plan(plan_code, model, cpu='Xeon-E3', pricings=(),
          memories=(), storages=(), bandwidths=(), vracks=(),
          datacenters=('gra',)):
    families = []
    if memories:
        families.append({'name': 'memory', 'addons': list(memories)})
    if storages:
        families.append({'name': 'storage', 'addons': list(storages)})
    if bandwidths:
        families.append({'name': 'bandwidth', 'addons': list(bandwidths)})
    if vracks:
        families.append({'name': 'vrack', 'addons': list(vracks)})
    return {
        'planCode': plan_code,
        'invoiceName': f'{model} |{cpu} ',
        'pricings': list(pricings),
        'addonFamilies': families,
        'configurations': [
            {'name': 'dedicated_datacenter', 'values': list(datacenters)},
        ],
    }


def _addon(plan_code, product=None, pricings=None):
    if pricings is None:
        pricings = [_pricing('default', 0)]
    return {
        'planCode': plan_code,
        'product': product or plan_code,
        'pricings': list(pricings),
    }


def _catalog(plans, addons, tax_rate=20.0):
    return {
        'locale': {'taxRate': tax_rate},
        'plans': list(plans),
        'addons': list(addons),
    }


def _avail(*entries):
    """Each entry is (fqn_base, {dc: availability})."""
    out = []
    for fqn, dcs in entries:
        out.append({
            'fqn': fqn,
            'datacenters': [{'datacenter': dc, 'availability': a}
                            for dc, a in dcs.items()],
        })
    return out


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _patch_requests(catalog, availabilities):
    def side_effect(url, *a, **kw):
        if 'order/catalog' in url:
            return _FakeResp(catalog)
        if 'datacenter/availabilities' in url:
            return _FakeResp(availabilities)
        raise AssertionError(f'unexpected URL in test: {url}')
    return patch('requests.get', side_effect=side_effect)


# ---------------- Standard two-DC KS-4 scenario ----------------

def _ks4_catalog(plan_pricings=None, memory_pricings=None):
    """Single KS-4 plan, gra+rbx, free addons. Caller can override
    the plan's or memory addon's pricing list."""
    if plan_pricings is None:
        # 10€/month @ default, with 20% promo → 8€/month
        plan_pricings = [_pricing('default', 10, promo_pct=20)]
    return _catalog(
        plans=[_plan('24sk40', 'KS-4',
                     pricings=plan_pricings,
                     memories=['ram-32g-ecc'],
                     storages=['softraid-2x480ssd'],
                     bandwidths=['bandwidth-500'],
                     datacenters=['gra', 'rbx'])],
        addons=[
            _addon('ram-32g-ecc', pricings=memory_pricings),
            _addon('softraid-2x480ssd'),
            _addon('bandwidth-500'),
        ],
    )


_KS4_AVAIL = _avail(
    ('24sk40.ram-32g-ecc.softraid-2x480ssd',
     {'gra': 'low', 'rbx': 'unavailable'}),
)


def _build(catalog, avail, **overrides):
    kwargs = dict(
        ovhSubsidiary='FR', filterName='', filterDisk='',
        filterMemory='', acceptable_dc=['gra', 'rbx'], maxPrice=0,
        addVAT=False, months=1, bandwidthAndVRack=True,
    )
    kwargs.update(overrides)
    with _patch_requests(catalog, avail):
        avail_dict = build_availability_dict('https://fake/',
                                             kwargs['acceptable_dc'])
        return build_list('https://fake/', avail_dict, **kwargs)


# ---------------- Availability parsing ----------------

class TestAvailabilityShape:

    def test_flattens_fqn_x_datacenter(self):
        with _patch_requests(_ks4_catalog(), _KS4_AVAIL):
            got = build_availability_dict('https://fake/', ['gra', 'rbx'])
        assert got == {
            '24sk40.ram-32g-ecc.softraid-2x480ssd.gra': 'low',
            '24sk40.ram-32g-ecc.softraid-2x480ssd.rbx': 'unavailable',
        }


# ---------------- Catalog parsing + pricing (months=1) ----------------

class TestCatalogPricing:

    def test_promo_applied_to_plan_price(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL)
        assert len(plans) == 2
        assert all(p['price'] == pytest.approx(8.0) for p in plans)

    def test_vat_rounds_price(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL, addVAT=True)
        assert all(p['price'] == pytest.approx(9.60) for p in plans)

    def test_availability_merged_in(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL)
        by_dc = {p['datacenter']: p['availability'] for p in plans}
        assert by_dc == {'gra': 'low', 'rbx': 'unavailable'}

    def test_missing_availability_tagged_unknown(self):
        plans = _build(_ks4_catalog(), [])
        assert all(p['availability'] == 'unknown' for p in plans)

    def test_name_filter_excludes_non_matching(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL, filterName='NOPE')
        assert plans == []

    def test_datacenter_filter_restricts_output(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL, acceptable_dc=['gra'])
        assert {p['datacenter'] for p in plans} == {'gra'}

    def test_max_price_drops_over_budget(self):
        # Price is 8€/month; maxPrice=5 should drop it.
        plans = _build(_ks4_catalog(), _KS4_AVAIL, maxPrice=5)
        assert plans == []


# ---------------- Commitment modes (months=12 / months=24) ----------------

class TestCommitmentModes:

    def test_months_12_uses_upfront12_price(self):
        # Plan has default=10€/mo and a discounted upfront12=90€ total.
        catalog = _ks4_catalog(plan_pricings=[
            _pricing('default', 10),
            _pricing('upfront12', 90),
        ])
        plans = _build(catalog, _KS4_AVAIL, months=12)
        # 90€ plan + 0€ addons; no promo, no VAT.
        assert all(p['price'] == pytest.approx(90.0) for p in plans)

    def test_plan_without_upfront24_is_dropped(self):
        # Plan only sells at default — asking for months=24 should drop it.
        catalog = _ks4_catalog(plan_pricings=[_pricing('default', 10)])
        plans = _build(catalog, _KS4_AVAIL, months=24)
        assert plans == []

    def test_addon_without_mode_falls_back_to_default_times_months(self):
        # Plan has upfront24=180€; memory addon only has default=2€/mo.
        # Expected: 180 + (2 × 24) = 228€ total for the 24-month term.
        catalog = _ks4_catalog(
            plan_pricings=[
                _pricing('default', 10),
                _pricing('upfront24', 180),
            ],
            memory_pricings=[_pricing('default', 2)],
        )
        plans = _build(catalog, _KS4_AVAIL, months=24)
        assert all(p['price'] == pytest.approx(228.0) for p in plans)

    def test_max_price_scaled_to_term(self):
        # build_list compares thisPrice > maxPrice * months.
        # At months=12, upfront12=120€, maxPrice=9 (€/mo) → cap is 108 → drop.
        catalog = _ks4_catalog(plan_pricings=[
            _pricing('default', 10),
            _pricing('upfront12', 120),
        ])
        plans = _build(catalog, _KS4_AVAIL, months=12, maxPrice=9)
        assert plans == []

        # maxPrice=11 → cap is 132 → kept.
        plans = _build(catalog, _KS4_AVAIL, months=12, maxPrice=11)
        assert len(plans) == 2


# ---------------- Bandwidth / vRack gating ----------------

class TestBandwidthGating:

    def test_paid_bandwidth_dropped_when_flag_false(self):
        # A plan whose bandwidth addon costs money should be dropped when
        # the user has toggled bandwidthAndVRack=False.
        catalog = _catalog(
            plans=[_plan('24sk40', 'KS-4',
                         pricings=[_pricing('default', 10)],
                         memories=['ram-32g-ecc'],
                         storages=['softraid-2x480ssd'],
                         bandwidths=['bandwidth-1g-paid'],
                         datacenters=['gra'])],
            addons=[
                _addon('ram-32g-ecc'),
                _addon('softraid-2x480ssd'),
                _addon('bandwidth-1g-paid',
                       pricings=[_pricing('default', 5)]),
            ],
        )
        avail = _avail(
            ('24sk40.ram-32g-ecc.softraid-2x480ssd',
             {'gra': 'low'}),
        )
        assert _build(catalog, avail, acceptable_dc=['gra'],
                      bandwidthAndVRack=False) == []
        # With the flag on, the plan is kept and the bandwidth price is
        # folded into the total.
        plans = _build(catalog, avail, acceptable_dc=['gra'],
                       bandwidthAndVRack=True)
        assert len(plans) == 1
        assert plans[0]['price'] == pytest.approx(15.0)


# ---------------- End-to-end: catalog → availability → autobuy ----------------

class TestEndToEndAutoBuy:

    def test_autobuy_rule_matches_only_available_plan(self):
        plans = _build(_ks4_catalog(), _KS4_AVAIL)
        rules = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                  'invoice': False, 'unknown': False}]
        add_auto_buy(plans, rules)

        from m.availability import test_availability
        buyable = [p for p in plans
                   if p['autobuy']
                   and test_availability(p['availability'], False,
                                         rules[0]['unknown'])]
        assert len(buyable) == 1
        assert buyable[0]['datacenter'] == 'gra'

    def test_autobuy_max_price_honors_real_promo_price(self):
        # Raw plan price is 10€ but promo drops it to 8€.
        # A rule with max_price=9 should therefore match.
        plans = _build(_ks4_catalog(), _KS4_AVAIL, acceptable_dc=['gra'])
        rule = {'regex': 'KS-4', 'num': 1, 'max_price': 9,
                'invoice': False, 'unknown': False}
        assert any(is_auto_buy(p, rule) for p in plans)

    def test_autobuy_max_price_honors_term_scaled_price(self):
        # At months=12 the plan price is 90€ total. A monthly max_price cap
        # is compared against the full-term price, so max_price=50 blocks
        # the buy even though the per-month equivalent (7.5€) is well under.
        catalog = _ks4_catalog(plan_pricings=[
            _pricing('default', 10),
            _pricing('upfront12', 90),
        ])
        plans = _build(catalog, _KS4_AVAIL, months=12, acceptable_dc=['gra'])
        rule_lo = {'regex': 'KS-4', 'num': 1, 'max_price': 50,
                   'invoice': False, 'unknown': False}
        rule_hi = {'regex': 'KS-4', 'num': 1, 'max_price': 100,
                   'invoice': False, 'unknown': False}
        assert not any(is_auto_buy(p, rule_lo) for p in plans)
        assert any(is_auto_buy(p, rule_hi) for p in plans)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
