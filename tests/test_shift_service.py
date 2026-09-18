import pandas as pd
import pytest

from core.models import ShiftSubmission
from services import shift_service
from services.shift_service import (
    STATUS_PENDING,
    STATUS_SUBMITTED,
    build_export_dataframe,
    build_submission_status,
    fetch_members,
    fetch_shifts,
    submit_shift,
)


def test_submit_shift_sends_payload(monkeypatch):
    sent = {}
    monkeypatch.setattr(shift_service.gas_client, 'submit', lambda payload: sent.update(payload))

    submission = ShiftSubmission(
        employee_code='1234',
        name='山田',
        department='家電',
        target_hours=0,
        day_requests={'1日（木）': '休'},
    )
    submit_shift(submission, target_month=10)

    assert sent['対象月'] == '10月'
    assert sent['1日（木）'] == '休'
    assert sent['request_id'] == submission.request_id(10)


def test_submit_shift_sends_same_request_id_for_identical_content(monkeypatch):
    '''連打・リトライで届く同じ内容には同じ ID が付く（GAS 側が2件目を捨てられる）。'''
    sent = []
    monkeypatch.setattr(shift_service.gas_client, 'submit', lambda payload: sent.append(payload))

    submission = ShiftSubmission(
        employee_code='1234', name='山田', department='家電',
        target_hours=0, day_requests={'1日（木）': '休'},
    )
    submit_shift(submission, target_month=10)
    submit_shift(submission, target_month=10)

    assert sent[0]['request_id'] == sent[1]['request_id']


def test_fetch_shifts_returns_empty_frame_when_only_header(monkeypatch):
    monkeypatch.setattr(shift_service.gas_client, 'fetch_rows', lambda *a, **k: [['従業員コード']])
    assert fetch_shifts(10).empty


def test_fetch_members_strips_column_whitespace(monkeypatch):
    rows = [[' 従業員コード ', ' 名前 '], ['1', '山田']]
    monkeypatch.setattr(shift_service.gas_client, 'fetch_rows', lambda *a, **k: rows)
    df = fetch_members()
    assert list(df.columns) == ['従業員コード', '名前']


def _shift_frame():
    return pd.DataFrame(
        [
            {'対象月': '10月', '提出日時': '2026-09-18 10:00:00',
             '従業員コード': '20', '名前': 'B', '部門': '家電', '1日（木）': '休'},
            {'対象月': '10月', '提出日時': '2026-09-18 11:00:00',
             '従業員コード': '5', '名前': 'A', '部門': '家電', '1日（木）': '出'},
            {'対象月': '10月', '提出日時': '2026-09-18 12:00:00',
             '従業員コード': '3', '名前': 'C', '部門': '季節AV', '1日（木）': '早'},
        ]
    )


def test_build_export_dataframe_drops_metadata_columns():
    df = build_export_dataframe(_shift_frame())
    assert '対象月' not in df.columns
    assert '提出日時' not in df.columns


def test_build_export_dataframe_sorts_by_department_then_code():
    df = build_export_dataframe(_shift_frame())
    # 季節AV が先、家電は従業員コードの数値順、部門の境目に空白行
    assert df['名前'].tolist() == ['C', '', 'A', 'B']
    assert df['従業員コード'].tolist() == ['3', '', '5', '20']


def test_build_export_dataframe_handles_unknown_department():
    df = _shift_frame()
    df.loc[len(df)] = {'対象月': '10月', '提出日時': '', '従業員コード': '1',
                       '名前': 'Z', '部門': '未設定', '1日（木）': '出'}
    result = build_export_dataframe(df)
    # 未知の部門は末尾に回る
    assert result['名前'].tolist()[-1] == 'Z'


def test_build_export_dataframe_returns_empty_as_is():
    assert build_export_dataframe(pd.DataFrame()).empty


def test_build_export_dataframe_without_department_column():
    df = pd.DataFrame([{'従業員コード': '1', '名前': 'A'}])
    result = build_export_dataframe(df)
    assert result['名前'].tolist() == ['A']


def _member_frame():
    return pd.DataFrame(
        [
            {'従業員コード': '5.0', '名前': 'A', '部門': '家電'},
            {'従業員コード': ' 20 ', '名前': 'B', '部門': '家電'},
            {'従業員コード': '3', '名前': 'C', '部門': '季節AV'},
        ]
    )


def test_build_submission_status_marks_submitted_and_pending():
    shifts = pd.DataFrame([{'従業員コード': '5'}, {'従業員コード': '3.0'}])
    status = build_submission_status(_member_frame(), shifts)

    by_name = dict(zip(status['名前'], status['提出状況']))
    assert by_name == {'A': STATUS_SUBMITTED, 'B': STATUS_PENDING, 'C': STATUS_SUBMITTED}
    # 未提出が先頭
    assert status['提出状況'].iloc[0] == STATUS_PENDING


def test_build_submission_status_all_pending_when_no_shifts():
    status = build_submission_status(_member_frame(), pd.DataFrame())
    assert set(status['提出状況']) == {STATUS_PENDING}


def test_build_submission_status_raises_for_empty_members():
    with pytest.raises(ValueError, match='登録されていません'):
        build_submission_status(pd.DataFrame(), pd.DataFrame())


def test_build_submission_status_raises_for_missing_columns():
    df = pd.DataFrame([{'従業員コード': '1', '氏名': 'A'}])
    with pytest.raises(ValueError, match='見つかりません'):
        build_submission_status(df, pd.DataFrame())
