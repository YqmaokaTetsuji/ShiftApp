'''入力された選択肢を、スプレッドシートに記録する表記へ変換するルール。'''

# 選択肢 -> 記録する文字
_CHOICE_TO_MARK = {
    '希望なし': '出',
    '有給': '有',
    '休': '休',
    '早': '早',
    '遅': '遅',
}

TIME_CHOICE = '時間指定'
TIME_NOT_FILLED = '時間指定(未入力)'

# 休みとして赤字表示する文字
OFF_MARKS = ('休', '有')


def resolve_request(choice: str, specific_time: str = '') -> str:
    '''ラジオボタンの選択と時間入力から、記録用の1セル分の値を作る。'''
    if choice == TIME_CHOICE:
        time_text = (specific_time or '').strip()
        return time_text if time_text else TIME_NOT_FILLED
    return _CHOICE_TO_MARK.get(choice, choice)


def is_day_off(value: str) -> bool:
    '''「休」「有」を含む＝休み扱いの表記かどうか'''
    return any(mark in str(value) for mark in OFF_MARKS)
