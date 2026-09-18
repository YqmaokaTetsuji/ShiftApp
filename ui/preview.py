'''シフト希望のカレンダープレビュー描画。'''
import pandas as pd

from core.calendar_util import build_week_matrix
from core.shift_rules import is_day_off

CALENDAR_COLUMNS = ['日', '月', '火', '水', '木', '金', '土']

SATURDAY_STYLE = 'background-color: #E6F2FF'
SUNDAY_STYLE = 'background-color: #FFE6E6'
OFF_STYLE = 'color: #FF0000; font-weight: bold'


def _build_calendar_frame(year: int, month: int, day_labels: list, shift_requests: dict) -> pd.DataFrame:
    cal_data = []
    for week in build_week_matrix(year, month):
        week_data = []
        for d in week:
            if d == 0:
                week_data.append('')
            else:
                req = shift_requests.get(day_labels[d - 1], '')
                display_text = '出' if req == '' else req
                week_data.append(f'{d}日: {display_text}')
        cal_data.append(week_data)

    return pd.DataFrame(cal_data, columns=CALENDAR_COLUMNS)


def _style_cells(data: pd.DataFrame) -> pd.DataFrame:
    '''日によってセルの設定を変える'''
    styles = pd.DataFrame('', index=data.index, columns=data.columns)
    for row in data.index:
        for col in data.columns:
            val = str(data.loc[row, col])
            css = []
            if col == '土':
                css.append(SATURDAY_STYLE)
            elif col == '日':
                css.append(SUNDAY_STYLE)
            if is_day_off(val):
                css.append(OFF_STYLE)
            styles.loc[row, col] = '; '.join(css)
    return styles


def styled_calendar(year: int, month: int, day_labels: list, shift_requests: dict):
    '''st.table にそのまま渡せる Styler を返す。'''
    df = _build_calendar_frame(year, month, day_labels, shift_requests)
    return df.style.apply(_style_cells, axis=None)
