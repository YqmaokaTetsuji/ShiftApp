import datetime

import pytest

from core import config


@pytest.mark.parametrize(
    'today, expected',
    [
        (datetime.date(2026, 1, 15), (2026, 2)),
        (datetime.date(2026, 11, 30), (2026, 12)),
        (datetime.date(2026, 12, 1), (2027, 1)),
        (datetime.date(2026, 12, 31), (2027, 1)),
    ],
)
def test_resolve_target_month(today, expected):
    assert config.resolve_target_month(today) == expected


@pytest.mark.parametrize(
    'hour, expected',
    [(0, True), (3, True), (4, False), (12, False), (23, False)],
)
def test_is_maintenance_time(hour, expected):
    moment = datetime.datetime(2026, 9, 18, hour, 30, tzinfo=config.JST)
    assert config.is_maintenance_time(moment) is expected


def test_get_settings_reads_env():
    settings = config.get_settings()
    assert settings.gas_url == 'https://example.test/exec'
    assert settings.admin_password == 'test-pass'


def test_get_settings_raises_without_secret(monkeypatch):
    '''環境変数も st.secrets も無いときは、起動時に気づけるよう例外にする。'''
    import streamlit as st

    class _NoSecrets:
        def __getitem__(self, key):
            raise KeyError(key)

    # ローカルに .streamlit/secrets.toml があっても結果が変わらないようにする
    monkeypatch.setattr(st, 'secrets', _NoSecrets())
    monkeypatch.delenv('GAS_URL', raising=False)
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    config.get_settings.cache_clear()

    with pytest.raises(RuntimeError, match='gas_url'):
        config.get_settings()
