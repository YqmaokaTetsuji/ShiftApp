'''入力フォーム（基本情報・日ごとの希望・一括入力ダイアログ）の描画。'''
import streamlit as st

from core.calendar_util import build_day_groups, matches_weekday
from core.config import (
    DEPARTMENTS,
    SHIFT_CHOICES,
    TARGET_HOURS_MAX,
    TARGET_HOURS_MIN,
    WEEKDAYS_JA,
)
from core.models import ShiftSubmission
from core.shift_rules import TIME_CHOICE, resolve_request
from ui.state import radio_key, time_key


@st.dialog('シフトの一括入力')
def bulk_input_dialog(day_labels: list) -> None:
    st.write('一括で入力したい曜日や日付を選択してください。')

    selected_dows = st.multiselect('1．曜日でまとめて選択', WEEKDAYS_JA, placeholder='（例：月、水、金）')
    selected_dates = st.multiselect('2．特定の日付を追加で選択', day_labels, placeholder='（例：15日、20日）')

    st.divider()

    shift_type = st.radio('適用するシフトを選択', SHIFT_CHOICES, horizontal=True)
    specific_time = ''
    if shift_type == TIME_CHOICE:
        specific_time = st.text_input('希望時間を入力（例：11-19, 早-15）', key='bulk_time_input')

    if st.button('この内容で一括反映する', type='primary', use_container_width=True):
        # 選択された日付と曜日を合体させる
        target_labels = set(selected_dates)
        for label in day_labels:
            for dow in selected_dows:
                if matches_weekday(label, dow):
                    target_labels.add(label)

        if not target_labels:
            st.error('対象の日付または曜日を1つ以上選択してください。')
            return

        # メイン画面の入力欄（セッションステート）を直接書き換える
        for label in target_labels:
            st.session_state[radio_key(label)] = shift_type
            if shift_type == TIME_CHOICE:
                st.session_state[time_key(label)] = specific_time
        # 画面を更新してダイアログを閉じる
        st.rerun()


def render_basic_info(disabled: bool) -> dict:
    st.subheader('基本情報')
    return {
        'name': st.text_input('1. お名前（フルネーム）', key='input_name', disabled=disabled),
        'employee_code': st.text_input('2. 従業員コード（数字）', key='input_code', disabled=disabled),
        'department': st.selectbox('3. 部門を選択', DEPARTMENTS, key='input_dept', disabled=disabled),
        'target_hours': st.number_input(
            '4. 希望出勤時間（希望がない場合は0を入力してください）',
            min_value=TARGET_HOURS_MIN,
            max_value=TARGET_HOURS_MAX,
            value=0,
            step=1,
            key='input_days',
            disabled=disabled,
        ),
        'remarks': st.text_area(
            '5. 備考（自由記述）',
            key='input_remarks',
            disabled=disabled,
            placeholder='テスト期間や、時間指定の補足などがあれば記入してください。',
        ),
    }


def render_day_inputs(day_labels: list, disabled: bool) -> dict:
    '''日ごとの希望を描画し、{日付ラベル: 記録用の値} を返す。'''
    col_sub, col_btn = st.columns([2, 1])
    with col_sub:
        st.subheader('日ごとの希望')
    with col_btn:
        if st.button('一括入力する', use_container_width=True, disabled=disabled):
            bulk_input_dialog(day_labels)

    tab_titles, day_groups = build_day_groups(day_labels)
    tabs = st.tabs(tab_titles)

    shift_requests = {}
    for i, tab in enumerate(tabs):
        with tab:
            for label in day_groups[i]:
                choice = st.radio(
                    f'**{label}**',
                    SHIFT_CHOICES,
                    horizontal=True,
                    key=radio_key(label),
                    disabled=disabled,
                )
                specific_time = ''
                if choice == TIME_CHOICE:
                    specific_time = st.text_input(
                        f'↳ 【{label}】希望時間を入力（例：11-19, 早-15, 14-L）',
                        key=time_key(label),
                        disabled=disabled,
                    )
                shift_requests[label] = resolve_request(choice, specific_time)
                st.write('---')

    return shift_requests


def build_submission(basic_info: dict, shift_requests: dict) -> ShiftSubmission:
    return ShiftSubmission(
        employee_code=basic_info['employee_code'],
        name=basic_info['name'],
        department=basic_info['department'],
        target_hours=basic_info['target_hours'],
        day_requests=shift_requests,
        remarks=basic_info['remarks'],
    )
