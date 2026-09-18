import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config  # noqa: E402


def _clear_settings_cache():
    '''get_settings 自体を差し替えているテストもあるので、あれば呼ぶ。'''
    cache_clear = getattr(config.get_settings, 'cache_clear', None)
    if cache_clear is not None:
        cache_clear()


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    '''テスト中は st.secrets ではなく環境変数からシークレットを読ませる。'''
    monkeypatch.setenv('GAS_URL', 'https://example.test/exec')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-pass')
    _clear_settings_cache()
    yield
    _clear_settings_cache()
