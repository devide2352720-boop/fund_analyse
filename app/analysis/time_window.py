"""Time window slicing and fund-benchmark data alignment."""

from typing import Optional

import numpy as np
import pandas as pd

from app.config import TIME_WINDOWS, MIN_OBSERVATIONS


def slice_time_windows(
    df: pd.DataFrame,
    windows: Optional[list[tuple[str, int]]] = None,
) -> dict[str, pd.DataFrame]:
    """Slice a DataFrame with 'date' column into time windows.

    Args:
        df: DataFrame with 'date' column (datetime).
        windows: List of (label, days_back). Defaults to config.TIME_WINDOWS.

    Returns:
        Dict of {label: sliced_df}. Windows with < MIN_OBSERVATIONS are omitted.
    """
    if df.empty or "date" not in df.columns:
        return {}

    if windows is None:
        windows = TIME_WINDOWS

    end_date = df["date"].max()
    result = {}

    for label, days_back in windows:
        start_date = end_date - pd.Timedelta(days=days_back)
        sliced = df[df["date"] >= start_date].copy()
        if len(sliced) >= MIN_OBSERVATIONS:
            result[label] = sliced

    return result


def align_fund_and_benchmark(
    fund_df: pd.DataFrame,
    bench_df: pd.DataFrame,
) -> pd.DataFrame:
    """Inner join fund and benchmark DataFrames on date.
    Both must have 'date' column. Returns merged DataFrame with
    fund_return and bench_return columns (decimal returns, not %)."""
    if fund_df.empty or bench_df.empty:
        return pd.DataFrame()

    fund = fund_df[["date"]].copy()
    bench = bench_df[["date", "close"]].copy()

    # Get fund daily returns - use daily_return if available, else compute from nav
    if "daily_return" in fund_df.columns:
        fund["fund_return"] = pd.to_numeric(fund_df["daily_return"], errors="coerce") / 100.0
    elif "nav" in fund_df.columns:
        fund["fund_return"] = fund_df["nav"].pct_change()
    else:
        return pd.DataFrame()

    merged = pd.merge(fund, bench, on="date", how="inner")
    merged = merged.dropna(subset=["fund_return", "close"])

    # Compute benchmark daily returns
    merged["bench_return"] = merged["close"].pct_change()
    merged = merged.dropna(subset=["bench_return"])

    # Remove infinities
    merged = merged.replace([np.inf, -np.inf], np.nan).dropna()

    return merged.reset_index(drop=True)
