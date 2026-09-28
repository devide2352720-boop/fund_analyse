"""Background loader for the full fund list.

Runs get_all_funds() in a worker thread so the main window is never blocked
by the network request on startup. Moved to its own QThread by
FundSearchWidget; triggered via a signal so retry = re-emit.

The pinyin index (initials + full pinyin for every fund name) is also built
here, in the worker thread, so the main thread never stalls on pypinyin for
~20k names.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from app.search.fuzzy import build_records


class FundListLoader(QObject):
    """Loads the fund list and emits [FundRecord, ...] on success."""

    loaded = pyqtSignal(list)  # list of FundRecord (code, name, abbr, full)
    failed = pyqtSignal(str)

    def run(self):
        try:
            from app.data.fund_api import get_all_funds

            df = get_all_funds()
            if df is None or df.empty:
                self.failed.emit("基金列表为空")
                return

            code_col = "基金代码" if "基金代码" in df.columns else df.columns[0]
            name_col = "基金简称" if "基金简称" in df.columns else df.columns[1]

            items = [(str(row[code_col]), str(row[name_col])) for _, row in df.iterrows()]
            records = build_records(items)
            self.loaded.emit(records)
        except Exception as e:
            self.failed.emit(str(e))
