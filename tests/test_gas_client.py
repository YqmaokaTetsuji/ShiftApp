import pytest

from services import gas_client
from services.gas_client import GasError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_on_json=False):
        self.status_code = status_code
        self._payload = payload
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError('not json')
        return self._payload


def test_submit_success(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(url=url, json=json, timeout=timeout)
        return FakeResponse(payload={'status': 'success'})

    monkeypatch.setattr(gas_client.requests, 'post', fake_post)
    gas_client.submit({'名前': '山田'})

    assert captured['url'] == 'https://example.test/exec'
    assert captured['json'] == {'名前': '山田'}
    assert captured['timeout'] == gas_client.POST_TIMEOUT_SEC


@pytest.mark.parametrize(
    'response',
    [
        FakeResponse(status_code=500, payload={'status': 'success'}),
        FakeResponse(payload={'status': 'error'}),
        FakeResponse(raise_on_json=True),
    ],
)
def test_submit_raises_on_bad_response(monkeypatch, response):
    monkeypatch.setattr(gas_client.requests, 'post', lambda *a, **k: response)
    with pytest.raises(GasError):
        gas_client.submit({})


def test_submit_raises_on_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError('network down')

    monkeypatch.setattr(gas_client.requests, 'post', boom)
    with pytest.raises(GasError):
        gas_client.submit({})


def test_fetch_rows_passes_params(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse(payload=[['名前'], ['山田']])

    monkeypatch.setattr(gas_client.requests, 'get', fake_get)
    rows = gas_client.fetch_rows('shift', month=10)

    assert rows == [['名前'], ['山田']]
    assert captured['params'] == {'type': 'shift', 'month': 10}
    assert captured['timeout'] == gas_client.GET_TIMEOUT_SEC


def test_fetch_rows_omits_month_when_none(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params=params)
        return FakeResponse(payload=[])

    monkeypatch.setattr(gas_client.requests, 'get', fake_get)
    gas_client.fetch_rows('member')
    assert captured['params'] == {'type': 'member'}


def test_fetch_rows_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(gas_client.requests, 'get', lambda *a, **k: FakeResponse(status_code=404))
    with pytest.raises(GasError):
        gas_client.fetch_rows('shift', month=10)
