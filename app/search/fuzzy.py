"""Fuzzy fund search: pinyin initials + full pinyin + name + code matching.

Pure logic with no Qt dependency, so it can run in the background loader
thread (building the pinyin index) without touching the UI.

Matching priority (lower tier = better):
    code exact > code prefix > name exact > name prefix >
    pinyin-initial exact/prefix > full-pinyin exact/prefix >
    initial subsequence (e.g. "yd" matches "易方达" whose initials are "yfd")
    > full-pinyin subsequence > code/name/initial/full contains.
"""

from __future__ import annotations

import re
from typing import List, NamedTuple, Optional

try:
    from pypinyin import Style, lazy_pinyin

    _HAS_PINYIN = True
except ImportError:  # pragma: no cover
    _HAS_PINYIN = False

    class _Style:
        FIRST_LETTER = "FIRST_LETTER"
        NORMAL = "NORMAL"

    Style = _Style()

    def lazy_pinyin(s, style=None):  # type: ignore[no-redef]
        return []


class FundRecord(NamedTuple):
    """One fund with its pinyin keys precomputed for fast search."""

    code: str
    name: str
    abbr: str  # 拼音首字母,小写,如 华夏成长 -> hxcz
    full: str  # 全拼,小写,如 华夏成长 -> huaxiachengzhang


def _pinyin_abbr(name: str) -> str:
    return "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()


def _pinyin_full(name: str) -> str:
    return "".join(lazy_pinyin(name, style=Style.NORMAL)).lower()


def build_records(items, use_pinyin: bool = True) -> List[FundRecord]:
    """Build FundRecord list from ``[(code, name), ...]``.

    When pypinyin is unavailable (or ``use_pinyin`` is False), abbr/full are
    left empty and matching degrades to code + name only.
    """
    records: List[FundRecord] = []
    for code, name in items:
        code = str(code).strip()
        name = str(name).strip()
        if not code:
            continue
        if use_pinyin and _HAS_PINYIN:
            records.append(FundRecord(code, name, _pinyin_abbr(name), _pinyin_full(name)))
        else:
            records.append(FundRecord(code, name, "", ""))
    return records


def _is_subseq(needle: str, hay: str) -> bool:
    """True if every char of ``needle`` appears in ``hay`` in order."""
    it = iter(hay)
    return all(c in it for c in needle)


_CODE_RE = re.compile(r"\d{6}")


class FundIndex:
    """In-memory fuzzy index over the full fund list."""

    def __init__(self, records: List[FundRecord]):
        self.records = records
        self._by_code = {r.code: r for r in records}

    def search(self, query: str, limit: int = 30) -> List[FundRecord]:
        q = (query or "").strip().lower()
        if not q:
            return []

        # Mixed-query short-circuit: a known 6-digit code embedded in the text
        # (e.g. "易方达110011") resolves to exactly that fund.
        m = _CODE_RE.search(q)
        if m:
            hit = self._by_code.get(m.group(0))
            if hit is not None:
                return [hit]

        # Strip spaces for pinyin matching so "yi fang da" matches too.
        q_ns = q.replace(" ", "")

        scored = []
        for r in self.records:
            tier = _best_tier(q, q_ns, r)
            if tier is not None:
                scored.append((tier, len(r.name), r.code, r))
        scored.sort(key=lambda x: (x[0], x[1], x[2]))
        return [rec for _, _, _, rec in scored[:limit]]


def _best_tier(q: str, q_ns: str, r: FundRecord) -> Optional[int]:
    name_l = r.name.lower()

    # Code
    if q == r.code:
        return 0
    if q.isdigit() and r.code.startswith(q):
        return 1

    # Name
    if q == name_l:
        return 2
    if name_l.startswith(q):
        return 3

    # Pinyin initials / full pinyin (only when pypinyin was available)
    if r.abbr:
        if q == r.abbr:
            return 4
        if r.abbr.startswith(q_ns):
            return 5
    if r.full:
        if q == r.full:
            return 6
        if r.full.startswith(q_ns):
            return 7
    if len(q) >= 2 and _is_subseq(q, r.abbr):
        return 8
    if len(q_ns) >= 2 and _is_subseq(q_ns, r.full):
        return 9

    # Contains fallbacks
    if q.isdigit() and q in r.code:
        return 10
    if q in name_l:
        return 11
    if r.abbr and q in r.abbr:
        return 12
    if r.full and q_ns in r.full:
        return 13
    return None
