from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, QModelIndex

from ...config import PostgresConfig
from ...repos import reports_repo
from .report_table_model import ReportTableModel, format_table_txt
from datetime import date
from PySide6.QtWidgets import QLabel, QLineEdit


class FinesReport(QWidget):
    def __init__(self, cfg: PostgresConfig, role: str, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.setWindowTitle('Отчёт: Штрафы')
        self.resize(900, 500)

        self.table = QTableView()

        self.lbl_from = QLabel('Дата с')
        self.le_from = QLineEdit()
        self.le_from.setPlaceholderText('YYYY-MM-DD')
        self.lbl_to = QLabel('по')
        self.le_to = QLineEdit()
        self.le_to.setPlaceholderText('YYYY-MM-DD')
        self.btn_apply = QPushButton('Применить')

        self.btn_refresh = QPushButton('Обновить')
        self.btn_export = QPushButton('Экспорт в TXT')
        self.btn_close = QPushButton('Закрыть')

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.lbl_from)
        filter_layout.addWidget(self.le_from)
        filter_layout.addWidget(self.lbl_to)
        filter_layout.addWidget(self.le_to)
        filter_layout.addWidget(self.btn_apply)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.table)
        main_layout.addLayout(btn_layout)

        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_apply.clicked.connect(self.load_data)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_close.clicked.connect(self.close)
        self.btn_reset = QPushButton('Сброс')
        self.btn_reset.clicked.connect(self.on_reset)
        try:
            btn_layout.addWidget(self.btn_reset)
        except Exception:
            pass

        self._columns = []
        self._rows = []
        self.load_data()

    def load_data(self):
        try:
            df = None
            dt = None
            if self.le_from.text().strip():
                try:
                    df = date.fromisoformat(self.le_from.text().strip())
                except Exception:
                    QMessageBox.warning(self, 'Ошибка', 'Неверный формат даты (Дата с)')
                    return
            if self.le_to.text().strip():
                try:
                    dt = date.fromisoformat(self.le_to.text().strip())
                except Exception:
                    QMessageBox.warning(self, 'Ошибка', 'Неверный формат даты (Дата по)')
                    return
            # validate date range
            if df and dt and df > dt:
                QMessageBox.warning(self, 'Ошибка', 'Дата с должна быть <= Дата по')
                return

            self._columns, self._rows = reports_repo.report_fines(self.cfg, df, dt)
            self.model = ReportTableModel(self._columns, self._rows)
            self.table.setModel(self.model)
            self.table.resizeColumnsToContents()
            try:
                self.setWindowTitle(f"Отчёт: Штрафы — строк: {len(self._rows)}")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить отчёт: {type(e).__name__}')

    def on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Сохранить отчёт', filter='Text files (*.txt)')
        if not path:
            return
        try:
            if not path.lower().endswith('.txt'):
                path = path + '.txt'
            header_lines = []
            header_lines.append(f"Generated: {date.today().isoformat()}")
            header_lines.append("Report: Fines")
            df_text = self.le_from.text().strip()
            dt_text = self.le_to.text().strip()
            header_lines.append(f"Date from: {df_text}")
            header_lines.append(f"Date to: {dt_text}")
            header_lines.append('')
            body = format_table_txt(self._columns, self._rows, max_col_width=40)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(header_lines) + '\n' + body)
            QMessageBox.information(self, 'OK', f'Сохранено: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'{type(e).__name__}: {e}')

    def on_reset(self):
        self.le_from.clear()
        self.le_to.clear()
        self.load_data()
