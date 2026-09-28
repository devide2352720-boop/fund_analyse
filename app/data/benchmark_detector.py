"""Benchmark detection: parse fund performance comparison benchmark strings
to identify the primary equity index (e.g., CSI 300, CSI 500).

Examples:
  "沪深300指数收益率×80%+中证综合债券指数收益率×20%"  → 沪深300
  "中证500指数收益率×95%+银行活期存款利率(税后)×5%"    → 中证500
  "中证1000指数收益率*95%+银行活期存款利率(税后)*5%"    → 中证1000
  "创业板指数收益率×95%+银行活期存款利率×5%"           → 创业板指数
  "中证综合债指数收益率×100%"                          → None (pure bond)
"""

import re
from typing import Optional, Tuple

from app.config import INDEX_NAME_TO_CODE, BOND_KEYWORDS


class BenchmarkDetectionError(Exception):
    """Raised when benchmark cannot be detected."""


# Regex for weighted pattern: "名称指数收益率×权重%" or "名称收益率×权重%"
# Non-greedy name + mandatory suffix ensures correct split
WEIGHTED_PATTERN = re.compile(
    r"([一-鿿\w]+?)"    # group 1: index name (non-greedy)
    r"(?:指数)?收益率?"           # suffix: optional "指数" + "收益率" or just "收益率"
    r"\s*[×*]\s*"               # multiplication sign
    r"(\d+(?:\.\d+)?)"          # group 2: weight
    r"\s*%"                      # percent
)

# Pattern for unweighted: "名称指数收益率" or "名称收益率"
# "收益率" is mandatory to avoid single-char false matches
UNWEIGHTED_PATTERN = re.compile(
    r"([一-鿿\w]+?)"    # group 1: index name (non-greedy)
    r"(?:指数)?收益率"           # suffix: optional "指数" + mandatory "收益率"
)

# Regex for "名称: XX%" or "名称xx%" format (colon-separated)
COLON_PATTERN = re.compile(
    r"([一-鿿\w]+?)"
    r"(?:指数)?"
    r"\s*[:：]\s*"
    r"(\d+(?:\.\d+)?)\s*%"
)


def _match_known_names(text: str) -> Optional[str]:
    """Look for known index names appearing in text (longest match first),
    ignoring bond keywords."""
    sorted_names = sorted(INDEX_NAME_TO_CODE.keys(), key=len, reverse=True)
    for name in sorted_names:
        is_bond = any(kw in name for kw in BOND_KEYWORDS)
        if not is_bond and name in text:
            return name
    return None


def _extract_weighted_components(text: str) -> list[tuple[str, float]]:
    """Extract (name, weight) pairs from weighted patterns, normalized."""
    components = []
    for pattern in (WEIGHTED_PATTERN, COLON_PATTERN):
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            try:
                weight = float(m.group(2))
            except (ValueError, IndexError):
                continue
            if name:
                components.append((name, weight))
    return components


def parse_benchmark_string(benchmark_str: str) -> Optional[str]:
    """Parse benchmark string and return the primary equity index Chinese name.
    Returns None if no equity index can be identified."""
    if not benchmark_str or not benchmark_str.strip():
        return None

    text = benchmark_str.strip()

    # Strategy 1: Weighted components - extract weights, pick top equity index
    components = _extract_weighted_components(text)
    equity_components = []
    for name, weight in components:
        is_bond = any(kw in name for kw in BOND_KEYWORDS)
        if not is_bond and name in INDEX_NAME_TO_CODE and INDEX_NAME_TO_CODE[name] is not None:
            equity_components.append((name, weight))

    if equity_components:
        equity_components.sort(key=lambda x: x[1], reverse=True)
        return equity_components[0][0]

    # Strategy 2: Unweighted pattern matching
    for m in UNWEIGHTED_PATTERN.finditer(text):
        name = m.group(1).strip()
        is_bond = any(kw in name for kw in BOND_KEYWORDS)
        if not is_bond and name in INDEX_NAME_TO_CODE and INDEX_NAME_TO_CODE[name] is not None:
            return name

    # Strategy 3: Direct lookup of known index names in text
    known = _match_known_names(text)
    if known is not None:
        return known

    return None


def resolve_index_code(index_name: str) -> Optional[str]:
    """Map Chinese index name to akshare index code.
    Returns None if not in mapping."""
    return INDEX_NAME_TO_CODE.get(index_name)


def detect_for_fund(fund_code: str, fund_overview: dict) -> Tuple[Optional[str], Optional[str], str]:
    """Full benchmark detection pipeline.
    Returns (index_name, index_code, raw_benchmark_string)."""
    # Try multiple field names that akshare might return
    benchmark_str = ""
    for field in ["业绩比较基准", "跟踪标的", "基准", "benchmark"]:
        if field in fund_overview and fund_overview[field]:
            benchmark_str = str(fund_overview[field]).strip()
            break

    if not benchmark_str:
        return None, None, ""

    index_name = parse_benchmark_string(benchmark_str)
    if index_name is None:
        return None, None, benchmark_str

    index_code = resolve_index_code(index_name)
    return index_name, index_code, benchmark_str
