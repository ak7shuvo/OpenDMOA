import pytest

from app import periods


@pytest.mark.parametrize('raw,expected', [
    ('2024-01', '2024-01'), ('2024-1', '2024-01'), ('2024/03', '2024-03'), ('03/2024', '2024-03'),
    ('Jan 2024', '2024-01'), ('January 2024', '2024-01'), ('2024Q2', '2024-Q2'), ('2024-q3', '2024-Q3'),
    ('2024', '2024'), ('2024-02-29', '2024-02-29'), ('31/12/2024', '2024-12-31'), ('2024-05-06T10:00:00', '2024-05-06'),
    ('2023-02-29', None), ('hello', None), ('', None), ('2024-13', None),
])
def test_normalise(raw, expected):
    assert periods.normalise(raw) == expected


def test_mdy_format():
    assert periods.normalise('12/31/2024', 'MDY') == '2024-12-31'


def test_next_periods():
    assert periods.next_periods('2024-11', 3) == ['2024-12', '2025-01', '2025-02']
    assert periods.next_periods('2024-Q4', 2) == ['2025-Q1', '2025-Q2']
    assert periods.next_periods('2024', 2) == ['2025', '2026']
    assert periods.next_periods('2024-12-31', 1) == ['2025-01-01']


def test_in_range_overlap():
    assert periods.in_range('2025', '2025-09', '2026-08')
    assert periods.in_range('2025-09', '2025-09', '2026-08')
    assert periods.in_range('2026-08', '2025-09', '2026-08')
    assert not periods.in_range('2025-08', '2025-09', '2026-08')
    assert not periods.in_range('2024', '2025-09', None)
    assert periods.in_range('2025-Q3', '2025-09', None)
