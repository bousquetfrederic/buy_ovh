"""Unit tests for m.conf — the typed config layer.

These tests cover the from_yaml construction that used to be scattered
across buy_ovh's loadConfigMain function and module globals. conf.yaml is
the single source of truth; nothing is persisted to the home directory.
"""
from m.conf import (BuyOvhConfig, MonitorConfig,
                    KNOWN_YAML_KEYS, warn_unknown_keys)


class TestBuyOvhConfigFromYaml:

    def test_empty_yaml_produces_defaults(self):
        cfg = BuyOvhConfig.from_yaml({})
        assert cfg.APIEndpoint == 'ovh-eu'
        assert cfg.ovhSubsidiary == 'FR'
        assert cfg.acceptable_dc == []
        assert cfg.fakeBuy is True
        assert cfg.months == 1
        assert cfg.showCpu is True
        assert cfg.showUnavailable is True

    def test_yaml_overrides_defaults(self):
        cfg = BuyOvhConfig.from_yaml({
            'APIEndpoint': 'ovh-ca',
            'ovhSubsidiary': 'CA',
            'fakeBuy': False,
            'months': 24,
        })
        assert cfg.APIEndpoint == 'ovh-ca'
        assert cfg.ovhSubsidiary == 'CA'
        assert cfg.fakeBuy is False
        assert cfg.months == 24

    def test_acceptable_dc_reads_from_datacenters_yaml_alias(self):
        # The old loadConfigMain had a (default, yaml_key) tuple to map
        # `datacenters` in the YAML to `acceptable_dc` on the globals.
        cfg = BuyOvhConfig.from_yaml({'datacenters': ['gra', 'sbg']})
        assert cfg.acceptable_dc == ['gra', 'sbg']

    def test_acceptable_dc_attribute_name_is_ignored_in_yaml(self):
        # YAML key is `datacenters`; the attr name is not a recognised key.
        cfg = BuyOvhConfig.from_yaml({'acceptable_dc': ['wat']})
        assert cfg.acceptable_dc == []

    def test_ephemeral_fields_not_read_from_yaml(self):
        # quickLook is session-only — pinning it in YAML is a no-op.
        cfg = BuyOvhConfig.from_yaml({'quickLook': True})
        assert cfg.quickLook is False

    def test_columnFilters_starts_empty_and_is_per_instance(self):
        a = BuyOvhConfig.from_yaml({})
        b = BuyOvhConfig.from_yaml({})
        a.columnFilters['planCode'] = 'foo'
        assert b.columnFilters == {}


class TestMonitorConfig:

    def test_defaults(self):
        cfg = MonitorConfig.from_yaml({})
        assert cfg.sleepsecs == 60
        assert cfg.email_on is False
        assert cfg.autoBuy == []

    def test_yaml_alias_for_auto_buy(self):
        cfg = MonitorConfig.from_yaml({
            'auto_buy': [{'regex': 'KS-4', 'num': 1,
                          'max_price': 0, 'invoice': False, 'unknown': False}],
        })
        assert len(cfg.autoBuy) == 1
        assert cfg.autoBuy[0]['regex'] == 'KS-4'

    def test_auto_buy_is_deepcopied_from_yaml(self):
        rules = [{'regex': 'KS-4', 'num': 5,
                  'max_price': 0, 'invoice': False, 'unknown': False}]
        cfg = MonitorConfig.from_yaml({'auto_buy': rules})
        cfg.autoBuy[0]['num'] -= 1
        # Original YAML dict is untouched.
        assert rules[0]['num'] == 5

    def test_email_flags_gated_by_email_on_false(self):
        # Flags in YAML are silently dropped when email_on is False/missing,
        # matching the old loadConfigEmail gate.
        cfg = MonitorConfig.from_yaml({
            'email_on': False,
            'email_at_startup': True,
            'email_availability_monitor': 'KS-',
        })
        assert cfg.email_on is False
        assert cfg.email_at_startup is False
        assert cfg.email_availability_monitor == ''

    def test_email_flags_honored_when_email_on_true(self):
        cfg = MonitorConfig.from_yaml({
            'email_on': True,
            'email_at_startup': True,
            'email_availability_monitor': 'KS-',
        })
        assert cfg.email_on is True
        assert cfg.email_at_startup is True
        assert cfg.email_availability_monitor == 'KS-'

    def test_datacenters_alias(self):
        cfg = MonitorConfig.from_yaml({'datacenters': ['gra']})
        assert cfg.acceptable_dc == ['gra']


class TestUnknownKeys:

    def test_clean_config_has_no_unknown_keys(self):
        cf = {'showFee': True, 'datacenters': ['gra'], 'auto_buy': [],
              'APIKey': 'x', 'logFile': 'log.txt', 'email_sender': 'a@b.c'}
        assert warn_unknown_keys(cf) == []

    def test_typo_is_flagged(self, capsys):
        # The bug that started this: showFees (plural) is silently ignored.
        unknown = warn_unknown_keys({'showFees': True, 'showFee': True})
        assert unknown == ['showFees']
        assert 'showFees' in capsys.readouterr().err

    def test_multiple_unknown_keys_sorted(self):
        assert warn_unknown_keys({'zzz': 1, 'aaa': 2}) == ['aaa', 'zzz']

    def test_aliased_field_name_is_unknown(self):
        # YAML must use `datacenters`, not the attribute name `acceptable_dc`.
        assert warn_unknown_keys({'acceptable_dc': []}) == ['acceptable_dc']

    def test_union_of_both_tools_is_accepted(self):
        # A buy_ovh-only key and a monitor_ovh-only key are both "known"
        # because conf.yaml is shared across tools.
        assert 'showFqn' in KNOWN_YAML_KEYS      # buy_ovh only
        assert 'sleepsecs' in KNOWN_YAML_KEYS    # monitor_ovh only
