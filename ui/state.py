'''セッションステートの初期化とキー命名を1箇所にまとめる。'''
import streamlit as st

_FLAGS = {
    'confirm_mode': False,
    'is_submitted': False,
    'excel_warning': False,
    'is_processing': False,
    'submit_error': '',
}


def radio_key(label: str) -> str:
    return f'radio_{label}'


def time_key(label: str) -> str:
    return f'time_{label}'


def init_session_state() -> None:
    '''状態の初期化'''
    for key, default in _FLAGS.items():
        if key not in st.session_state:
            st.session_state[key] = default
    # 送信済みの内容を覚えておくための集合。_FLAGS に混ぜると
    # 同じ set が全セッションで共有されてしまうので、ここで個別に作る。
    if 'sent_request_ids' not in st.session_state:
        st.session_state.sent_request_ids = set()


def init_day_inputs(day_labels: list) -> None:
    '''あらかじめ全日程の変数を希望なしとして作成（一括入力のため）'''
    for label in day_labels:
        if radio_key(label) not in st.session_state:
            st.session_state[radio_key(label)] = '希望なし'
        if time_key(label) not in st.session_state:
            st.session_state[time_key(label)] = ''


def is_input_disabled() -> bool:
    return (
        st.session_state.confirm_mode
        or st.session_state.is_submitted
        or st.session_state.is_processing
    )
