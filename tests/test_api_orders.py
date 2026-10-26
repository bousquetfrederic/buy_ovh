"""Order-list tests: name and datacenter of dedicated and VPS orders (issue #5)."""
from datetime import datetime, timedelta, timezone

import pytest

import m.api

DEDICATED = {
    'description': 'SYS-1 | Intel Xeon-E 2136 location - centre de données bhs - 1 mois',
    'extension': {'order': {
        'plan': {'code': '24sys01-v1', 'product': {'name': 'eco'}},
        'configurations': [{'label': 'dedicated_datacenter', 'value': 'bhs'},
                           {'label': 'region', 'value': 'canada'}]}},
}
VPS = {
    'description': '12 - 12 months',
    'extension': {'order': {
        'plan': {'code': 'vps-2027-model1', 'product': {'name': 'virtualprivateserver'}},
        'configurations': [{'label': 'region', 'value': 'europe'},
                           {'label': 'vps_datacenter', 'value': 'DE'}]}},
}


class _FakeClient:
    """One detail per order; no 'extension' makes that call fail."""

    def __init__(self, orders):
        self.orders = orders
        self.expiration = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    def get(self, path, **kwargs):
        parts = path.strip('/').split('/')
        if parts == ['me', 'order']:
            return list(range(len(self.orders)))
        order = self.orders[int(parts[2])]
        if parts[3:] == ['status']:
            return 'notPaid'
        if parts[3:] == ['details']:
            return [0]
        if parts[3:] == ['details', '0']:
            return {'domain': '*001', 'detailType': 'DURATION',
                    'description': order['description']}
        if parts[3:] == ['details', '0', 'extension']:
            if 'extension' not in order:
                raise RuntimeError('404')
            return order['extension']
        return {'expirationDate': self.expiration,
                'url': f'https://example.invalid/{parts[2]}'}


def _orders(monkeypatch, orders):
    monkeypatch.setattr(m.api, 'client', _FakeClient(orders))
    now = datetime.now()
    return [(o['description'], o['location'])
            for o in m.api.get_orders_per_status(now - timedelta(days=14), now, ['notPaid'])]


class TestOrderItem:
    def test_dedicated_server(self, monkeypatch):
        assert _orders(monkeypatch, [DEDICATED]) == [('SYS-1', 'bhs')]

    def test_vps_is_named_by_its_plan_and_located_by_its_extension(self, monkeypatch):
        assert _orders(monkeypatch, [DEDICATED, VPS]) == [('SYS-1', 'bhs'),
                                                          ('vps-2027-model1', 'DE')]

    def test_without_extension_falls_back_to_the_description(self, monkeypatch):
        dedicated = {'description': DEDICATED['description']}
        assert _orders(monkeypatch, [dedicated]) == [('SYS-1', 'bhs')]

    def test_description_without_location_does_not_crash(self, monkeypatch):
        assert _orders(monkeypatch, [{'description': 'VPS 1 month'}]) == [('VPS', '')]

    def test_not_logged_in_raises(self, monkeypatch):
        monkeypatch.setattr(m.api, 'client', None)
        with pytest.raises(m.api.NotLoggedIn):
            m.api.get_orders_per_status(datetime.now(), datetime.now(), ['notPaid'])
