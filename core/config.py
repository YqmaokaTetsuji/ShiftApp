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


def shift_month_label(target_year: int, target_month: int) -> str:
    '''スプレッドシートの「対象月」列とシート名に使う年月表記（例: 2026年01月）。

    GAS 側はこの値に「シフト」を付けたものをシート名にする（例: 2026年01月シフト）。
    '''
    return f'{target_year}年{target_month:02d}月'


def excel_file_name(target_year: int, target_month: int) -> str:
    return f'【店長確認用】{shift_month_label(target_year, target_month)}シフト提出状況.xlsx'


def excel_sheet_name(target_year: int, target_month: int) -> str:
    return f'{shift_month_label(target_year, target_month)}シフト提出'


@dataclass(frozen=True)
class Store:
    '''店舗。code は Secrets のキー（[stores.<code>]）にも使う。'''
    code: str
    name: str


# プルダウンに並べる店舗（この順で表示する）
STORE_PLACEHOLDER = '選択してください'
STORES = (
    Store('116', '池袋東部'),
    Store('176', '西台'),
    Store('178', '西友成増'),
    Store('180', 'イトーヨーカドー赤羽'),
    Store('206', '板橋前野町'),
    Store('227', '練馬駅前'),
    Store('236', 'リヴィンオズ大泉'),
    Store('246', '練馬高野台駅前'),
)
STORES_BY_CODE = {store.code: store for store in STORES}


@dataclass(frozen=True)
class StoreSettings:
    '''店舗ごとに外部から注入される秘匿値'''
    gas_url: str
    admin_password: str


def _read_store_secret(store_code: str, key: str) -> str:
    '''環境変数を優先し、無ければ st.secrets の [stores.<店舗コード>] を見る。

    テストやローカル実行では環境変数（例: GAS_URL_246）だけで動かせるようにするため、
    streamlit の import はこの関数の中に閉じ込めている。
    '''
    env_key = f'{key.upper()}_{store_code}'
    value = os.environ.get(env_key)
    if value:
        return value
    try:
        import streamlit as st

        value = st.secrets['stores'][store_code][key]
    except Exception as exc:
        raise RuntimeError(
            f'店舗 {store_code} の設定「{key}」が見つかりません。'
            f'このまま入力せずに、練馬高野台 箭内に連絡してください。'
        ) from exc
    if not value:
        raise RuntimeError(f'店舗 {store_code} の設定「{key}」が空です。')
    return value


@functools.lru_cache(maxsize=None)
def get_store_settings(store_code: str) -> StoreSettings:
    '''店舗の保存先とパスワード。未登録の店舗コードや設定漏れは RuntimeError。'''
    if store_code not in STORES_BY_CODE:
        raise RuntimeError(f'店舗コード「{store_code}」は登録されていません。')
    return StoreSettings(
        gas_url=_read_store_secret(store_code, 'gas_url'),
        admin_password=_read_store_secret(store_code, 'admin_password'),
    )
