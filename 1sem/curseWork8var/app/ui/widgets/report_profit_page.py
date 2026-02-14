from datetime import date, timedelta
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


class ProfitReportPage(QWidget):
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
        # compute month start and next month start
        try:
            qdate = self.date_edit.date()
            year = qdate.year()
            month = qdate.month()
            start = date(year, month, 1)
            # next month
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)

            sql_sales = "SELECT COALESCE(SUM(s.quantity * s.amount),0) FROM sales s WHERE s.sale_date >= %s AND s.sale_date < %s"
            sql_charges = "SELECT COALESCE(SUM(c.amount),0) FROM charges c WHERE c.charge_date >= %s AND c.charge_date < %s"

            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_sales, (start, end))
                    total_sales = cur.fetchone()[0]
                    cur.execute(sql_charges, (start, end))
                    total_charges = cur.fetchone()[0]

            # keep DB numeric types (Decimal/int) — TableModel will stringify
            total_sales = total_sales or 0
            total_charges = total_charges or 0
            profit = total_sales - total_charges
            month_str = f"{year:04d}-{month:02d}"
            rows = [[month_str, total_sales, total_charges, profit]]
            headers = ["Месяц", "Выручка", "Расходы", "Прибыль"]
            self.model.set_data(headers, rows)
            try:
                self.view.resizeColumnsToContents()
            except Exception:
                pass
            self._loaded = True
        except Exception as e:
            self._loaded = False
            QMessageBox.critical(self, "DB error", str(e))
