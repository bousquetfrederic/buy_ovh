"""Integration-style tests for monitor_ovh.

Each test sets up fake m.availability / m.catalog / m.api / m.email / m.print
modules, clears monitor_ovh from sys.modules, and re-imports it. The main
loop is forced to exit after one iteration by making build_availability_dict
raise KeyboardInterrupt on its second call (the first call is the real
iteration we want to observe).
"""
import copy
import sys
from unittest.mock import MagicMock

import pytest


def _reset_modules():
    # Drop monitor_ovh and everything under m.* so the next import starts
    # from scratch with our patched modules picked up.
    for key in list(sys.modules):
        if key == 'monitor_ovh' or key == 'm' or key.startswith('m.'):
            del sys.modules[key]


def _install_fakes(conf, avail=None, plans=None, login_succeeds=True,
                   kb_after_cycles=1):
    """Patch every external boundary monitor_ovh touches.

    Returns a dict that records calls so tests can assert on behavior.
    """
    _reset_modules()

    # m.config loads YAML from sys.argv[1] at import time; point it at the
    # example file so the import succeeds, then overwrite configFile with
    # our test dict.
    sys.argv = ['monitor_ovh', 'conf.example.yaml']
    import m.config
    m.config.configFile = copy.deepcopy(conf)

    # Now force-import the modules so our patches stick before monitor_ovh
    # binds references to them.
    import m.availability
    import m.catalog
    import m.api
    import m.email
    import m.print

    calls = {
        'login': [],
        'build_cart': [],
        'checkout_cart': [],
        'send_email': [],
        'startup_email': 0,
        'auto_buy_email': [],
        'availability': 0,
        'catalog': 0,
    }

    def fake_avail(url, dcs):
        calls['availability'] += 1
        if calls['availability'] > kb_after_cycles:
            raise KeyboardInterrupt()
        return dict(avail or {})

    def fake_catalog(*a, **kw):
        calls['catalog'] += 1
        return [dict(p) for p in (plans or [])]

    def fake_login(endpoint, key, secret, ck):
        calls['login'].append((endpoint, key, secret, ck))
        if login_succeeds:
            m.api.client = MagicMock()
            return True
        return False

    def fake_build_cart(plan, *a, **kw):
        calls['build_cart'].append(plan['fqn'])
        return 'fake-cart-id'

    def fake_checkout_cart(cart, buyNow, fake=False):
        calls['checkout_cart'].append((cart, buyNow, fake))

    def fake_send_email(subject, body, warnUser=False):
        calls['send_email'].append((subject, body))

    def fake_startup_email():
        calls['startup_email'] += 1

    def fake_auto_buy_email(msg):
        calls['auto_buy_email'].append(msg)

    m.availability.build_availability_dict = fake_avail
    m.availability.test_availability = lambda a, u=True, k=True: True
    m.catalog.build_list = fake_catalog
    m.api.client = None
    m.api.login = fake_login
    m.api.is_logged_in = lambda: m.api.client is not None
    m.api.api_url = lambda ep: 'https://fake/'
    m.api.build_cart = fake_build_cart
    m.api.checkout_cart = fake_checkout_cart
    m.email.send_email = fake_send_email
    m.email.send_startup_email = fake_startup_email
    m.email.send_auto_buy_email = fake_auto_buy_email

    # Silence output-heavy helpers.
    m.print.clear_screen = lambda: None
    m.print.print_prompt = lambda *a, **kw: None
    m.print.print_plan_list = lambda *a, **kw: None
    m.print.print_and_sleep = lambda show, secs: None

    # Don't burn real time in exception-retry paths.
    import time
    calls['_time_sleep_patched'] = time.sleep
    time.sleep = lambda s: None

    return calls


def _run(conf, **kwargs):
    calls = _install_fakes(conf, **kwargs)
    with pytest.raises(SystemExit):
        import monitor_ovh  # noqa: F401
    return calls


def _plan(fqn='24sk40.ram-32g.ssd.gra', model='KS-4', price=10.0,
          datacenter='gra', availability='low'):
    return {
        'fqn': fqn,
        'model': model,
        'price': price,
        'datacenter': datacenter,
        'availability': availability,
        'memory': 'ram-32g-ecc',
        'storage': 'softraid-2x480ssd',
        'bandwidth': 'bandwidth-500',
        'vrack': 'none',
        'planCode': '24sk40',
        'fee': 0.0,
        'cpu': 'Xeon',
    }


