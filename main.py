#!/usr/bin/env python3
"""Entry point: 基金选股与择时分析系统."""

import sys
import os

# Ensure we're in the project directory for relative imports
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

import logging

import warnings
warnings.filterwarnings("ignore", message="iCCP")

import matplotlib
matplotlib.use("Qt5Agg")

# Set Chinese font for matplotlib
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei"]
plt.rcParams["axes.unicode_minus"] = False

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Install default request timeout for akshare before anything else uses it
from app.data import net_guard  # noqa: F401

from app.main_window import MainWindow

LOG_FILE = os.path.join(os.getcwd(), "fund_analyzer.log")


def _setup_runtime():
    """Configure logging, stdout/stderr, and an unhandled-exception hook.

    Under pythonw.exe there is no console, so sys.stdout/sys.stderr are None;
    an uncaught exception would then crash silently when Python tries to print
    a traceback. Redirect them so errors land in the log file instead.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        encoding="utf-8",
    )

    def _excepthook(exc_type, exc_value, exc_tb):
        logging.critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        try:
            from PyQt5.QtWidgets import QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"{exc_value}\n\n详情已写入日志: {LOG_FILE}",
                )
        except Exception:
            pass

    sys.excepthook = _excepthook


def main():
    _setup_runtime()

    try:
        # Enable high-DPI scaling
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Set default font for CJK support
        font = QFont("Microsoft YaHei", 9)
        app.setFont(font)

        window = MainWindow()
        window.show()

        sys.exit(app.exec_())
    except Exception:
        logging.critical("启动失败", exc_info=True)
        try:
            from PyQt5.QtWidgets import QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, "启动失败", f"应用启动时发生错误，详见日志: {LOG_FILE}"
                )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
