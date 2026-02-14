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
    QFileDialog,
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
        self.btn_export = QPushButton("Экспорт в TXT")
        ctrl.addWidget(self.btn_export)
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
        self.btn_export.clicked.connect(self.export_to_txt)

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

    def export_to_txt(self) -> None:
        try:
            rows_count = self.model.rowCount()
            cols_count = self.model.columnCount()
            if rows_count == 0 or cols_count == 0:
                QMessageBox.warning(self, "Нет данных", "Нет данных для экспорта")
                return

            headers = list(getattr(self.model, "_headers", []))
            data_rows = getattr(self.model, "_rows", None) or getattr(self.model, "_data", None) or []
            data_rows = list(data_rows)

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить отчет",
                "",
                "Text files (*.txt)"
            )
            if not file_path:
                return
            if not file_path.lower().endswith(".txt"):
                file_path += ".txt"

            col_widths = []
            for c in range(len(headers)):
                max_w = len(str(headers[c]))
                for r in data_rows:
                    try:
                        val = r[c]
                    except Exception:
                        val = ""
                    max_w = max(max_w, len(str(val)))
                col_widths.append(max_w + 2)

            lines = []
            lines.append(f"Отчет: {self.title}")
            lines.append(f"Дата формирования: {date.today()}")
            lines.append("" + "-" * 40)

            header_line = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
            lines.append(header_line)
            lines.append("" + "-" * len(header_line))

            for r in data_rows:
                line = " | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers)))
                lines.append(line)

            text = "\n".join(lines)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)

            QMessageBox.information(self, "Экспорт", "Отчет успешно сохранён")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))
