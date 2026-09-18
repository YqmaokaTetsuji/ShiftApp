'''Google Apps Script（スプレッドシート）との通信だけを担当する層。

Streamlit には依存しない。失敗は例外 GasError で表現し、
画面への出し方は呼び出し側（UI 層）に任せる。
'''
import requests

from core.config import get_settings

POST_TIMEOUT_SEC = 10
GET_TIMEOUT_SEC = 15


class GasError(Exception):
    '''スプレッドシートとの通信・応答が失敗したことを表す。'''


def submit(payload: dict) -> None:
    '''提出データを1件送信する。失敗時は GasError。'''
    url = get_settings().gas_url
    try:
        response = requests.post(url, json=payload, timeout=POST_TIMEOUT_SEC)
    except Exception as exc:
        raise GasError('スプレッドシートへの送信に失敗しました。') from exc

    if response.status_code != 200:
        raise GasError(f'スプレッドシートが応答しませんでした（HTTP {response.status_code}）。')

    try:
        body = response.json()
    except Exception as exc:
        raise GasError('スプレッドシートの応答を解釈できませんでした。') from exc

    if body.get('status') != 'success':
        raise GasError('スプレッドシート側で保存に失敗しました。')


def fetch_rows(table_type: str, month: int = None) -> list:
    '''シートの内容を「1行目=見出し」の2次元リストとして取得する。'''
    url = get_settings().gas_url
    params = {'type': table_type}
    if month is not None:
        params['month'] = month

    try:
        response = requests.get(url, params=params, timeout=GET_TIMEOUT_SEC)
    except Exception as exc:
        raise GasError('データの取得に失敗しました。') from exc

    if response.status_code != 200:
        raise GasError(f'データの取得に失敗しました（HTTP {response.status_code}）。')

    try:
        return response.json()
    except Exception as exc:
        raise GasError('取得したデータを解釈できませんでした。') from exc
