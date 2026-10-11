import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config  # noqa: E402


def _clear_settings_cache():
    '''get_store_settings 自体を差し替えているテストもあるので、あれば呼ぶ。'''
    cache_clear = getattr(config.get_store_settings, 'cache_clear', None)
    if cache_clear is not None:
        cache_clear()


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    '''テスト中は st.secrets ではなく環境変数から、全店舗分のシークレットを読ませる。'''
    for store in config.STORES:
        monkeypatch.setenv(f'GAS_URL_{store.code}', f'https://example.test/{store.code}/exec')
        monkeypatch.setenv(f'ADMIN_PASSWORD_{store.code}', f'test-pass-{store.code}')
    _clear_settings_cache()
    yield
    _clear_settings_cache()
