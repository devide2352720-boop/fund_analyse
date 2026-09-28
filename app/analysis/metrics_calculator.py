"""Orchestrator: coordinates data fetching, benchmark detection, and
all financial metric calculations across time windows."""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from PyQt5.QtCore import QObject, pyqtSignal

from app.config import RISK_FREE_RATE_ANNUAL, TIME_WINDOWS
from app.analysis.time_window import (
    slice_time_windows,
    align_fund_and_benchmark,
)
from app.analysis.stock_selection import (
    calculate_jensen_alpha,
    calculate_sharpe_ratio,
    calculate_information_ratio,
    calculate_cumulative_return,
    calculate_max_drawdown,
    JensenAlphaResult,
    SharpeRatioResult,
    InformationRatioResult,
)
from app.analysis.market_timing import (
    calculate_hm_model,
    calculate_tm_model,
    HMResult,
    TMResult,
)


@dataclass
class WindowMetrics:
    window_label: str
    n_observations: int
    jensen_alpha: Optional[JensenAlphaResult] = None
    sharpe_ratio: Optional[SharpeRatioResult] = None
    information_ratio: Optional[InformationRatioResult] = None
    hm_model: Optional[HMResult] = None
    tm_model: Optional[TMResult] = None
    cumulative_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    error: Optional[str] = None


@dataclass
class MetricsResult:
    fund_code: str
    fund_name: str
    benchmark_name: Optional[str]
    benchmark_code: Optional[str]
    raw_benchmark_str: str
    fund_df: Optional["pd.DataFrame"] = None
    bench_df: Optional["pd.DataFrame"] = None
    window_results: dict[str, WindowMetrics] = field(default_factory=dict)
    overview: Optional[dict] = None


class MetricsCalculator(QObject):
    """QObject that runs all calculations. Designed to be moved to a QThread."""

    progress_updated = pyqtSignal(str)
    calculation_complete = pyqtSignal(MetricsResult)
    calculation_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._abort_flag = False

    def abort(self):
        self._abort_flag = True

    def calculate_all(self, fund_code: str, fund_name: str):
        """Full analysis pipeline. Emits signals for UI updates."""
        self._abort_flag = False

        try:
            self.progress_updated.emit("正在获取基金基本信息...")
            if self._abort_flag:
                return

            # 1. Fetch fund overview
            from app.data.fund_api import get_fund_overview
            overview = get_fund_overview(fund_code)

            # 2. Detect benchmark
            self.progress_updated.emit("正在检测业绩比较基准...")
            from app.data.benchmark_detector import detect_for_fund
            bench_name, bench_code, raw_bench_str = detect_for_fund(fund_code, overview)

            if self._abort_flag:
                return

            # 3. Fetch fund NAV history
            self.progress_updated.emit("正在获取基金净值数据...")
            from app.data.fund_api import get_fund_nav_history
            fund_df = get_fund_nav_history(fund_code)

            if fund_df.empty:
                self.calculation_error.emit(f"基金 {fund_name}({fund_code}) 无净值数据")
                return

            if self._abort_flag:
                return

            # 4. If benchmark detected, fetch benchmark data
            bench_df = None
            if bench_code and bench_code != "HSI" and bench_code != "SPX" and bench_code != "NDX":
                # Determine date range from fund data
                start_date = fund_df["date"].min().strftime("%Y%m%d")
                end_date = fund_df["date"].max().strftime("%Y%m%d")

                self.progress_updated.emit(f"正在获取基准指数 {bench_name} 数据...")
                from app.data.index_api import get_index_history
                try:
                    bench_df = get_index_history(bench_code, start_date, end_date)
                except Exception as e:
                    self.progress_updated.emit(f"警告: 无法获取基准数据: {e}")

            if self._abort_flag:
                return

            # 5. Slice time windows
            self.progress_updated.emit("正在计算各时间窗口指标...")
            windows = slice_time_windows(fund_df, TIME_WINDOWS)

            # 6. Attach full DataFrames for charting
            result = MetricsResult(
                fund_code=fund_code,
                fund_name=fund_name,
                benchmark_name=bench_name,
                benchmark_code=bench_code,
                raw_benchmark_str=raw_bench_str,
                fund_df=fund_df,
                bench_df=bench_df,
            )

            for label, window_df in windows.items():
                if self._abort_flag:
                    return

                self.progress_updated.emit(f"正在计算 {label} 指标...")

                wm = WindowMetrics(window_label=label, n_observations=len(window_df))

                fund_returns = window_df["daily_return"].values / 100.0  # convert to decimal

                # Pure return metrics (no benchmark needed)
                wm.cumulative_return = calculate_cumulative_return(fund_returns)
                wm.max_drawdown = calculate_max_drawdown(fund_returns)

                # Sharpe is always computable (no benchmark needed)
                wm.sharpe_ratio = calculate_sharpe_ratio(fund_returns, RISK_FREE_RATE_ANNUAL)

                # Benchmark-dependent metrics
                if bench_df is not None and not bench_df.empty:
                    aligned = align_fund_and_benchmark(window_df, bench_df)
                    if len(aligned) >= 20:
                        bench_returns = aligned["bench_return"].values
                        fund_ret_aligned = aligned["fund_return"].values

                        wm.jensen_alpha = calculate_jensen_alpha(
                            fund_ret_aligned, bench_returns, RISK_FREE_RATE_ANNUAL
                        )
                        wm.information_ratio = calculate_information_ratio(
                            fund_ret_aligned, bench_returns
                        )
                        wm.hm_model = calculate_hm_model(
                            fund_ret_aligned, bench_returns, RISK_FREE_RATE_ANNUAL
                        )
                        wm.tm_model = calculate_tm_model(
                            fund_ret_aligned, bench_returns, RISK_FREE_RATE_ANNUAL
                        )
                    else:
                        wm.error = f"对齐后仅 {len(aligned)} 个交易日数据"
                else:
                    wm.error = "无基准数据"
                    # For pure benchmark-relative metrics, mark as unavailable
                    if bench_name is None:
                        wm.error = "该基金无权益类业绩比较基准"

                result.window_results[label] = wm

            # Full-history overview for the summary bar
            result.overview = self._build_overview(fund_df, fund_name, fund_code, bench_name)

            self.calculation_complete.emit(result)

        except Exception as e:
            self.calculation_error.emit(f"分析出错: {e}")

    def _build_overview(self, fund_df, fund_name, fund_code, bench_name) -> dict:
        """Compute since-inception summary indicators from the full NAV history."""
        full_returns = fund_df["daily_return"].values / 100.0
        n = len(full_returns)

        cumulative = calculate_cumulative_return(full_returns)
        if n > 0 and cumulative > -1.0:
            annualized = (1.0 + cumulative) ** (252.0 / n) - 1.0
        else:
            annualized = 0.0

        sharpe = calculate_sharpe_ratio(full_returns, RISK_FREE_RATE_ANNUAL)

        return {
            "fund_name": fund_name,
            "fund_code": fund_code,
            "benchmark_name": bench_name,
            "cumulative_return": cumulative,
            "annualized_return": annualized,
            "max_drawdown": calculate_max_drawdown(full_returns),
            "annualized_vol": float(np.std(full_returns, ddof=1) * np.sqrt(252)),
            "sharpe_ratio": sharpe.sharpe_ratio if sharpe else None,
        }
