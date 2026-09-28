"""Index/benchmark data retrieval via akshare with caching and retry."""

import time
from typing import Optional

import pandas as pd

from app.config import CACHE_TTL
from app.data import net_guard  # noqa: F401  # installs default request timeout
from app.data.cache_manager import get_cache


class IndexDataError(Exception):
    """Raised when index data cannot be fetched."""


def _sina_index_symbol(code: str) -> str:
    """Map an A-share index code to Sina's symbol format (sh/sz prefix).

    399xxx indices belong to Shenzhen, everything else is treated as Shanghai.
    """
    if code.startswith("399"):
        return f"sz{code}"
    return f"sh{code}"


def _fetch_with_retry(fetch_fn, max_retries: int = 2, delay: float = 2.0):
    """Retry a fetch function on transient network errors."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return fetch_fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(delay)
    raise last_exception


def get_index_history(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Return DataFrame with columns [date, close] for the given index code.
    Handles special codes (HSI, SPX, NDX) with different API calls.
    Retries on transient network errors. Cached for 1 hour."""
    cache = get_cache()
    cache_key = f"index_history_{code}_{start_date}_{end_date}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        import akshare as ak

        def _fetch():
            if code == "HSI":
                return ak.stock_hk_index_daily_em(symbol="HSI")
            elif code in ("SPX", "NDX"):
                # ak.index_investing_global no longer exists in akshare 1.18.63;
                # raise a clear error instead of an AttributeError.
                raise IndexDataError(f"暂不支持该指数: {code}")
            else:
                # Prefer Sina (stock_zh_index_daily): the EastMoney endpoint
                # (index_zh_a_hist) is unreliable from this network. Sina returns
                # full history, so slice to the requested range afterwards.
                try:
                    df = ak.stock_zh_index_daily(symbol=_sina_index_symbol(code))
                    if df is not None and not df.empty and "date" in df.columns:
                        df = df.copy()
                        df["date"] = pd.to_datetime(df["date"])
                        lo = pd.to_datetime(start_date)
                        hi = pd.to_datetime(end_date)
                        df = df[(df["date"] >= lo) & (df["date"] <= hi)]
                        if not df.empty:
                            return df
                except Exception:
                    pass
                # Fallback to EastMoney for indices Sina doesn't cover.
                return ak.index_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                )

        df = _fetch_with_retry(_fetch)

        if df is None or df.empty:
            raise IndexDataError(f"指数 {code} 无数据")

        # Normalize columns
        date_col = None
        close_col = None
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in ("日期", "date"):
                date_col = col
            elif col_str in ("收盘", "close", "收盘价"):
                close_col = col

        if date_col is None or close_col is None:
            raise IndexDataError(f"无法识别指数 {code} 的列名: {list(df.columns)}")

        result = pd.DataFrame()
        result["date"] = pd.to_datetime(df[date_col])
        result["close"] = pd.to_numeric(df[close_col], errors="coerce")
        result = result.dropna(subset=["close"])
        result = result.sort_values("date").reset_index(drop=True)

        cache.set(cache_key, result, CACHE_TTL["index_history"])
        return result
    except IndexDataError:
        raise
    except Exception as e:
        raise IndexDataError(f"获取指数 {code} 数据失败: {e}") from e
