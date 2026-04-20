"""Unit tests for the pricing helpers in m.catalog.

These cover the split that disambiguates the old 0-sentinel: a plan with
no offer at a given commitment now returns None (and gets dropped from
the list), while a bundled addon that legitimately costs 0 stays at 0.0.
"""
from m.catalog import (addon_price_with_fallback, plan_fee, plan_price,
                       _apply_promo, _find_pricing, _pricing_mode)


def _entry(mode='default', phase=1, capacity='renew',
           strategy='tiered', price=1_000_000_000, promotions=None):
    return {'mode': mode, 'phase': phase, 'capacities': [capacity],
            'strategy': strategy, 'price': price,
            'promotions': promotions or []}


class TestPricingMode:

    def test_default_for_1_month(self):
        assert _pricing_mode(1) == 'default'

    def test_upfront12(self):
        assert _pricing_mode(12) == 'upfront12'

    def test_upfront24(self):
        assert _pricing_mode(24) == 'upfront24'

    def test_other_falls_back_to_default(self):
        # Anything else (e.g. 6) isn't a commitment OVH sells, so the
        # caller gets default-rate pricing.
        assert _pricing_mode(6) == 'default'


class TestApplyPromo:

    def test_no_promo_returns_base(self):
        assert _apply_promo(_entry(price=1_000_000_000)) == 10.0

    def test_percentage_promo(self):
        entry = _entry(price=1_000_000_000,
                       promotions=[{'type': 'percentage', 'value': 25}])
        assert _apply_promo(entry) == 7.5

    def test_non_percentage_promo_ignored(self):
        # buy_ovh never implemented non-percentage promos; they silently
        # pass through at the base price rather than crashing.
        entry = _entry(price=1_000_000_000,
                       promotions=[{'type': 'fixed', 'value': 5}])
        assert _apply_promo(entry) == 10.0


class TestFindPricing:

    def test_matches_all_four_fields(self):
        plan = {'pricings': [_entry(mode='default', phase=1, capacity='renew')]}
        assert _find_pricing(plan, mode='default', phase=1, capacity='renew') is not None

    def test_mismatch_returns_none(self):
        plan = {'pricings': [_entry(mode='default', phase=1, capacity='renew')]}
        assert _find_pricing(plan, mode='upfront12', phase=1, capacity='renew') is None

    def test_non_tiered_strategy_skipped(self):
        plan = {'pricings': [_entry(strategy='step')]}
        assert _find_pricing(plan, mode='default', phase=1, capacity='renew') is None

    def test_malformed_entry_skipped_not_raised(self):
        # A row missing 'capacities' shouldn't crash the whole parse.
        plan = {'pricings': [
            {'mode': 'default', 'phase': 1, 'strategy': 'tiered', 'price': 1},
            _entry(),
        ]}
        assert _find_pricing(plan, mode='default', phase=1, capacity='renew') is not None

    def test_missing_pricings_returns_none(self):
        assert _find_pricing({}, mode='default', phase=1, capacity='renew') is None


class TestPlanPrice:

    def test_found_returns_currency_float(self):
        plan = {'pricings': [_entry(mode='default', price=1_000_000_000)]}
        assert plan_price(plan, 'default') == 10.0

    def test_missing_mode_returns_none(self):
        # This is the key disambiguation vs. the old 0-sentinel: a plan
        # with no upfront12 offer gets dropped by the caller, not priced at 0.
        plan = {'pricings': [_entry(mode='default')]}
        assert plan_price(plan, 'upfront12') is None

    def test_empty_pricings_returns_none(self):
        assert plan_price({'pricings': []}, 'default') is None


class TestPlanFee:

    def test_found_returns_currency_float(self):
        plan = {'pricings': [_entry(phase=0, capacity='installation',
                                    price=500_000_000)]}
        assert plan_fee(plan, 'default') == 5.0

    def test_missing_returns_zero_not_none(self):
        # Unlike price, a missing fee doesn't drop the plan — plenty of
        # plans ship with no installation charge.
        assert plan_fee({'pricings': []}, 'default') == 0.0


class TestAddonPriceWithFallback:

    def test_mode_present_uses_that_entry(self):
        addon = {'pricings': [_entry(mode='upfront12', price=500_000_000)]}
        assert addon_price_with_fallback(addon, 'upfront12', 12) == 5.0

    def test_bundled_addon_stays_zero(self):
        # Default quote of 0 means the addon is free on default mode.
        # Multiplying by months is still 0 — the point is we don't
        # confuse "no row at all" with "free".
        addon = {'pricings': [_entry(mode='default', price=0)]}
        assert addon_price_with_fallback(addon, 'default', 1) == 0.0

    def test_missing_mode_falls_back_to_default_times_months(self):
        # Addon doesn't list upfront12 — we charge default × 12.
        addon = {'pricings': [_entry(mode='default', price=100_000_000)]}
        assert addon_price_with_fallback(addon, 'upfront12', 12) == 12.0

    def test_missing_default_and_missing_mode_is_zero(self):
        # No pricing rows at all → nothing to charge.
        assert addon_price_with_fallback({'pricings': []}, 'upfront12', 12) == 0.0

    def test_default_mode_without_default_row_is_zero(self):
        # Mode is already 'default' — no fallback possible, no row found.
        assert addon_price_with_fallback({'pricings': []}, 'default', 1) == 0.0
