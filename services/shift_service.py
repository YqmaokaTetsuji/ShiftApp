'''ユースケース層：提出、取得、Excel 用の整形、提出状況の照合。

Streamlit に依存しないので、将来 FastAPI などから呼び出すこともできる。
'''
import pandas as pd

from core.config import DEPARTMENTS, DEPARTMENT_PLACEHOLDER
from core.models import ShiftSubmission
from services import gas_client
from services.gas_client import GasError  # 呼び出し側の import を1箇所にまとめる

__all__ = [
    'GasError',
    'submit_shift',
    'fetch_shifts',
    'fetch_members',
    'build_export_dataframe',
    'build_submission_status',
]

# Excel 出力から外す列
EXPORT_DROP_COLUMNS = ['対象月', '提出日時']

STATUS_SUBMITTED = '提出済'
STATUS_PENDING = '未提出'

MEMBER_REQUIRED_COLUMNS = ['従業員コード', '名前', '部門']


def submit_shift(submission: ShiftSubmission, target_month: int) -> None:
    '''シフト希望を1件提出する。失敗時は GasError。

    内容から決まる request_id を添えて送る。同じ内容が二重に届いた場合は
    GAS 側が 2 件目以降を捨てるので、連打やリトライで行が増えない。
    '''
    payload = submission.to_payload(target_month)
    payload['request_id'] = submission.request_id(target_month)
    gas_client.submit(payload)


def _rows_to_dataframe(rows: list) -> pd.DataFrame:
    '''「1行目=見出し」の2次元リストを DataFrame に変換する。空なら空の DataFrame。'''
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df.columns = df.columns.str.strip()
    return df


def fetch_shifts(target_month: int) -> pd.DataFrame:
    '''対象月の提出済みシフトを取得する。未提出のみなら空の DataFrame。'''
    return _rows_to_dataframe(gas_client.fetch_rows('shift', month=target_month))


def fetch_members() -> pd.DataFrame:
    '''名簿タブを取得する。'''
    return _rows_to_dataframe(gas_client.fetch_rows('member'))


def _normalize_codes(series: pd.Series) -> pd.Series:
    '''スプレッドシート由来の「1234.0」のような数値化を文字列コードへ戻す。'''
    return series.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()


def build_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    '''Excel 出力用に、不要列の削除・部門順の並び替え・部門間の空行挿入を行う。'''
    if df.empty:
        return df

    df = df.copy()

    drop_cols = [c for c in EXPORT_DROP_COLUMNS if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    if '部門' not in df.columns or '従業員コード' not in df.columns:
        return df

    # 部門順 → 従業員コード順に並び替え
    dept_order = {dept: i for i, dept in enumerate(DEPARTMENTS) if dept != DEPARTMENT_PLACEHOLDER}
    df['_sort_key'] = df['部門'].map(lambda x: dept_order.get(x, 99))
    df['_code_num'] = pd.to_numeric(df['従業員コード'], errors='coerce').fillna(999999)
    df = df.sort_values(['_sort_key', '_code_num']).drop(columns=['_sort_key', '_code_num'])

    # 部門が切り替わるタイミングで空白行を挿入
    new_rows = []
    current_dept = None
    for _, row in df.iterrows():
        if current_dept is not None and current_dept != row['部門']:
            new_rows.append({col: '' for col in df.columns})
        new_rows.append(row.to_dict())
        current_dept = row['部門']

    return pd.DataFrame(new_rows, columns=df.columns)


def build_submission_status(df_members: pd.DataFrame, df_shifts: pd.DataFrame) -> pd.DataFrame:
    '''名簿と提出済みシフトを突き合わせ、提出済/未提出の一覧を作る。

    名簿が空、または必要な列が無い場合は ValueError。
    '''
    if df_members.empty:
        raise ValueError('スプレッドシートの「名簿」タブにスタッフのデータが登録されていません。（2行目以降が空です）')

    if not set(MEMBER_REQUIRED_COLUMNS).issubset(df_members.columns):
        raise ValueError('スプレッドシートの「名簿」タブに「従業員コード」「名前」「部門」の列が見つかりません。')

    df_status = df_members[MEMBER_REQUIRED_COLUMNS].copy()
    df_status['従業員コード'] = _normalize_codes(df_status['従業員コード'])

    submitted_codes = []
    if not df_shifts.empty and '従業員コード' in df_shifts.columns:
        submitted_codes = _normalize_codes(df_shifts['従業員コード']).tolist()

    df_status['提出状況'] = df_status['従業員コード'].apply(
        lambda x: STATUS_SUBMITTED if x in submitted_codes else STATUS_PENDING
    )
    # 「未提出」が先頭に来るように並べる
    return df_status.sort_values('提出状況', ascending=False)
