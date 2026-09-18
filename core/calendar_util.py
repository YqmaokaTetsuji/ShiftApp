'''対象月の日付ラベルとカレンダー配置の生成。'''
import calendar
import datetime

from core.config import WEEKDAYS_JA


def build_day_labels(year: int, month: int) -> tuple:
    '''対象月の日数と、「1日（水）」形式のラベル一覧を返す。'''
    _, num_days = calendar.monthrange(year, month)

    day_labels = []
    for d in range(1, num_days + 1):
        dt = datetime.date(year, month, d)
        day_labels.append(f'{d}日（{WEEKDAYS_JA[dt.weekday()]}）')

    return num_days, day_labels


def build_day_groups(day_labels: list) -> tuple:
    '''入力タブ用に、日付ラベルを7日ずつのグループへ分割する。'''
    num_days = len(day_labels)
    tab_titles = ['1日〜7日', '8日〜14日', '15日〜21日', '22日〜28日']
    day_groups = [day_labels[0:7], day_labels[7:14], day_labels[14:21], day_labels[21:28]]

    if num_days > 28:
        tab_titles.append(f'29日〜{num_days}日')
        day_groups.append(day_labels[28:num_days])

    return tab_titles, day_groups


def build_week_matrix(year: int, month: int) -> list:
    '''日曜始まりの週ごとの日付マトリクス。月外は 0。'''
    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    return cal.monthdayscalendar(year, month)


def matches_weekday(label: str, weekday_ja: str) -> bool:
    '''日付ラベルが指定の曜日かどうか'''
    return f'（{weekday_ja}）' in label
