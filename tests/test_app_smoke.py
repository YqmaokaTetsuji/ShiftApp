'''画面全体が例外なく描画できるかのスモークテスト（Streamlit の AppTest を使用）。'''
import datetime
import os

import pytest

pytest.importorskip('streamlit')

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'form_app.py')


@pytest.fixture
def app(monkeypatch):
    # メンテナンス時間帯に当たると st.stop() してしまうため、昼の時刻に固定する
    import core.config as config

    monkeypatch.setattr(config, 'now_jst', lambda: datetime.datetime(2026, 9, 18, 12, 0, tzinfo=config.JST))
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    return at


def test_initial_render_has_no_exception(app):
    app.run()
    assert not app.exception
    assert any('シフト希望提出フォーム' in md.value for md in app.markdown)
    # ライブプレビューが出ている
    assert any('ライブプレビュー' in md.value for md in app.markdown)


def test_validation_blocks_empty_submission(app):
    app.run()

    # 「確認画面へ進む」ボタンを押す
    proceed = [b for b in app.button if b.label == '確認画面へ進む'][0]
    proceed.click().run()

    assert not app.exception
    messages = [e.value for e in app.error]
    assert any('お名前' in m for m in messages)
    assert any('部門' in m for m in messages)
    assert any('従業員コード' in m for m in messages)


def test_filled_form_moves_to_confirm_screen(app):
    app.run()
    app.text_input(key='input_name').set_value('山田 太郎')
    app.text_input(key='input_code').set_value('1234')
    app.selectbox(key='input_dept').set_value('家電')
    app.run()

    proceed = [b for b in app.button if b.label == '確認画面へ進む'][0]
    proceed.click().run()

    assert not app.exception
    assert app.session_state['confirm_mode'] is True
    assert any('シフト希望プレビュー' in md.value for md in app.markdown)


def test_missing_settings_stops_the_form_before_input(monkeypatch):
    '''設定が読めないときは、入力させる前に止める。'''
    import core.config as config

    def raise_missing():
        raise RuntimeError('設定「gas_url」が見つかりません。')

    monkeypatch.setattr(config, 'get_settings', raise_missing)
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    assert not at.exception
    assert any('設定が読み込めませんでした' in e.value for e in at.error)
    # 入力欄は描画されない（入力し終えてから失敗させない）
    assert not any(t.key == 'input_name' for t in at.text_input)


def test_maintenance_window_stops_the_form(monkeypatch):
    import core.config as config

    monkeypatch.setattr(config, 'now_jst', lambda: datetime.datetime(2026, 9, 18, 2, 0, tzinfo=config.JST))
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    assert not at.exception
    assert any('メンテナンス中' in e.value for e in at.error)
    # 入力欄は描画されない
    assert not any(t.key == 'input_name' for t in at.text_input)


def _goto_confirm(app):
    app.run()
    app.text_input(key='input_name').set_value('山田 太郎')
    app.text_input(key='input_code').set_value('1234')
    app.selectbox(key='input_dept').set_value('家電')
    app.run()
    [b for b in app.button if b.label == '確認画面へ進む'][0].click().run()
    return [b for b in app.button if b.label == 'この内容で確定・提出する'][0]


def test_submit_sends_once_and_locks_the_button(app, monkeypatch):
    '''提出後は確定ボタンが消え、それ以上送れない。'''
    from services import gas_client

    sent = []
    monkeypatch.setattr(gas_client, 'submit', lambda payload: sent.append(payload))

    _goto_confirm(app).click().run()

    assert not app.exception
    assert len(sent) == 1
    assert app.session_state['is_submitted'] is True
    assert app.session_state['is_processing'] is False
    # 確定ボタン自体が描画されなくなるので、連打しようがない
    assert not any(b.label == 'この内容で確定・提出する' for b in app.button)


def test_submit_failure_keeps_confirm_screen_with_error(app, monkeypatch):
    '''通信に失敗したら確認画面に留まり、同じ内容のまま再試行できる。'''
    from services import gas_client

    def boom(payload):
        raise gas_client.GasError('ng')

    monkeypatch.setattr(gas_client, 'submit', boom)

    _goto_confirm(app).click().run()

    assert not app.exception
    assert app.session_state['is_submitted'] is False
    assert app.session_state['confirm_mode'] is True
    assert app.session_state['is_processing'] is False
    assert any('通信エラー' in e.value for e in app.error)
    assert any(b.label == 'この内容で確定・提出する' for b in app.button)


def test_repeated_submits_send_only_once(app, monkeypatch):
    '''連打で起きる「送信フラグが立ったまま再実行が何度も走る」状態を再現する。

    フラグの更新が間に合わなくても、同じ内容が2回 GAS へ飛んではいけない。
    '''
    from services import gas_client

    sent = []
    monkeypatch.setattr(gas_client, 'submit', lambda payload: sent.append(payload))

    _goto_confirm(app).click().run()
    assert len(sent) == 1

    # 連打で積まれた再実行が、送信中の状態のまま何度も走った場合を模す
    for _ in range(5):
        app.session_state['is_processing'] = True
        app.session_state['is_submitted'] = False
        app.session_state['confirm_mode'] = True
        app.run()

    assert not app.exception
    assert len(sent) == 1
    assert app.session_state['is_submitted'] is True


def test_retry_after_failure_is_allowed(app, monkeypatch):
    '''本当に届かなかった場合は、同じ内容でも再試行できる。'''
    from services import gas_client

    sent = []

    def flaky(payload):
        if not sent:
            sent.append(payload)
            raise gas_client.GasError('ng')
        sent.append(payload)

    monkeypatch.setattr(gas_client, 'submit', flaky)

    _goto_confirm(app).click().run()
    assert app.session_state['is_submitted'] is False

    [b for b in app.button if b.label == 'この内容で確定・提出する'][0].click().run()

    assert not app.exception
    assert len(sent) == 2
    assert app.session_state['is_submitted'] is True
    # 再試行でも同じ ID なので、実は届いていた場合は GAS 側が弾く
    assert sent[0]['request_id'] == sent[1]['request_id']
