"""Main window: layout composition, signal wiring, thread management."""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.search_widget import FundSearchWidget
from app.ui.result_table import ResultTableWidget
from app.ui.chart_widget import ChartWidget
from app.ui.detail_panel import DetailPanel
from app.analysis.metrics_calculator import MetricsCalculator, MetricsResult


class MainWindow(QMainWindow):
    """Top-level window composing all UI components."""

    start_analysis = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("基金选股与择时分析系统")
        self.setMinimumSize(1200, 900)
        self._pending_code = None
        self._setup_ui()
        self._setup_worker_thread()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        self.search_widget = FundSearchWidget()
        main_layout.addWidget(self.search_widget)

        self._build_overview_bar()
        main_layout.addWidget(self._overview_bar)

        # Table on top, chart below (vertical splitter), so the full table
        # width is available on first open — no horizontal dragging needed.
        splitter = QSplitter(Qt.Vertical)
        self.result_table = ResultTableWidget()
        self.chart_widget = ChartWidget()
        splitter.addWidget(self.result_table)
        splitter.addWidget(self.chart_widget)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.result_table.setMinimumHeight(230)
        main_layout.addWidget(splitter, stretch=1)

        self.detail_panel = DetailPanel()
        main_layout.addWidget(self.detail_panel)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 请输入基金名称或代码搜索")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.search_widget.fund_selected.connect(self._on_fund_selected)
        self.result_table.window_clicked.connect(self._on_window_clicked)

    def _build_overview_bar(self):
        """Summary strip below the search bar with key fund indicators."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #f5f7fa; border: 1px solid #ddd; border-radius: 4px; }"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(18)

        self._ov_fund = QLabel("")
        self._ov_fund.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")

        self._ov_bench = QLabel("")
        self._ov_cum = QLabel("")
        self._ov_ann = QLabel("")
        self._ov_dd = QLabel("")
        self._ov_vol = QLabel("")
        self._ov_sharpe = QLabel("")

        for lbl in (
            self._ov_fund,
            self._ov_bench,
            self._ov_cum,
            self._ov_ann,
            self._ov_dd,
            self._ov_vol,
            self._ov_sharpe,
        ):
            lbl.setStyleSheet("font-size: 12px; color: #333;")
            lay.addWidget(lbl)

        lay.addStretch(1)
        frame.setVisible(False)
        self._overview_bar = frame

    def _clear_overview(self):
        self._overview_bar.setVisible(False)

    def _show_overview(self, result: MetricsResult):
        ov = result.overview
        if not ov:
            self._clear_overview()
            return

        self._ov_fund.setText(f"{ov['fund_name']} ({ov['fund_code']})")
        bench = ov.get("benchmark_name") or "未检测到权益类基准"
        self._ov_bench.setText(f"业绩基准: {bench}")
        self._ov_cum.setText(self._pct_label("成立以来收益率", ov.get("cumulative_return")))
        self._ov_ann.setText(self._pct_label("年化收益率", ov.get("annualized_return")))
        self._ov_dd.setText(self._pct_label("最大回撤", ov.get("max_drawdown")))
        self._ov_vol.setText(self._pct_label("年化波动率", ov.get("annualized_vol")))

        sharpe = ov.get("sharpe_ratio")
        self._ov_sharpe.setText(
            f"夏普比率: {sharpe:.2f}" if sharpe is not None else "夏普比率: N/A"
        )

        self._overview_bar.setVisible(True)

    @staticmethod
    def _pct_label(name: str, value: float | None) -> str:
        if value is None:
            return f"{name}: N/A"
        if value > 0:
            color = "#2e7d32"
        elif value < 0:
            color = "#c62828"
        else:
            color = "#333"
        return f'{name}: <span style="color:{color};">{value * 100:.2f}%</span>'

    def _setup_worker_thread(self):
        self.worker_thread = QThread(self)
        self.calculator = MetricsCalculator()
        self.calculator.moveToThread(self.worker_thread)

        # Cross-thread signal: main -> worker (auto queued)
        self.start_analysis.connect(self.calculator.calculate_all)

        # Cross-thread signals: worker -> main (auto queued)
        self.calculator.calculation_complete.connect(self._on_calculation_done)
        self.calculator.calculation_error.connect(self._on_calculation_error)
        self.calculator.progress_updated.connect(self._on_progress_updated)

        self.worker_thread.start()

    def _on_fund_selected(self, code: str, name: str):
        """User selected a fund. Start analysis in worker thread."""
        self.calculator.abort()
        self._clear_overview()

        self._pending_code = code
        self.result_table.clear_results()
        self.chart_widget.clear_plot()
        self.detail_panel.show_loading(f"正在分析 {name}({code})，请稍候...")
        self.status_bar.showMessage(f"正在分析 {name}({code})...")
        self.progress_bar.setVisible(True)

        # Emit signal -> queued in worker thread -> calculator.calculate_all runs there
        self.start_analysis.emit(code, name)

    def _on_progress_updated(self, message: str):
        self.status_bar.showMessage(message)
        self.detail_panel.show_loading(message)

    def _on_calculation_done(self, result: MetricsResult):
        """Update all UI with results. Runs in main thread (auto-queued)."""
        if result.fund_code != self._pending_code:
            return
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(
            f"分析完成 - {result.fund_name}({result.fund_code})"
        )

        self.result_table.display_results(result)
        self.detail_panel.show_results(result)
        self._show_overview(result)

        # Plot chart using data already included in the result
        self.chart_widget.plot_comparison(
            result.fund_df,
            result.bench_df,
            result.fund_name,
            result.benchmark_name,
        )

    def _on_calculation_error(self, error: str):
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"错误: {error}")
        self.detail_panel.show_error(error)
        QMessageBox.warning(self, "分析出错", error)

    def _on_window_clicked(self, window_label: str):
        # Positional msecs: PyQt5's showMessage doesn't accept a "timeout" kwarg.
        self.status_bar.showMessage(f"查看 {window_label} 指标详情", 3000)

    def closeEvent(self, event):
        """Clean up threads on exit."""
        self.calculator.abort()
        self.worker_thread.quit()
        self.worker_thread.wait(2000)
        self.search_widget.shutdown()
        event.accept()
