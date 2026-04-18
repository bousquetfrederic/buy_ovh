"""Integration-style tests for manage_ovh startup paths."""
import copy
import sys
from unittest.mock import MagicMock

import pytest


def _reset_modules():
    for key in list(sys.modules):
        if key == 'manage_ovh' or key == 'm' or key.startswith('m.'):
            del sys.modules[key]


def _install_fakes(conf, login_succeeds=True):
    _reset_modules()
    sys.argv = ['manage_ovh', '--conf', 'conf.example.yaml']
    import m.config
    m.config.configFile = copy.deepcopy(conf)

    import m.api
    import m.manage

    calls = {'login': [], 'run': 0}

    def fake_login(endpoint, key, secret, ck):
        calls['login'].append((endpoint, key, secret, ck))
        if login_succeeds:
            m.api.client = MagicMock()
            return True
        return False

    m.api.client = None
    m.api.login = fake_login

    def fake_run():
        calls['run'] += 1

    m.manage.run = fake_run
    return calls


def _run(conf, **kw):
    calls = _install_fakes(conf, **kw)
    with pytest.raises(SystemExit):
        import manage_ovh  # noqa: F401
    return calls


BASE_CONF = {
    'APIEndpoint': 'ovh-eu',
}


class TestStartup:

    def test_no_creds_exits_fast(self):
        calls = _install_fakes(BASE_CONF)
        with pytest.raises(SystemExit) as excinfo:
            import manage_ovh  # noqa: F401
        assert 'APIKey' in str(excinfo.value)
        assert calls['login'] == []
        assert calls['run'] == 0

    def test_missing_consumer_key_exits_fast(self):
        conf = dict(BASE_CONF)
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        # APIConsumerKey intentionally missing
        calls = _install_fakes(conf)
        with pytest.raises(SystemExit) as excinfo:
            import manage_ovh  # noqa: F401
        assert 'APIConsumerKey' in str(excinfo.value)
        assert calls['login'] == []

    def test_login_failure_exits_fast(self):
        conf = dict(BASE_CONF)
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        calls = _install_fakes(conf, login_succeeds=False)
        with pytest.raises(SystemExit) as excinfo:
            import manage_ovh  # noqa: F401
        assert 'login failed' in str(excinfo.value).lower()
        assert calls['login'] == [('ovh-eu', 'k', 's', 'ck')]
        assert calls['run'] == 0

    def test_login_success_runs_ui(self):
        conf = dict(BASE_CONF)
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        calls = _run(conf)
        assert calls['login'] == [('ovh-eu', 'k', 's', 'ck')]
        assert calls['run'] == 1

    def test_keyboard_interrupt_in_ui_exits_cleanly(self):
        conf = dict(BASE_CONF)
        conf['APIKey'] = 'k'
        conf['APISecret'] = 's'
        conf['APIConsumerKey'] = 'ck'
        _install_fakes(conf)
        import m.manage

        def raising_run():
            raise KeyboardInterrupt()
        m.manage.run = raising_run

        with pytest.raises(SystemExit) as excinfo:
            import manage_ovh  # noqa: F401
        assert 'Bye now' in str(excinfo.value)
