"""Results table displaying metrics for each time window with color coding."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from app.config import TABLE_DECIMALS
from app.analysis.metrics_calculator import MetricsResult


# Colors for significance-based highlighting
GREEN = QColor(198, 239, 206)   # significant positive
YELLOW = QColor(255, 255, 204)  # not significant positive
ORANGE = QColor(255, 235, 204)  # not significant negative
RED = QColor(255, 199, 206)     # significant negative
HEADER_BG = QColor(68, 114, 196)
HEADER_FG = QColor(255, 255, 255)

COLUMN_LABELS = [
    "时间段",
    "区间收益率",
    "最大回撤",
    "Jensen α",
    "Sharpe",
    "信息比率",
    "H-M γ",
    "T-M γ",
]


class ResultTableWidget(QTableWidget):
    """Table showing 6 time windows × 5 metric columns."""

    window_clicked = pyqtSignal(str)  # window label

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMN_LABELS))
        self.setHorizontalHeaderLabels(COLUMN_LABELS)
        # Table now spans the full window width: last section absorbs extra
        # space, scrollbar only appears if the window is very narrow.
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)

        # Font
        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)

        # Connect click
        self.cellClicked.connect(self._on_cell_clicked)

        self.clear_results()

    def clear_results(self):
        """Reset table to empty state."""
        self.setRowCount(0)

    def display_results(self, results: MetricsResult):
        """Populate table from MetricsResult."""
        self.clear_results()

        windows = ["3年", "1年", "6个月", "3个月", "1个月", "1周"]
        self.setRowCount(len(windows))

        for row, label in enumerate(windows):
            # Time period label
            period_item = QTableWidgetItem(label)
            period_item.setTextAlignment(Qt.AlignCenter)
            period_item.setFlags(period_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 0, period_item)

            if label in results.window_results:
                wm = results.window_results[label]
                n_obs = wm.n_observations
                period_item.setToolTip(f"交易日数: {n_obs}")

                # 区间收益率 (col 1)
                if wm.cumulative_return is not None:
                    val = wm.cumulative_return
                    item = QTableWidgetItem(f"{val*100:.2f}%")
                    item.setBackground(self._color_for_metric(val, 0.0, higher_is_better=True))
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 1, item)

                # 最大回撤 (col 2)
                if wm.max_drawdown is not None:
                    val = wm.max_drawdown
                    item = QTableWidgetItem(f"{val*100:.2f}%")
                    item.setBackground(self._color_for_metric(val, 0.0, higher_is_better=True))
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 2, item)

                # Jensen's Alpha (col 3)
                if wm.jensen_alpha:
                    val = wm.jensen_alpha.alpha
                    pv = wm.jensen_alpha.alpha_p_value
                    text = f"{val:.{TABLE_DECIMALS}f} (p={pv:.4f})"
                    item = QTableWidgetItem(text)
                    item.setBackground(self._color_for_metric(val, pv, higher_is_better=True))
                    item.setToolTip(f"β={wm.jensen_alpha.beta:.4f}, R²={wm.jensen_alpha.r_squared:.4f}")
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 3, item)

                # Sharpe Ratio (col 4)
                if wm.sharpe_ratio:
                    val = wm.sharpe_ratio.sharpe_ratio
                    text = f"{val:.{TABLE_DECIMALS}f}"
                    item = QTableWidgetItem(text)
                    item.setBackground(self._color_for_metric(val, 0.0, higher_is_better=True))
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 4, item)

                # Information Ratio (col 5)
                if wm.information_ratio:
                    val = wm.information_ratio.information_ratio
                    text = f"{val:.{TABLE_DECIMALS}f}"
                    item = QTableWidgetItem(text)
                    item.setBackground(self._color_for_metric(val, 0.0, higher_is_better=True))
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 5, item)

                # H-M gamma (col 6)
                if wm.hm_model:
                    val = wm.hm_model.beta_2
                    pv = wm.hm_model.gamma_p_value
                    text = f"{val:.{TABLE_DECIMALS}f} (p={pv:.4f})"
                    item = QTableWidgetItem(text)
                    item.setBackground(self._color_for_metric(val, pv, higher_is_better=True))
                    item.setToolTip(f"α={wm.hm_model.alpha:.4f}, β₁={wm.hm_model.beta_1:.4f}, R²={wm.hm_model.r_squared:.4f}")
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 6, item)

                # T-M gamma (col 7)
                if wm.tm_model:
                    val = wm.tm_model.beta_2
                    pv = wm.tm_model.gamma_p_value
                    text = f"{val:.{TABLE_DECIMALS}f} (p={pv:.4f})"
                    item = QTableWidgetItem(text)
                    item.setBackground(self._color_for_metric(val, pv, higher_is_better=True))
                    item.setToolTip(f"α={wm.tm_model.alpha:.4f}, β₁={wm.tm_model.beta_1:.4f}, R²={wm.tm_model.r_squared:.4f}")
                elif wm.error:
                    item = QTableWidgetItem(wm.error)
                    item.setBackground(QColor(240, 240, 240))
                else:
                    item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, 7, item)

            else:
                # Window not available
                for col in range(1, 8):
                    item = QTableWidgetItem("数据不足")
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setBackground(QColor(240, 240, 240))
                    self.setItem(row, col, item)

    def _on_cell_clicked(self, row: int, _col: int):
        """Emit window_clicked signal with the time period label."""
        item = self.item(row, 0)
        if item:
            self.window_clicked.emit(item.text())

    @staticmethod
    def _color_for_metric(value: float, p_value: float,
                          higher_is_better: bool = True,
                          alpha: float = 0.05) -> QColor:
        """Return background color based on value sign and significance.

        Green:  significant and positive (for higher_is_better) / negative (for lower_is_better)
        Yellow: not significant but positive
        Orange: not significant but negative
        Red:    significant and negative (for higher_is_better) / positive (for lower_is_better)
        """
        is_positive = value > 0
        is_significant = p_value < alpha and p_value > 0

        if not is_significant:
            if is_positive:
                return YELLOW
            else:
                return ORANGE
        else:
            # Significant
            if higher_is_better:
                return GREEN if is_positive else RED
            else:
                return RED if is_positive else GREEN
