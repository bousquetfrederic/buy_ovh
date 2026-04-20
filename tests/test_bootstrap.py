"""Unit tests for m.bootstrap.

Covers the credential gating used by all four entry points so the
behavior the monitor_ovh integration tests assert on is also pinned
down at the unit level.
"""
import logging
from unittest.mock import patch

import pytest

import m.api
import m.bootstrap


@pytest.fixture(autouse=True)
def _clean_logging():
    """Reset root handlers and urllib3 level between tests so each
    setup_logging call starts from a clean slate."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    urllib3 = logging.getLogger('urllib3')
    saved_urllib3 = urllib3.level
    yield
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)
    urllib3.setLevel(saved_urllib3)


class TestSetupLogging:

    def test_no_file_no_stream_fallback_installs_no_handler(self):
        before = len(logging.getLogger().handlers)
        m.bootstrap.setup_logging({}, 'test_prog')
        after = len(logging.getLogger().handlers)
        assert after == before

    def test_stream_fallback_installs_a_stream_handler(self):
        m.bootstrap.setup_logging({}, 'test_prog', stream_fallback=True)
        handlers = logging.getLogger().handlers
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_file_takes_precedence_over_stream_fallback(self, tmp_path):
        log_file = tmp_path / 'out.log'
        m.bootstrap.setup_logging(
            {'logFile': str(log_file)}, 'test_prog', stream_fallback=True)
        handlers = logging.getLogger().handlers
        assert any(isinstance(h, logging.FileHandler) for h in handlers)

    def test_loglevel_error_tunes_urllib3_to_error(self):
        m.bootstrap.setup_logging({'logLevel': 'ERROR'}, 'test_prog')
        assert logging.getLogger('urllib3').level == logging.ERROR

    def test_loglevel_warning_tunes_urllib3_to_warning(self):
        m.bootstrap.setup_logging({'logLevel': 'WARNING'}, 'test_prog')
        assert logging.getLogger('urllib3').level == logging.WARNING


class TestLoginIfCredentials:

    def test_no_creds_returns_false_without_calling_api(self):
        with patch.object(m.api, 'login') as mlog, \
             patch.object(m.api, 'get_consumer_key') as mck:
            assert m.bootstrap.login_if_credentials({}, 'ovh-eu') is False
            mlog.assert_not_called()
            mck.assert_not_called()

    def test_partial_creds_returns_false_without_calling_api(self):
        conf = {'APIKey': 'k'}  # no APISecret
        with patch.object(m.api, 'login') as mlog, \
             patch.object(m.api, 'get_consumer_key') as mck:
            assert m.bootstrap.login_if_credentials(conf, 'ovh-eu') is False
            mlog.assert_not_called()
            mck.assert_not_called()

    def test_full_creds_invokes_login_and_passes_return_through(self):
        conf = {'APIKey': 'k', 'APISecret': 's', 'APIConsumerKey': 'ck'}
        with patch.object(m.api, 'login', return_value=True) as mlog:
            assert m.bootstrap.login_if_credentials(conf, 'ovh-eu') is True
            mlog.assert_called_once_with('ovh-eu', 'k', 's', 'ck')

    def test_login_failure_returned_as_false(self):
        conf = {'APIKey': 'k', 'APISecret': 's', 'APIConsumerKey': 'ck'}
        with patch.object(m.api, 'login', return_value=False):
            assert m.bootstrap.login_if_credentials(conf, 'ovh-eu') is False


class TestLoginRequired:

    def test_missing_creds_sys_exits_with_missing_msg(self):
        with patch.object(m.api, 'login') as mlog:
            with pytest.raises(SystemExit) as excinfo:
                m.bootstrap.login_required(
                    {}, 'ovh-eu', 'need creds', 'oops failed')
            assert 'need creds' in str(excinfo.value)
            mlog.assert_not_called()

    def test_partial_creds_sys_exits_without_login(self):
        conf = {'APIKey': 'k', 'APISecret': 's'}  # no APIConsumerKey
        with patch.object(m.api, 'login') as mlog:
            with pytest.raises(SystemExit):
                m.bootstrap.login_required(
                    conf, 'ovh-eu', 'need creds', 'oops failed')
            mlog.assert_not_called()

    def test_login_failure_sys_exits_with_failed_msg(self):
        conf = {'APIKey': 'k', 'APISecret': 's', 'APIConsumerKey': 'ck'}
        with patch.object(m.api, 'login', return_value=False):
            with pytest.raises(SystemExit) as excinfo:
                m.bootstrap.login_required(
                    conf, 'ovh-eu', 'need creds', 'oops failed')
            assert 'oops failed' in str(excinfo.value)

    def test_login_success_returns_none(self):
        conf = {'APIKey': 'k', 'APISecret': 's', 'APIConsumerKey': 'ck'}
        with patch.object(m.api, 'login', return_value=True):
            # No exception, no return value — just falls through.
            assert m.bootstrap.login_required(
                conf, 'ovh-eu', 'need creds', 'oops failed') is None
