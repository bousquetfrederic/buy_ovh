"""Unit tests for m.conf — the typed config layer.

These tests cover the from_yaml / apply_state_overlay / mirrored_state
round-trip that used to be scattered across buy_ovh's loadConfigMain
function, module globals, MIRRORED_KEYS, and the m.state overlay.
"""
from m.conf import BuyOvhConfig, MonitorConfig, MIRRORED_KEYS


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


class TestStateOverlay:

    def test_overlay_applies_mirrored_keys(self):
        cfg = BuyOvhConfig.from_yaml({})
        cfg.apply_state_overlay({
            'showCpu': False,
            'fakeBuy': False,
            'months': 12,
        })
        assert cfg.showCpu is False
        assert cfg.fakeBuy is False
        assert cfg.months == 12

    def test_overlay_ignores_non_mirrored_keys(self):
        cfg = BuyOvhConfig.from_yaml({})
        cfg.apply_state_overlay({
            'filterName': 'KS-',  # not mirrored — should be ignored
            'APIEndpoint': 'ovh-ca',  # ditto
        })
        assert cfg.filterName == ''
        assert cfg.APIEndpoint == 'ovh-eu'

    def test_overlay_tolerates_unknown_keys(self):
        # Drift across versions shouldn't crash — saved state may carry
        # keys we don't know about.
        cfg = BuyOvhConfig.from_yaml({})
        cfg.apply_state_overlay({'some_future_flag': True})
        # No exception; nothing set.
        assert not hasattr(cfg, 'some_future_flag')

    def test_mirrored_state_round_trip(self):
        cfg = BuyOvhConfig.from_yaml({})
        cfg.showFqn = True
        cfg.addVAT = True
        cfg.months = 12
        state = cfg.mirrored_state()
        # All mirrored keys are in the dict.
        assert set(state) == set(MIRRORED_KEYS)
        # Only mirrored values are present.
        assert state['showFqn'] is True
        assert state['addVAT'] is True
        assert state['months'] == 12
        assert 'filterName' not in state
        assert 'quickLook' not in state


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