BASE_CONF = {
    'APIEndpoint': 'ovh-eu',
    'ovhSubsidiary': 'FR',
    'datacenters': ['gra'],
    'filterName': '',
    'filterDisk': '',
    'filterMemory': '',
    'maxPrice': 0,
    'sleepsecs': 0,
    'printListWhileLooping': False,
    'fakeBuy': True,
}


# ---------------- Startup: credentials gating ----------------

class TestStartupCreds:

    def test_no_autobuy_no_creds_runs_without_login(self):
        calls = _run(BASE_CONF)
        assert calls['login'] == []
        assert calls['availability'] >= 1  # loop did start

    def test_autobuy_without_any_creds_exits_fast(self):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': False}]
        calls = _install_fakes(conf)
        with pytest.raises(SystemExit) as excinfo:
            import monitor_ovh  # noqa: F401
        # Never reached the loop.
        assert calls['availability'] == 0
        assert 'auto_buy' in str(excinfo.value)
        assert 'missing' in str(excinfo.value).lower() \
               or 'login' in str(excinfo.value).lower()

    def test_autobuy_with_partial_creds_exits_fast(self):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': False}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        # APIConsumerKey intentionally missing
        calls = _install_fakes(conf)
        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401
        assert calls['availability'] == 0
        assert calls['login'] == []  # login never attempted

    def test_autobuy_with_full_creds_logs_in(self):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': False}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        calls = _run(conf)
        assert len(calls['login']) == 1
        assert calls['login'][0] == ('ovh-eu', 'k', 's', 'ck')

    def test_autobuy_login_failure_exits_fast(self):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': False}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        calls = _install_fakes(conf, login_succeeds=False)
        with pytest.raises(SystemExit) as excinfo:
            import monitor_ovh  # noqa: F401
        assert 'login failed' in str(excinfo.value).lower()
        assert calls['availability'] == 0  # loop not entered


# ---------------- Startup: email at startup ----------------

class TestStartupEmail:

    def test_startup_email_sent_when_configured(self):
        conf = dict(BASE_CONF)
        conf['email_on'] = True
        conf['email_at_startup'] = True
        calls = _run(conf)
        assert calls['startup_email'] == 1

    def test_startup_email_skipped_when_email_off(self):
        conf = dict(BASE_CONF)
        conf['email_on'] = False
        conf['email_at_startup'] = True
        calls = _run(conf)
        assert calls['startup_email'] == 0

    def test_startup_email_skipped_by_default(self):
        calls = _run(BASE_CONF)
        assert calls['startup_email'] == 0


# ---------------- Autobuy: firing ----------------

