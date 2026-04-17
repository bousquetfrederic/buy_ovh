"""Unit tests for m.catalog.apply_column_filters.

The helper backs the Excel-style per-column filter UI in m.interactive.
Tests cover both text (regex) and numeric (comparison) semantics, plus
safety against invalid regex input."""

from m.catalog import apply_column_filters, column_display_value


def _plan(**kw):
    base = {
        'planCode': '24ska01',
        'model': 'KS-A',
        'cpu': 'N2800',
        'datacenter': 'gra',
        'memory': 'ram-4g-ddr4',
        'storage': 'softraid-1x500nvme',
        'bandwidth': 'bw-300-mbps',
        'vrack': 'none',
        'fqn': '24ska01.ram-4g.softraid-1x500nvme.gra',
        'price': 10.0,
        'fee': 0.0,
    }
    base.update(kw)
    return base


def test_no_filters_returns_all():
    plans = [_plan(), _plan(datacenter='rbx')]
    assert apply_column_filters(plans, {}) == plans
    assert apply_column_filters(plans, {'model': ''}) == plans


def test_text_regex_is_case_insensitive():
    plans = [_plan(model='KS-A'), _plan(model='SYS-1')]
    assert len(apply_column_filters(plans, {'model': 'ks'})) == 1
    assert len(apply_column_filters(plans, {'model': 'KS'})) == 1


def test_filter_matches_displayed_value_not_raw_code():
    # memory raw = 'ram-8g-ddr4', displayed = '8g' — filter must hit display.
    plans = [_plan(memory='ram-8g-ddr4'), _plan(memory='ram-32g-ddr4')]
    assert column_display_value(plans[0], 'memory') == '8g'
    kept = apply_column_filters(plans, {'memory': '^8g$'})
    assert len(kept) == 1 and kept[0]['memory'] == 'ram-8g-ddr4'


def test_combined_filters_are_AND():
    plans = [
        _plan(model='KS-A', datacenter='gra'),
        _plan(model='KS-A', datacenter='rbx'),
        _plan(model='SYS-1', datacenter='gra'),
    ]
    kept = apply_column_filters(plans, {'model': 'KS', 'datacenter': '^gra$'})
    assert len(kept) == 1
    assert kept[0]['datacenter'] == 'gra'


def test_numeric_bare_number_is_leq():
    plans = [_plan(price=8.0), _plan(price=12.0), _plan(price=20.0)]
    kept = apply_column_filters(plans, {'price': '12'})
    assert sorted(p['price'] for p in kept) == [8.0, 12.0]


def test_numeric_operators():
    plans = [_plan(price=5.0), _plan(price=10.0), _plan(price=15.0)]
    assert [p['price'] for p in apply_column_filters(plans, {'price': '<10'})] == [5.0]
    assert [p['price'] for p in apply_column_filters(plans, {'price': '>=10'})] == [10.0, 15.0]
    assert [p['price'] for p in apply_column_filters(plans, {'price': '=10'})] == [10.0]


def test_total_column_filters_on_price_plus_fee():
    plans = [_plan(price=10.0, fee=5.0), _plan(price=10.0, fee=20.0)]
    kept = apply_column_filters(plans, {'total': '<=20'})
    assert len(kept) == 1 and kept[0]['fee'] == 5.0


def test_invalid_regex_drops_everything():
    plans = [_plan(), _plan(model='SYS-1')]
    assert apply_column_filters(plans, {'model': '[unterminated'}) == []


def test_invalid_numeric_pattern_drops_everything():
    plans = [_plan(price=5.0)]
    assert apply_column_filters(plans, {'price': 'not-a-number'}) == []


def test_fqn_filter():
    plans = [_plan(fqn='24ska01.a.b.gra'), _plan(fqn='24ska01.a.b.rbx')]
    kept = apply_column_filters(plans, {'fqn': r'\.gra$'})
    assert len(kept) == 1 and kept[0]['fqn'].endswith('.gra')
