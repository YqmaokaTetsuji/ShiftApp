'''アプリ全体の設定値と、対象年月・シークレットの解決。

この層は Streamlit に依存しない。シークレットだけは、Streamlit Cloud 上では
st.secrets から、ローカルやテストでは環境変数から読めるようにしている。
'''
import datetime
import functools
import os
from dataclasses import dataclass

JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

# 部門の指定
DEPARTMENT_PLACEHOLDER = '選択してください'
DEPARTMENTS = [DEPARTMENT_PLACEHOLDER, '季節AV', '家電', '情報', '通信']

# 日ごとの希望として選べる選択肢
SHIFT_CHOICES = ['希望なし', '休', '早', '遅', '時間指定', '有給']

WEEKDAYS_JA = ['月', '火', '水', '木', '金', '土', '日']

# メンテナンス時間帯（この時間はフォームを閉じる）
MAINTENANCE_START_HOUR = 1
MAINTENANCE_END_HOUR = 4

# 希望出勤時間の入力レンジ
TARGET_HOURS_MIN = 0
TARGET_HOURS_MAX = 120


def now_jst() -> datetime.datetime:
    '''現在時刻（JST）'''
    return datetime.datetime.now(JST)


def resolve_target_month(today: datetime.date = None) -> tuple:
    '''提出対象となる「翌月」の (年, 月) を返す。12月なら翌年1月。'''
    if today is None:
        today = now_jst().date()
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def is_maintenance_time(moment: datetime.datetime = None) -> bool:
    '''メンテナンス時間帯かどうか'''
    if moment is None:
        moment = now_jst()
    return MAINTENANCE_START_HOUR <= moment.hour < MAINTENANCE_END_HOUR


def excel_file_name(target_month: int) -> str:
    return f'【店長確認用】{target_month}月シフト提出状況.xlsx'


def excel_sheet_name(target_month: int) -> str:
    return f'{target_month}月シフト提出'


@dataclass(frozen=True)
class Settings:
    '''外部から注入される秘匿値'''
    gas_url: str
    admin_password: str


def _read_secret(key: str) -> str:
    '''環境変数を優先し、無ければ st.secrets を見る。

    テストやローカル実行では環境変数だけで動かせるようにするため、
    streamlit の import はこの関数の中に閉じ込めている。
    '''
    value = os.environ.get(key.upper())
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets[key]
    except Exception as exc:
        raise RuntimeError(
            f'設定「{key}」が見つかりません。'
            f'環境変数 {key.upper()} か .streamlit/secrets.toml を設定してください。'
        ) from exc


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        gas_url=_read_secret('gas_url'),
        admin_password=_read_secret('admin_password'),
    )
