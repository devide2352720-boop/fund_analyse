"""Matplotlib NAV comparison chart widget."""

from typing import Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter, AutoDateLocator
import matplotlib.ticker as ticker

from app.config import CHART_DPI


class ChartWidget(FigureCanvasQTAgg):
    """NAV comparison chart: fund vs benchmark, both normalized to 100."""

    def __init__(self, parent=None):
        self.figure = Figure(figsize=(8, 4), dpi=CHART_DPI)
        super().__init__(self.figure)
        self.setParent(parent)
        self.axes = self.figure.add_subplot(111)
        self.figure.tight_layout()
        self._setup_styles()
        self.clear_plot()

    def _setup_styles(self):
        """Configure matplotlib style."""
        self.figure.patch.set_facecolor("white")
        self.axes.tick_params(labelsize=9)

    def clear_plot(self):
        """Reset to empty state with placeholder text."""
        self.axes.clear()
        self.axes.text(
            0.5, 0.5, "选择基金后将显示净值对比图",
            transform=self.axes.transAxes,
            ha="center", va="center",
            fontsize=14, color="gray",
        )
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.draw()

    def plot_comparison(
        self,
        fund_df: pd.DataFrame,
        bench_df: Optional[pd.DataFrame],
        fund_name: str,
        bench_name: Optional[str],
    ):
        """Plot fund NAV vs benchmark, both normalized to 100 at start date."""
        self.axes.clear()

        if fund_df.empty:
            self.clear_plot()
            return

        # Fund NAV line
        fund = fund_df.sort_values("date")
        fund_nav_norm = fund["nav"].values / fund["nav"].iloc[0] * 100
        self.axes.plot(fund["date"], fund_nav_norm, label=fund_name, linewidth=1.5, color="#2196F3")

        # Benchmark line
        if bench_df is not None and not bench_df.empty and bench_name:
            bench = bench_df.sort_values("date")
            # Align to fund date range
            bench = bench[
                (bench["date"] >= fund["date"].min()) &
                (bench["date"] <= fund["date"].max())
            ]
            if not bench.empty:
                bench_norm = bench["close"].values / bench["close"].iloc[0] * 100
                self.axes.plot(bench["date"], bench_norm, label=bench_name, linewidth=1.5, color="#FF5722", linestyle="--")

        # Formatting
        self.axes.set_ylabel("归一化净值 (基期=100)", fontsize=10)
        self.axes.set_xlabel("日期", fontsize=10)
        self.axes.legend(fontsize=9, loc="upper left")
        self.axes.grid(True, alpha=0.3)
        self.axes.axhline(
            y=100, color="gray", linewidth=0.5, linestyle=":", label="_nolegend_"
        )

        # Date axis formatting
        locator = AutoDateLocator()
        self.axes.xaxis.set_major_locator(locator)
        self.axes.xaxis.set_major_formatter(DateFormatter("%Y-%m"))
        self.figure.autofmt_xdate()

        # Y-axis formatting
        self.axes.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))

        self.figure.tight_layout()
        self.draw()
