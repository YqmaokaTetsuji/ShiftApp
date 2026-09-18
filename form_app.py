'''シフト希望提出フォーム（Streamlit エントリポイント）。

画面の流れだけを持ち、ロジックは core / services / exporters に委譲する。
'''
import streamlit as st

from core.calendar_util import build_day_labels
from core.config import get_settings, is_maintenance_time, now_jst, resolve_target_month
from services.shift_service import GasError, submit_shift
from ui import admin_view
from ui.form_view import build_submission, render_basic_info, render_day_inputs
from ui.preview import styled_calendar
from ui.state import init_day_inputs, init_session_state, is_input_disabled

st.set_page_config(page_title='シフト希望提出フォーム', layout='wide')

HIDE_STREAMLIT_STYLE = '''
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
'''
st.markdown(HIDE_STREAMLIT_STYLE, unsafe_allow_html=True)

# 設定は起動時に検証する。提出ボタンを押した瞬間に初めて発覚すると、
# 入力し終えた利用者の内容がまるごと無駄になるため。
try:
    get_settings()
except RuntimeError as exc:
    st.error(
        '**アプリの設定が読み込めませんでした**\n\n'
        f'{exc}\n\n'
        '恐れ入りますが、このまま入力せずに管理者へご連絡ください。'
    )
    st.stop()

TARGET_YEAR, TARGET_MONTH = resolve_target_month()
num_days, day_labels = build_day_labels(TARGET_YEAR, TARGET_MONTH)

init_session_state()
init_day_inputs(day_labels)
input_disabled = is_input_disabled()

# --- タイトル 管理者パネル ---
col_title, col_admin = st.columns([4, 1])
with col_title:
    st.markdown(f'### {TARGET_YEAR}年{TARGET_MONTH}月分 シフト希望提出フォーム')
    st.write(
        '時間の希望がある日だけ選択してください。希望がない日は「希望なし」のままでOKです。\n\n'
        'システムの不具合がありましたら、不具合の画面の写真とともに、箭内にご連絡ください。'
    )
with col_admin:
    admin_view.render(TARGET_MONTH)

st.divider()

# メンテナンス期間中は表示しないようにする
if is_maintenance_time(now_jst()):
    st.error(
        '**現在システムメンテナンス中です**\n\n'
        '毎日 **00:00 〜 04:00** はメンテナンスのためご利用いただけません。\n'
        '恐れ入りますが、この時間を避けて再度アクセスしてください。'
    )
    st.stop()

# --- 入力エリア ---
col_left, col_right = st.columns([1, 2])

with col_left:
    basic_info = render_basic_info(input_disabled)

with col_right:
    shift_requests = render_day_inputs(day_labels, input_disabled)

submission = build_submission(basic_info, shift_requests)

st.divider()

# --- 提出処理 ---
def _back_to_edit() -> None:
    st.session_state.submit_error = ''
    st.session_state.confirm_mode = False


def _request_submit() -> None:
    '''提出ボタンの on_click コールバック。印をつけるだけで、ここでは送信しない。

    ここで通信まで済ませてしまうと、押してから通信が終わるまで
    画面が描き変わらず「固まった」ように見える（GAS は数秒かかる）。
    いったん描画に戻して「送信中」を出してから送る。
    '''
    if st.session_state.is_processing or st.session_state.is_submitted:
        return
    st.session_state.submit_error = ''
    st.session_state.is_processing = True


def _do_submit(submission, target_month: int) -> None:
    '''送信し、その結果を状態に書き込む。

    二重送信の判定は is_processing のようなフラグではなく、
    **提出内容から決まる request_id** で行う。連打すると再実行が何度も走り、
    フラグの更新が間に合わない瞬間ができてしまうため、
    「この内容はもう送った」という事実そのものを見て止める。

    なお、この関数は st.* を一切呼ばない。Streamlit は st.* を呼んだ地点で
    保留中の再実行に切り替わるので、通信と状態更新の間に st.* があると、
    そこで実行が打ち切られて同じ内容がもう一度飛ぶ。
    '''
    request_id = submission.request_id(target_month)

    # すでにこのセッションで送り終えた内容なら、通信せずに完了として扱う
    if request_id in st.session_state.sent_request_ids:
        st.session_state.submit_error = ''
        st.session_state.is_submitted = True
        st.session_state.confirm_mode = False
        st.session_state.is_processing = False
        return

    # 送る「前」に記録するのが要点。送信直後に実行が打ち切られても、
    # 次の実行で同じ内容がもう一度飛ぶことがない。
    st.session_state.sent_request_ids.add(request_id)
    try:
        submit_shift(submission, target_month)
    except GasError:
        # 届かなかったので再試行を許す。もし実は届いていた場合は、
        # 同じ request_id なので GAS 側の重複排除で弾かれる。
        st.session_state.sent_request_ids.discard(request_id)
        st.session_state.submit_error = (
            '【通信エラー】Googleスプレッドシートへの送信に失敗しました。'
            'そのままもう一度お試しいただくか、管理者へ連絡してください。'
        )
    else:
        st.session_state.submit_error = ''
        st.session_state.is_submitted = True
        st.session_state.confirm_mode = False
    finally:
        st.session_state.is_processing = False


# --- プレビュー ボタンエリア ---
# 画面下部はまるごと差し替えられる置き場にする。こうしないと、送信中に
# 前の描画（確定ボタン）がブラウザ上に残ったままになり、通信が終わるまで
# 押せてしまう。st.empty() なら書き込んだ瞬間に前の中身が消える。
result_area = st.empty()

if st.session_state.is_submitted:
    with result_area.container():
        st.success(f'{submission.name}さん、シフトの提出が完了しました。')
        st.info('※修正が必要な場合は店長または箭内へ連絡してください。')
        st.markdown('#### 提出されたシフト内容')
        st.table(styled_calendar(TARGET_YEAR, TARGET_MONTH, day_labels, shift_requests))

elif st.session_state.is_processing:
    # 送信中はボタンを一切描画しない。押せるものが無ければ連打のしようがない。
    with result_area.container():
        st.info('送信中です。このままお待ちください（画面を閉じたり更新したりしないでください）。')
        with st.spinner('クラウドにシフトを送信しています...'):
            _do_submit(submission, TARGET_MONTH)
    st.rerun()

elif st.session_state.confirm_mode:
    with result_area.container():
        st.warning('以下の内容で確定してよろしいですか？')
        st.markdown('#### シフト希望プレビュー')
        st.table(styled_calendar(TARGET_YEAR, TARGET_MONTH, day_labels, shift_requests))

        if submission.remarks:
            st.markdown('**【備考】**')
            st.write(submission.remarks)

        if st.session_state.submit_error:
            st.error(st.session_state.submit_error)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.button('戻って修正する', use_container_width=True, on_click=_back_to_edit)
        with col_btn2:
            st.button(
                'この内容で確定・提出する',
                type='primary',
                use_container_width=True,
                on_click=_request_submit,
            )

else:
    with result_area.container():
        st.markdown('#### ライブプレビュー')
        st.table(styled_calendar(TARGET_YEAR, TARGET_MONTH, day_labels, shift_requests))
        st.write('')
        if st.button('確認画面へ進む', type='primary', use_container_width=True):
            errors = submission.validate()
            for message in errors:
                st.error(message)
            if not errors:
                st.session_state.confirm_mode = True
                st.rerun()
