from typing import List, Sequence, Any
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QTableView, QMessageBox
from PySide6.QtCore import Qt
from app.ui.widgets.table_model import TableModel
from app.core.db import get_conn
from app.core.config import Config
from PySide6.QtWidgets import QAbstractItemView


class GridPage(QWidget):
    """Generic grid page showing results of a SQL query in a QTableView.

    Usage:
      page = GridPage(cfg, title)
      page.set_query(sql, headers)
      page.refresh()
    """

    def __init__(self, cfg: Config, title: str):
        super().__init__()
        self.cfg = cfg
        self.title = title
        self._sql: str | None = None
        self._headers: List[str] = []
        self._loaded = False

        layout = QVBoxLayout(self)
        # Page title — table is real now, no "(в разработке)"
        self.title_label = QLabel(f"Раздел: {title}")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.view = QTableView()
        self.model = TableModel([], [])
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.view)

    @property
    def loaded(self) -> bool:
        return self._loaded

    def set_query(self, sql: str, headers: Sequence[str]) -> None:
        """Set the SQL query and column headers for this page."""
        self._sql = sql
        self._headers = list(headers)

    def selected_row_index(self) -> int | None:
        sm = self.view.selectionModel()
        if not sm:
            return None
        rows = sm.selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def selected_row(self) -> list[Any] | None:
        idx = self.selected_row_index()
        if idx is None:
            return None
        try:
            return self.model.row_values(idx)
        except Exception:
            return None

    def selected_id(self) -> int | None:
        idx = self.selected_row_index()
        if idx is None:
            return None
        return self.id_at_row(idx)

    def id_at_row(self, row: int) -> int | None:
        vals = self.model.row_values(row)
        if not vals:
            return None
        try:
            v = vals[0]
            return int(v) if v is not None else None
        except Exception:
            return None

    def refresh(self) -> None:
        if not self._sql:
            return
        try:
            rows = []
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(self._sql)
                    rows = cur.fetchall()
            # update model
            self.model.set_data(self._headers, rows)
            try:
                self.view.resizeColumnsToContents()
            except Exception:
                pass
            self._loaded = True
        except Exception as e:
            # ensure loaded flag reflects state
            self._loaded = False
            QMessageBox.critical(self, "DB error", str(e))
