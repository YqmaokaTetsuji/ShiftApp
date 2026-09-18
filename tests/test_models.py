import datetime

from core.config import JST
from core.models import ShiftSubmission


def _submission(**overrides):
    base = dict(
        employee_code='1234',
        name='山田 太郎',
        department='家電',
        target_hours=80,
        day_requests={'1日（木）': '出', '2日（金）': '休'},
        remarks='テスト期間あり',
    )
    base.update(overrides)
    return ShiftSubmission(**base)


def test_normalized_converts_fullwidth_code_and_strips():
    s = _submission(employee_code=' １２３４ ', name='  山田 太郎  ', remarks='  メモ  ')
    clean = s.normalized()
    assert clean.employee_code == '1234'
    assert clean.name == '山田 太郎'
    assert clean.remarks == 'メモ'


def test_validate_passes_for_complete_submission():
    assert _submission().validate() == []


def test_validate_collects_all_missing_fields():
    errors = _submission(name='  ', employee_code='', department='選択してください').validate()
    assert len(errors) == 3
    assert any('お名前' in e for e in errors)
    assert any('部門' in e for e in errors)
    assert any('従業員コード' in e for e in errors)


def test_to_payload_shape_and_order():
    at = datetime.datetime(2026, 9, 18, 10, 30, 0, tzinfo=JST)
    payload = _submission().to_payload(target_month=10, submitted_at=at)

    assert payload['対象月'] == '10月'
    assert payload['提出日時'] == '2026-09-18 10:30:00'
    assert payload['従業員コード'] == '1234'
    assert payload['名前'] == '山田 太郎'
    assert payload['部門'] == '家電'
    assert payload['希望出勤時間'] == 80
    assert payload['1日（木）'] == '出'
    assert payload['2日（金）'] == '休'
    # 備考は日付列より後ろに来る
    assert list(payload)[-1] == '備考'
    assert payload['備考'] == 'テスト期間あり'


def test_to_payload_normalizes_input():
    payload = _submission(employee_code='５６７８', name=' 佐藤 ').to_payload(target_month=1)
    assert payload['従業員コード'] == '5678'
    assert payload['名前'] == '佐藤'


def _id_submission(**overrides):
    base = dict(
        employee_code='1234', name='山田', department='家電',
        target_hours=0, day_requests={'1日（木）': '休'}, remarks='',
    )
    base.update(overrides)
    return ShiftSubmission(**base)


def test_request_id_ignores_submitted_at():
    '''提出日時は押した瞬間で変わるので、重複判定のキーには影響させない。'''
    assert _id_submission().request_id(10) == _id_submission().request_id(10)


def test_request_id_changes_when_content_changes():
    '''内容を直して出し直した場合は別 ID になり、重複扱いで捨てられない。'''
    base = _id_submission()
    assert base.request_id(10) != _id_submission(day_requests={'1日（木）': '出'}).request_id(10)
    assert base.request_id(10) != _id_submission(remarks='テスト期間').request_id(10)
    assert base.request_id(10) != base.request_id(11)
