"""Period strings: YYYY, YYYY-Qn, YYYY-MM, YYYY-MM-DD (ISO-like, sortable)."""
from __future__ import annotations

import re
from datetime import date, timedelta

RX = {
    'year': re.compile(r'^(\d{4})$'),
    'quarter': re.compile(r'^(\d{4})-Q([1-4])$'),
    'month': re.compile(r'^(\d{4})-(0[1-9]|1[0-2])$'),
    'day': re.compile(r'^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$'),
}

ALT_MONTH = [re.compile(r'^(\d{4})[/.](\d{1,2})$'), re.compile(r'^(\d{1,2})[/.-](\d{4})$')]
ALT_DAY = [re.compile(r'^(\d{4})[/.](\d{1,2})[/.](\d{1,2})$'), re.compile(r'^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$')]
MONTHS = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}


def kind(p: str) -> str | None:
    for k, rx in RX.items():
        if rx.match(p):
            if k == 'day':
                try:
                    date.fromisoformat(p)
                except ValueError:
                    return None
            return k
    return None


def normalise(raw: str, date_format: str = 'DMY') -> str | None:
    """Coerce common spellings to canonical period strings. Returns None if unparseable."""
    s = str(raw).strip()
    if not s:
        return None
    if kind(s):
        return s
    m = re.match(r'^(\d{4})[- ]?[Qq]([1-4])$', s)
    if m:
        return f'{m.group(1)}-Q{m.group(2)}'
    m = re.match(r'^([A-Za-z]{3})[A-Za-z]*[ -](\d{4})$', s)
    if m and m.group(1).lower() in MONTHS:
        return f'{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}'
    m = re.match(r'^(\d{4})-(\d{1,2})$', s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f'{m.group(1)}-{int(m.group(2)):02d}'
    m = ALT_MONTH[0].match(s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f'{m.group(1)}-{int(m.group(2)):02d}'
    m = ALT_MONTH[1].match(s)
    if m and 1 <= int(m.group(1)) <= 12:
        return f'{m.group(2)}-{int(m.group(1)):02d}'
    m = ALT_DAY[0].match(s)
    if m:
        return _day(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = ALT_DAY[1].match(s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _day(y, b, a) if date_format == 'DMY' else _day(y, a, b)
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ].*$', s)
    if m:
        return _day(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _day(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def to_month_start(p: str) -> str:
    """Comparable key for range filters: every period maps to its first YYYY-MM-DD."""
    k = kind(p)
    if k == 'year':
        return f'{p}-01-01'
    if k == 'quarter':
        y, q = p.split('-Q')
        return f'{y}-{(int(q) - 1) * 3 + 1:02d}-01'
    if k == 'month':
        return f'{p}-01'
    return p


def to_period_end(p: str) -> str:
    k = kind(p)
    if k == 'year':
        return f'{p}-12-31'
    if k == 'quarter':
        y, q = p.split('-Q')
        return f'{y}-{int(q) * 3:02d}-31'
    if k == 'month':
        return f'{p}-31'
    return p


def in_range(p: str, start: str | None, end: str | None) -> bool:
    """True when period ``p`` overlaps [start, end] (inclusive, any granularity).

    A yearly value (``2025``) therefore belongs to a window 2025-09 → 2026-08.
    """
    if start and to_period_end(p) < to_month_start(start):
        return False
    if end and to_month_start(p) > to_period_end(end):
        return False
    return True


def next_periods(last: str, h: int) -> list[str]:
    k = kind(last)
    out: list[str] = []
    if k == 'year':
        y = int(last)
        out = [str(y + i) for i in range(1, h + 1)]
    elif k == 'quarter':
        y, q = int(last[:4]), int(last[-1])
        for _ in range(h):
            q += 1
            if q > 4:
                q, y = 1, y + 1
            out.append(f'{y}-Q{q}')
    elif k == 'month':
        y, mo = int(last[:4]), int(last[5:7])
        for _ in range(h):
            mo += 1
            if mo > 12:
                mo, y = 1, y + 1
            out.append(f'{y}-{mo:02d}')
    elif k == 'day':
        d = date.fromisoformat(last)
        out = [(d + timedelta(days=i)).isoformat() for i in range(1, h + 1)]
    else:
        out = [f'{last}+{i}' for i in range(1, h + 1)]
    return out


def season_length_for(p: str) -> int:
    return {'year': 1, 'quarter': 4, 'month': 12, 'day': 7}.get(kind(p) or '', 1)
