from core.calendar_util import build_day_labels
from ui.preview import SATURDAY_STYLE, SUNDAY_STYLE, styled_calendar


def _cell_styles(year, month):
    _, labels = build_day_labels(year, month)
    styler = styled_calendar(year, month, labels, {})
    styler._compute()
    data = styler.data
    styles = {}
    for (row, col), props in styler.ctx.items():
        cell = str(data.iat[row, col])
        if cell:
            day = int(cell.split('日')[0])
            styles[day] = '; '.join(f'{k}: {v}' for k, v in props)
    return styles


def test_holiday_is_colored_like_sunday():
    styles = _cell_styles(2026, 11)
    # 11月3日（火）は文化の日
    assert styles[3] == SUNDAY_STYLE
    # 平日は色なし、土日は従来どおり
    assert 4 not in styles
    assert styles[7] == SATURDAY_STYLE
    assert styles[1] == SUNDAY_STYLE


def test_holiday_on_saturday_is_colored_like_sunday():
    # 2028年4月29日（土）は昭和の日
    styles = _cell_styles(2028, 4)
    assert styles[29] == SUNDAY_STYLE
    assert styles[22] == SATURDAY_STYLE
