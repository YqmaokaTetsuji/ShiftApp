import pytest

from core.shift_rules import TIME_NOT_FILLED, is_day_off, resolve_request


@pytest.mark.parametrize(
    'choice, time_text, expected',
    [
        ('希望なし', '', '出'),
        ('有給', '', '有'),
        ('休', '', '休'),
        ('早', '', '早'),
        ('遅', '', '遅'),
        ('時間指定', '11-19', '11-19'),
        ('時間指定', '  14-L  ', '14-L'),
        ('時間指定', '', TIME_NOT_FILLED),
        ('時間指定', '   ', TIME_NOT_FILLED),
    ],
)
def test_resolve_request(choice, time_text, expected):
    assert resolve_request(choice, time_text) == expected


def test_resolve_request_ignores_time_for_non_time_choice():
    assert resolve_request('休', '11-19') == '休'


@pytest.mark.parametrize(
    'value, expected',
    [('休', True), ('有', True), ('出', False), ('11-19', False), ('', False)],
)
def test_is_day_off(value, expected):
    assert is_day_off(value) is expected
