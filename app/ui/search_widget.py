"""Fund search widget with fuzzy (pinyin) autocomplete.

The fund list is loaded asynchronously in a background QThread so that
constructing this widget never blocks the main window on a network call.

Matching (code / name / pinyin initials / full pinyin, sorted by relevance)
is done in Python against a FundIndex. The dropdown is a plain QFrame +
QListWidget popup driven entirely from here (no QCompleter), so the ordered
top-N results appear exactly as ranked and keyboard handling is fully under
our control and consistent across platforms.
"""

import logging
import re
import time

from PyQt5.QtCore import QEvent, QPoint, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import SEARCH_DEBOUNCE_MS
from app.search.fuzzy import FundIndex
from app.ui.fund_list_loader import FundListLoader

POPUP_LIMIT = 50
POPUP_VISIBLE_ROWS = 15


class FundSearchWidget(QWidget):
    """Search bar with fuzzy autocomplete dropdown for fund selection."""

    fund_selected = pyqtSignal(str, str)  # (fund_code, fund_name)

    # Class-level signal: emits a request to (re)load the fund list in the
    # worker thread. pyqtSignal must be a class attribute, not an instance one.
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_funds_lookup = {}  # code -> (code, name)
        self._display_lookup = {}    # "name (code)" -> (code, name)
        self._index = None           # FundIndex, built when the list loads
        self._suppress_next_text_change = False
        self._setup_ui()
        self._setup_loader()
        self._load_fund_data_async()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("基金搜索:")
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入基金名称或代码（支持关键词搜索）")
        self.input.setMinimumHeight(32)
        self.input.installEventFilter(self)

        layout.addWidget(label)
        layout.addWidget(self.input, stretch=1)

        # Loading / failure status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status_label)

        self._retry_btn = QPushButton("重试")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self._retry)
        layout.addWidget(self._retry_btn)

        # Dropdown popup (frameless, closes on outside click)
        self._popup = QFrame(self, Qt.Popup | Qt.FramelessWindowHint)
        self._popup.setObjectName("fundPopup")
        self._popup.setStyleSheet(
            "#fundPopup { background: #ffffff; border: 1px solid #aaaaaa; }"
        )
        popup_lay = QVBoxLayout(self._popup)
        popup_lay.setContentsMargins(0, 0, 0, 0)
        popup_lay.setSpacing(0)
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { border: none; font-size: 13px; }"
            "QListWidget::item { padding: 3px 6px; }"
            "QListWidget::item:selected { background: #cde4ff; color: #000; }"
        )
        self._list.setFrameShape(QListWidget.NoFrame)
        self._list.setFocusPolicy(Qt.NoFocus)
        popup_lay.addWidget(self._list)
        self._popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._popup.hide()

        self._list.itemClicked.connect(self._on_item_clicked)

        # Debounce timer
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._on_debounced_text_changed)

        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self._on_return_pressed)

    def _setup_loader(self):
        """Create the worker thread that loads the fund list."""
        self._loader_thread = QThread(self)
        self._loader = FundListLoader()
        self._loader.moveToThread(self._loader_thread)
        self.load_requested.connect(self._loader.run)
        self._loader.loaded.connect(self._on_funds_loaded)
        self._loader.failed.connect(self._on_funds_load_failed)
        self._loader_thread.start()

    def _load_fund_data_async(self):
        """Start loading the fund list in the background."""
        self._set_status("正在加载基金列表...")
        self.load_requested.emit()

    def _on_funds_loaded(self, records):
        """Fund records (with pinyin) arrived from the worker thread."""
        if not records:
            self._on_funds_load_failed("基金列表为空")
            return

        self._all_funds_lookup = {r.code: (r.code, r.name) for r in records}
        self._display_lookup = {f"{r.name} ({r.code})": (r.code, r.name) for r in records}
        self._index = FundIndex(records)

        self._retry_btn.setVisible(False)
        self._set_status(f"已加载 {len(records)} 只基金")
        self.input.setPlaceholderText("输入基金名称、代码或拼音首字母（如 hx、yd）")

    def _on_funds_load_failed(self, error: str):
        self._retry_btn.setVisible(True)
        self._set_status("基金列表加载失败")
        self.input.setPlaceholderText("加载失败，可直接输入6位基金代码后回车")

    def _retry(self):
        self._load_fund_data_async()

    def _set_status(self, message: str):
        self._status_label.setText(message)

    # ---- keyboard handling -------------------------------------------------

    def eventFilter(self, obj, event):
        """Arrow / Enter / Esc navigation while the dropdown is open."""
        if obj is not self.input or event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        popup_open = self._popup.isVisible()

        if key in (Qt.Key_Down, Qt.Key_Up):
            if popup_open:
                self._move_selection(key == Qt.Key_Down)
            else:
                # Open the dropdown for the current text on arrow-down.
                self.input.textChanged.emit(self.input.text())
                self._debounce.stop()
                self._on_debounced_text_changed()
            return True

        if key in (Qt.Key_Enter, Qt.Key_Return):
            if popup_open:
                self._commit_selection()
            return True

        if key == Qt.Key_Escape:
            if popup_open:
                self._popup.hide()
                return True
            return False

        return False

    def _move_selection(self, down: bool):
        count = self._list.count()
        if count == 0:
            return
        row = self._list.currentRow()
        if down:
            row = row + 1 if row < count - 1 else 0
        else:
            row = row - 1 if row > 0 else count - 1
        self._list.setCurrentRow(row)

    def _commit_selection(self):
        row = self._list.currentRow()
        if row < 0 and self._list.count() > 0:
            row = 0
        item = self._list.item(row)
        if item is None:
            return
        self._popup.hide()
        self._select_fund(
            item.data(Qt.UserRole), item.data(Qt.UserRole + 1), item.text()
        )

    def _on_item_clicked(self, item: QListWidgetItem):
        self._popup.hide()
        self._select_fund(item.data(Qt.UserRole), item.data(Qt.UserRole + 1), item.text())

    def _select_fund(self, code, name, display: str):
        """Write the chosen fund back to the input and emit the selection."""
        self._suppress_next_text_change = True
        self.input.setText(display)
        self.fund_selected.emit(code, name)

    # ---- searching ---------------------------------------------------------

    def _on_text_changed(self, text: str):
        """Debounced text change handler.

        After a selection we rewrite the input text ourselves; this consumes
        the resulting textChanged so the dropdown doesn't reappear.
        """
        if self._suppress_next_text_change:
            self._suppress_next_text_change = False
            return
        self._debounce.start(SEARCH_DEBOUNCE_MS)

    def _on_debounced_text_changed(self):
        """Rebuild the dropdown with the top fuzzy matches for the query."""
        text = self.input.text().strip()
        if not text or self._index is None:
            self._list.clear()
            self._popup.hide()
            return

        t0 = time.perf_counter()
        matches = self._index.search(text, limit=POPUP_LIMIT)
        elapsed = (time.perf_counter() - t0) * 1000
        if elapsed > 100:
            logging.warning("fuzzy search took %.0f ms for %r", elapsed, text)

        self._list.clear()
        for r in matches:
            item = QListWidgetItem(f"{r.name} ({r.code})")
            item.setData(Qt.UserRole, r.code)
            item.setData(Qt.UserRole + 1, r.name)
            self._list.addItem(item)

        if matches:
            self._show_popup()
        else:
            self._popup.hide()

    def _show_popup(self):
        """Position and show the dropdown under the input, first row selected."""
        count = self._list.count()
        row_h = self._list.sizeHintForRow(0) if count else 20
        visible = min(count, POPUP_VISIBLE_ROWS)
        height = visible * (row_h + 2) + 4
        self._popup.resize(self.input.width(), max(height, 20))
        pos = self.input.mapToGlobal(QPoint(0, self.input.height() + 3))
        self._popup.move(pos)
        self._list.setCurrentRow(0)
        self._popup.show()

    def _on_return_pressed(self):
        """Commit via Enter when the dropdown is closed.

        When the dropdown is open, eventFilter intercepts Enter (selection
        path); this fires when the user commits a bare query directly (e.g.
        a 6-digit code, or a query that yields exactly one fuzzy hit).
        """
        text = self.input.text().strip()
        if not text:
            return

        code = self._extract_fund_code(text)
        if code:
            hit = self._all_funds_lookup.get(code)
            name = hit[1] if hit else code
            self.fund_selected.emit(code, name)
            return

        hit = self._display_lookup.get(text)
        if hit:
            self.fund_selected.emit(*hit)
        elif self._index is not None:
            matches = self._index.search(text, limit=2)
            if len(matches) == 1:
                self.fund_selected.emit(matches[0].code, matches[0].name)

    @staticmethod
    def _extract_fund_code(text: str):
        match = re.search(r"\d{6}", text)
        return match.group(0) if match else None

    def clear(self):
        self.input.clear()
        self._popup.hide()

    def shutdown(self):
        """Stop the background loader thread. Called on window close."""
        if getattr(self, "_loader_thread", None) is not None:
            self._loader_thread.quit()
            self._loader_thread.wait(2000)
