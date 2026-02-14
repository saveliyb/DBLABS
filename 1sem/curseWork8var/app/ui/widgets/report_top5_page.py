from datetime import date
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QDateEdit,
    QPushButton,
    QTableView,
    QMessageBox,
)
from PySide6.QtCore import Qt, QDate
from app.ui.widgets.table_model import TableModel
from app.core.db import get_conn
from app.core.config import Config
from PySide6.QtWidgets import QAbstractItemView


class Top5ReportPage(QWidget):
    def __init__(self, cfg: Config, title: str):
        super().__init__()
        self.cfg = cfg
        self.title = title
        self._loaded = False

        layout = QVBoxLayout(self)
        self.title_label = QLabel(f"Раздел: {title}")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Месяц:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("yyyy-MM")
        self.date_edit.setCalendarPopup(True)
        # default to first day of current month
        d = QDate.currentDate()
        self.date_edit.setDate(QDate(d.year(), d.month(), 1))
        ctrl.addWidget(self.date_edit)
        self.btn_gen = QPushButton("Сформировать")
        ctrl.addWidget(self.btn_gen)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.view = QTableView()
        self.model = TableModel([], [])
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.view)

        self.btn_gen.clicked.connect(self.refresh)

    @property
    def loaded(self) -> bool:
        return self._loaded

    def refresh(self) -> None:
        try:
            qdate = self.date_edit.date()
            year = qdate.year()
            month = qdate.month()
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)

            sql = """
SELECT w.id, w.name, COALESCE(SUM(s.quantity * s.amount),0) AS revenue
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE s.sale_date >= %s AND s.sale_date < %s
GROUP BY w.id, w.name
ORDER BY revenue DESC
LIMIT 5
"""
            rows = []
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (start, end))
                    rows = cur.fetchall()

            headers = ["ID", "Товар", "Выручка"]
            self.model.set_data(headers, rows)
            try:
                self.view.resizeColumnsToContents()
            except Exception:
                pass
            self._loaded = True
        except Exception as e:
            self._loaded = False
            QMessageBox.critical(self, "DB error", str(e))
