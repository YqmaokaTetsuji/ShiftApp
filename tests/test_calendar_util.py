from core.calendar_util import (
    build_day_groups,
    build_day_labels,
    build_week_matrix,
    matches_weekday,
)


def test_build_day_labels_february_leap_year():
    num_days, labels = build_day_labels(2024, 2)
    assert num_days == 29
    assert labels[0] == '1日（木）'
    assert labels[-1] == '29日（木）'


def test_build_day_labels_31_days():
    num_days, labels = build_day_labels(2026, 10)
    assert num_days == 31
    assert len(labels) == 31
    assert labels[0] == '1日（木）'


def test_build_day_groups_adds_fifth_tab_for_long_month():
    _, labels = build_day_labels(2026, 10)
    titles, groups = build_day_groups(labels)
    assert titles[-1] == '29日〜31日'
    assert len(groups) == 5
    assert groups[-1] == labels[28:]
    # すべての日がいずれかのタブに1度だけ現れる
    assert [d for g in groups for d in g] == labels


def test_build_day_groups_february_has_four_tabs():
    _, labels = build_day_labels(2026, 2)  # 28日
    titles, groups = build_day_groups(labels)
    assert len(titles) == 4
    assert [d for g in groups for d in g] == labels


def test_build_week_matrix_starts_on_sunday():
    weeks = build_week_matrix(2026, 10)
    assert len(weeks[0]) == 7
    # 2026年10月1日は木曜 → 最初の週は日〜水が 0
    assert weeks[0][:4] == [0, 0, 0, 0]
    assert weeks[0][4] == 1
    assert max(max(w) for w in weeks) == 31


def test_matches_weekday():
    assert matches_weekday('3日（土）', '土')
    assert not matches_weekday('3日（土）', '日')
