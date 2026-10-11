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


def _select_store(app, code='246'):
    app.selectbox(key='input_store').set_value(code)
    app.run()


def test_initial_render_asks_for_store_first(app):
    app.run()
    assert not app.exception
    assert any('シフト希望提出フォーム' in md.value for md in app.markdown)
    assert any('店舗を選択' in i.value for i in app.info)
    # 店舗を選ぶまで入力欄は出さない
    assert not any(t.key == 'input_name' for t in app.text_input)


def test_selecting_store_shows_the_form(app):
    app.run()
    _select_store(app)
    assert not app.exception
    assert any(t.key == 'input_name' for t in app.text_input)
    # ライブプレビューが出ている
    assert any('ライブプレビュー' in md.value for md in app.markdown)


def test_store_select_lists_store_names(app):
    app.run()
    select = app.selectbox(key='input_store')
    assert '練馬高野台駅前' in select.options
    assert '池袋東部' in select.options


def test_validation_blocks_empty_submission(app):
    app.run()
    _select_store(app)

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
    _select_store(app)
    app.text_input(key='input_name').set_value('山田 太郎')
    app.text_input(key='input_code').set_value('1234')
    app.selectbox(key='input_dept').set_value('家電')
    app.run()

    proceed = [b for b in app.button if b.label == '確認画面へ進む'][0]
    proceed.click().run()

    assert not app.exception
    assert app.session_state['confirm_mode'] is True
    assert any('シフト希望プレビュー' in md.value for md in app.markdown)
    # 提出先の店舗名を確認画面に出す
    assert any('練馬高野台駅前' in w.value for w in app.warning)
    # 確認画面では店舗を変えられない
    assert app.selectbox(key='input_store').disabled


def test_missing_settings_stops_the_form_before_input(app, monkeypatch):
    '''店舗の設定が読めないときは、入力させる前に止める。'''
    import core.config as config

    def raise_missing(store_code):
        raise RuntimeError(f'店舗 {store_code} の設定「gas_url」が見つかりません。')

    # app フィクスチャで昼の時刻に固定しておかないと、メンテナンス時間帯
    # （＝毎晩 02:00 の自動反映のとき）に先に止まってテストが落ちる
    monkeypatch.setattr(config, 'get_store_settings', raise_missing)
    at = app
    at.run()
    _select_store(at, '116')

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


def _goto_confirm(app, store_code='246'):
    app.run()
    _select_store(app, store_code)
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
    monkeypatch.setattr(gas_client, 'submit', lambda url, payload: sent.append((url, payload)))

    _goto_confirm(app, '180').click().run()

    assert not app.exception
    assert len(sent) == 1
    # 選んだ店舗のスプレッドシートへ送られる
    assert sent[0][0] == 'https://example.test/180/exec'
    assert app.session_state['is_submitted'] is True
    assert app.session_state['is_processing'] is False
    # 確定ボタン自体が描画されなくなるので、連打しようがない
    assert not any(b.label == 'この内容で確定・提出する' for b in app.button)


def test_submit_failure_keeps_confirm_screen_with_error(app, monkeypatch):
    '''通信に失敗したら確認画面に留まり、同じ内容のまま再試行できる。'''
    from services import gas_client

    def boom(url, payload):
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
    monkeypatch.setattr(gas_client, 'submit', lambda url, payload: sent.append(payload))

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

    def flaky(url, payload):
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


@pytest.mark.parametrize('password, unlocked', [('test-pass-246', True), ('test-pass-116', False)])
def test_admin_menu_uses_selected_store_password(app, password, unlocked):
    '''店長パネルは選択中の店舗のパスワードでだけ開く（他店のパスワードでは開かない）。'''
    app.run()
    _select_store(app, '246')
    app.text_input(key='admin_pass_246').set_value(password)
    app.run()

    assert not app.exception
    assert any(b.label == '最新のExcelを作成する' for b in app.button) is unlocked
