"""Fund data retrieval via akshare with caching and column normalization."""

import time
from typing import Optional

import pandas as pd

from app.config import (
    NAV_DATE_ALIASES,
    NAV_VALUE_ALIASES,
    NAV_RETURN_ALIASES,
    CACHE_TTL,
)
from app.data import net_guard  # noqa: F401  # installs default request timeout
from app.data.cache_manager import get_cache


class FundDataError(Exception):
    """Raised when fund data cannot be fetched."""


def _normalize_nav_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to date, nav, daily_return."""
    renamed = {}
    for col in df.columns:
        col_str = str(col).strip()
        if col_str in NAV_DATE_ALIASES:
            renamed[col] = "date"
        elif col_str in NAV_VALUE_ALIASES:
            renamed[col] = "nav"
        elif col_str in NAV_RETURN_ALIASES:
            renamed[col] = "daily_return"
    df = df.rename(columns=renamed)
    return df


def _resolve_nav_df(df: pd.DataFrame) -> pd.DataFrame:
    """Post-process: parse dates, sort, compute returns if missing."""
    if df.empty:
        return df

    # Normalize columns
    df = _normalize_nav_columns(df)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

    # If daily_return is missing but nav is present, compute it
    if "daily_return" not in df.columns and "nav" in df.columns:
        df["daily_return"] = df["nav"].pct_change() * 100
        # First row will have NaN return
        df["daily_return"] = df["daily_return"].fillna(0.0)

    return df


def get_all_funds() -> pd.DataFrame:
    """Return DataFrame with columns: 基金代码, 基金简称, 基金类型.
    Cached for 24 hours."""
    cache = get_cache()
    cached = cache.get("fund_list")
    if cached is not None:
        return cached

    try:
        import akshare as ak

        df = ak.fund_name_em()
        cache.set("fund_list", df, CACHE_TTL["fund_list"])
        return df
    except Exception as e:
        raise FundDataError(f"无法获取基金列表: {e}") from e


def get_fund_overview(code: str) -> dict:
    """Return fund overview dict including '业绩比较基准'.
    Cached for 7 days.
    Returns empty dict on failure."""
    cache = get_cache()
    cache_key = f"fund_overview_{code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        import akshare as ak

        df = ak.fund_overview_em(symbol=code)
        if df is None or df.empty:
            return {}

        # Convert single-row DataFrame to dict
        row = df.iloc[0].to_dict()
        # Convert any non-serializable types
        result = {}
        for k, v in row.items():
            if isinstance(v, (int, float, str)):
                result[k] = v
            elif isinstance(v, pd.Timestamp):
                result[k] = v.strftime("%Y-%m-%d")
            else:
                result[k] = str(v) if v is not None else ""

        cache.set(cache_key, result, CACHE_TTL["fund_overview"])
        return result
    except Exception:
        # fund_overview_em might not support all fund codes; try alternative
        try:
            import akshare as ak

            df = ak.fund_info_ths(symbol=code)
            if df is not None and not df.empty:
                row = df.iloc[0].to_dict()
                result = {}
                for k, v in row.items():
                    if isinstance(v, (int, float, str)):
                        result[k] = v
                    elif isinstance(v, pd.Timestamp):
                        result[k] = v.strftime("%Y-%m-%d")
                    else:
                        result[k] = str(v) if v is not None else ""
                cache.set(cache_key, result, CACHE_TTL["fund_overview"])
                return result
        except Exception:
            pass
        return {}


def get_fund_nav_history(code: str) -> pd.DataFrame:
    """Return DataFrame with columns [date, nav, daily_return].
    Cached for 1 hour."""
    cache = get_cache()
    cache_key = f"nav_history_{code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        import akshare as ak

        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            raise FundDataError(f"基金 {code} 无净值数据")

        df = _resolve_nav_df(df)
        cache.set(cache_key, df, CACHE_TTL["nav_history"])
        return df
    except FundDataError:
        raise
    except Exception as e:
        raise FundDataError(f"获取基金 {code} 净值失败: {e}") from e


def search_funds(keyword: str) -> pd.DataFrame:
    """Search funds by keyword (code prefix or name substring)."""
    try:
        all_funds = get_all_funds()
    except FundDataError:
        return pd.DataFrame()

    if not keyword or len(keyword.strip()) == 0:
        return all_funds.head(20)

    kw = keyword.strip()

    # Determine which columns to search
    code_col = "基金代码" if "基金代码" in all_funds.columns else all_funds.columns[0]
    name_col = "基金简称" if "基金简称" in all_funds.columns else all_funds.columns[1]

    code_mask = all_funds[code_col].astype(str).str.startswith(kw)
    name_mask = all_funds[name_col].astype(str).str.contains(kw, case=False, na=False)

    result = all_funds[code_mask | name_mask]
    return result.head(50)