class TestAutoBuyFires:

    def _conf_with_autobuy(self, num=1, invoice=False, unknown=False,
                           max_price=0):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': num,
                             'max_price': max_price,
                             'invoice': invoice, 'unknown': unknown}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        return conf

    def test_matching_plan_triggers_buy(self):
        conf = self._conf_with_autobuy()
        calls = _run(conf, plans=[_plan(model='KS-4')])
        assert len(calls['build_cart']) == 1
        assert len(calls['checkout_cart']) == 1
        # buyNow=True since invoice=False
        assert calls['checkout_cart'][0][1] is True

    def test_invoice_mode_sets_buyNow_false(self):
        conf = self._conf_with_autobuy(invoice=True)
        calls = _run(conf, plans=[_plan(model='KS-4')])
        assert len(calls['checkout_cart']) == 1
        assert calls['checkout_cart'][0][1] is False

    def test_non_matching_plan_does_not_buy(self):
        conf = self._conf_with_autobuy()
        calls = _run(conf, plans=[_plan(model='OTHER', fqn='other.foo.gra')])
        assert calls['build_cart'] == []
        assert calls['checkout_cart'] == []

    def test_price_cap_prevents_buy(self):
        conf = self._conf_with_autobuy(max_price=5)
        calls = _run(conf, plans=[_plan(model='KS-4', price=100.0)])
        assert calls['build_cart'] == []

    def test_no_plans_no_buys(self):
        conf = self._conf_with_autobuy()
        calls = _run(conf, plans=[])
        assert calls['build_cart'] == []

    def test_num_gating_prevents_second_fire(self):
        # Two cycles, num=1: only one buy.
        conf = self._conf_with_autobuy(num=1)
        calls = _install_fakes(conf, plans=[_plan(model='KS-4')],
                               kb_after_cycles=2)
        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401
        assert len(calls['build_cart']) == 1

    def test_num_two_fires_twice_across_cycles(self):
        conf = self._conf_with_autobuy(num=2)
        calls = _install_fakes(conf, plans=[_plan(model='KS-4')],
                               kb_after_cycles=2)
        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401
        assert len(calls['build_cart']) == 2

    def test_unknown_availability_gated_by_rule_flag(self):
        # Plan has 'unknown' availability; rule has unknown=False → no buy.
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': False}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'

        calls = _install_fakes(conf, plans=[_plan(model='KS-4',
                                                  availability='unknown')])
        # Use the real test_availability for an honest check.
        import m.availability

        def real_test_availability(a, u=False, k=False):
            if a == 'unknown':
                return k
            if a in ('unavailable', 'comingSoon'):
                return u
            return True
        m.availability.test_availability = real_test_availability

        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401
        assert calls['build_cart'] == []

    def test_unknown_availability_allowed_when_rule_opts_in(self):
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [{'regex': 'KS-4', 'num': 1, 'max_price': 0,
                             'invoice': False, 'unknown': True}]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'

        calls = _install_fakes(conf, plans=[_plan(model='KS-4',
                                                  availability='unknown')])
        import m.availability

        def real_test_availability(a, u=False, k=False):
            if a == 'unknown':
                return k
            if a in ('unavailable', 'comingSoon'):
                return u
            return True
        m.availability.test_availability = real_test_availability

        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401
        assert len(calls['build_cart']) == 1

    def test_two_rules_fire_twice_on_same_plan(self):
        # Both rules match; the loop doesn't break after the first match.
        conf = dict(BASE_CONF)
        conf['auto_buy'] = [
            {'regex': 'KS-4', 'num': 1, 'max_price': 0,
             'invoice': False, 'unknown': False},
            {'regex': '24sk40', 'num': 1, 'max_price': 0,
             'invoice': True, 'unknown': False},
        ]
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        calls = _run(conf, plans=[_plan(model='KS-4', fqn='24sk40.foo.gra')])
        assert len(calls['build_cart']) == 2
        # One buyNow=True (first rule), one buyNow=False (second).
        buy_nows = sorted(x[1] for x in calls['checkout_cart'])
        assert buy_nows == [False, True]


# ---------------- Monitor: emails ----------------

class TestMonitorEmails:

    def test_availability_monitor_sends_email_when_changed(self):
        # Need two iterations so there's a previousAvailabilities to diff.
        conf = dict(BASE_CONF)
        conf['email_on'] = True
        conf['email_availability_monitor'] = '24sk40'

        # First iter returns the plan as unavailable; second iter returns it
        # available; the diff should fire an email. Force 2 iterations then
        # exit.
        avail_sequence = [
            {'24sk40.gra': 'unavailable'},
            {'24sk40.gra': 'low'},
        ]

        calls = _install_fakes(conf, kb_after_cycles=2)
        idx = {'n': 0}

        def seq_avail(url, dcs):
            calls['availability'] += 1
            if calls['availability'] > 2:
                raise KeyboardInterrupt()
            result = avail_sequence[idx['n']]
            idx['n'] += 1
            return dict(result)

        import m.availability
        m.availability.build_availability_dict = seq_avail
        # We need real test_availability semantics here for the diff to
        # classify unavailable vs low correctly.
        def real_test_availability(a, u=False, k=False):
            if a == 'unknown':
                return k
            if a in ('unavailable', 'comingSoon'):
                return u
            return True
        m.availability.test_availability = real_test_availability

        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401

        subjects = [s for s, _ in calls['send_email']]
        assert any('availabilities' in s for s in subjects)

    def test_no_email_when_email_on_false(self):
        conf = dict(BASE_CONF)
        conf['email_on'] = False
        conf['email_availability_monitor'] = '24sk40'

        avail_sequence = [
            {'24sk40.gra': 'unavailable'},
            {'24sk40.gra': 'low'},
        ]

        calls = _install_fakes(conf, kb_after_cycles=2)
        idx = {'n': 0}

        def seq_avail(url, dcs):
            calls['availability'] += 1
            if calls['availability'] > 2:
                raise KeyboardInterrupt()
            result = avail_sequence[idx['n']]
            idx['n'] += 1
            return dict(result)

        import m.availability
        m.availability.build_availability_dict = seq_avail

        with pytest.raises(SystemExit):
            import monitor_ovh  # noqa: F401

        assert calls['send_email'] == []
