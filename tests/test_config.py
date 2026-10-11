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


def test_stores_have_unique_codes():
    codes = [store.code for store in config.STORES]
    assert len(codes) == len(set(codes)) == 8
    assert config.STORES_BY_CODE['246'].name == '練馬高野台駅前'


def test_get_store_settings_reads_env():
    settings = config.get_store_settings('246')
    assert settings.gas_url == 'https://example.test/246/exec'
    assert settings.admin_password == 'test-pass-246'


def test_get_store_settings_is_separate_per_store():
    assert config.get_store_settings('116').gas_url != config.get_store_settings('246').gas_url


def test_get_store_settings_reads_streamlit_secrets(monkeypatch):
    import streamlit as st

    secrets = {'stores': {'176': {'gas_url': 'https://secret.test/176', 'admin_password': 'pw176'}}}
    monkeypatch.setattr(st, 'secrets', secrets)
    monkeypatch.delenv('GAS_URL_176')
    monkeypatch.delenv('ADMIN_PASSWORD_176')
    config.get_store_settings.cache_clear()

    settings = config.get_store_settings('176')
    assert settings.gas_url == 'https://secret.test/176'
    assert settings.admin_password == 'pw176'


def test_get_store_settings_rejects_unknown_store():
    with pytest.raises(RuntimeError, match='登録されていません'):
        config.get_store_settings('999')


def test_get_store_settings_raises_without_secret(monkeypatch):
    '''環境変数も st.secrets も無いときは、入力前に気づけるよう例外にする。'''
    import streamlit as st

    # ローカルに .streamlit/secrets.toml があっても結果が変わらないようにする
    monkeypatch.setattr(st, 'secrets', {})
    monkeypatch.delenv('GAS_URL_116')
    monkeypatch.delenv('ADMIN_PASSWORD_116')
    config.get_store_settings.cache_clear()

    with pytest.raises(RuntimeError, match=r'店舗 116 の設定「gas_url」が見つかりません'):
        config.get_store_settings('116')
