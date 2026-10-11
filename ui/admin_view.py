'''店長専用メニューの描画。データ取得・整形・Excel 生成は services / exporters に委譲する。'''
import hmac

import streamlit as st

from core.config import excel_file_name, excel_sheet_name, get_store_settings
from exporters.excel import build_shift_workbook
from services.shift_service import (
    GasError,
    STATUS_PENDING,
    build_export_dataframe,
    build_submission_status,
    fetch_members,
    fetch_shifts,
)

UNSUBMITTED_ROW_STYLE = 'background-color: #FFE6E6'


def _render_excel_download(target_month: int, store_code: str) -> None:
    st.markdown('#### シフトデータのダウンロード')
    st.write('スプレッドシートの最新データを、見やすく色付けされたExcelファイルとして保存します。')

    if not st.button('最新のExcelを作成する', use_container_width=True):
        return

    with st.spinner('クラウドからデータを取得＆Excelを装飾中...'):
        try:
            df_shifts = fetch_shifts(target_month, store_code)
        except GasError as exc:
            st.error(f'通信エラーが発生しました: {exc}')
            return

        if df_shifts.empty:
            st.info('まだ誰もシフトを提出していません。')
            return

        df_export = build_export_dataframe(df_shifts)
        excel_data = build_shift_workbook(df_export, excel_sheet_name(target_month))

    st.success('✅ Excel準備完了！')
    st.download_button(
        label='Excelファイル（.xlsx）を保存',
        data=excel_data,
        file_name=excel_file_name(target_month),
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        use_container_width=True,
        type='primary',
    )


def _highlight_unsubmitted(row):
    style = UNSUBMITTED_ROW_STYLE if row['提出状況'] == STATUS_PENDING else ''
    return [style] * len(row)


def _render_submission_status(target_month: int, store_code: str) -> None:
    st.markdown('#### 提出状況一覧（未提出チェック）')

    with st.spinner('名簿と提出状況を照合中...'):
        try:
            df_members = fetch_members(store_code)
            df_shifts = fetch_shifts(target_month, store_code)
            df_status = build_submission_status(df_members, df_shifts)
        except GasError as exc:
            st.error(f'読み込みエラー: {exc}')
            return
        except ValueError as exc:
            st.warning(str(exc))
            return

    st.dataframe(
        df_status.style.apply(_highlight_unsubmitted, axis=1),
        hide_index=True,
        use_container_width=True,
    )


def render(target_month: int, store_code: str = None) -> None:
    '''店長専用メニュー。パスワードは選択中の店舗のものと照合する。'''
    with st.popover('店長専用メニュー', use_container_width=True):
        if not store_code:
            st.info('先に「店舗を選択」で店舗を選んでください。')
            return

        try:
            settings = get_store_settings(store_code)
        except RuntimeError as exc:
            st.error(str(exc))
            return

        admin_pass = st.text_input('店長用パスワードを入力', type='password', key=f'admin_pass_{store_code}')
        if not admin_pass or not hmac.compare_digest(admin_pass, settings.admin_password):
            return

        st.write('---')
        _render_excel_download(target_month, store_code)
        st.write('---')
        _render_submission_status(target_month, store_code)
