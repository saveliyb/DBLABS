from typing import List
from datetime import date

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QMessageBox,
)
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from ..config import PostgresConfig
from ..repos import journal_repo
from .loan_form import LoanForm


class LoansTableModel(QAbstractTableModel):
    def __init__(self, columns: List[str], rows: List[tuple]):
        super().__init__()
        self._columns = columns
        self._rows = rows

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._rows[index.row()][index.column()]
            return "" if val is None else str(val)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section]
        return section + 1


class LoansView(QWidget):
    def __init__(self, cfg: PostgresConfig, role: str, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role

        self.setWindowTitle("Выдачи")
        self.resize(1000, 500)

        self.table = QTableView()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_open = QPushButton("Открыть")
        self.btn_issue = QPushButton("Выдать")
        self.btn_return = QPushButton("Принять")
        self.btn_delete = QPushButton("Удалить")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_open)
        btn_layout.addWidget(self.btn_issue)
        btn_layout.addWidget(self.btn_return)
        btn_layout.addWidget(self.btn_delete)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.table)
        main_layout.addLayout(btn_layout)

        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_open.clicked.connect(self.on_open)
        self.btn_issue.clicked.connect(self.on_issue)
        self.btn_return.clicked.connect(self.on_return)
        self.btn_delete.clicked.connect(self.on_delete)
        self.table.doubleClicked.connect(self.on_double_click)

        if self.role != 'admin':
            self.btn_issue.setEnabled(False)
            self.btn_return.setEnabled(False)
            self.btn_delete.setEnabled(False)

        self._table = journal_repo.detect_journal_table(self.cfg)
        self._pk = journal_repo.get_pk(self.cfg, self._table)

        self._columns = []
        self._rows = []
        self.load_data()

    def load_data(self):
        try:
            self._columns, self._rows = journal_repo.list_rows_joined(self.cfg, self._table)
            self.model = LoansTableModel(self._columns, self._rows)
            self.table.setModel(self.model)
            self.table.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить журнал: {type(e).__name__}")

    def _get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None, None
        row = idx.row()
        row_values = self._rows[row]
        row_dict = {col: row_values[i] for i, col in enumerate(self._columns)}
        pk_val = row_dict.get(self._pk) if self._pk else None
        return pk_val, row_dict

    def on_double_click(self, index):
        self.on_open()

    def on_open(self):
        pk, row = self._get_selected()
        if row is None:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        dlg = LoanForm(self.cfg, self.role, self._table, journal_repo.get_columns(self.cfg, self._table), self._pk, row, mode='view', parent=self)
        dlg.exec()
        self.load_data()

    def on_issue(self):
        dlg = LoanForm(self.cfg, self.role, self._table, journal_repo.get_columns(self.cfg, self._table), self._pk, None, mode='issue', parent=self)
        if dlg.exec() == 1:
            self.load_data()

    def on_return(self):
        pk, row = self._get_selected()
        if row is None:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        if not self._pk:
            QMessageBox.warning(self, "Ошибка", "В таблице журнала нет первичного ключа")
            return
        # quick return: if already returned -> inform
        if row.get('returned_at') is not None:
            QMessageBox.information(self, "Инфо", "Книга уже возвращена")
            return
        dlg = LoanForm(self.cfg, self.role, self._table, journal_repo.get_columns(self.cfg, self._table), self._pk, row, mode='return', parent=self)
        if dlg.exec() == 1:
            self.load_data()

    def on_delete(self):
        pk, row = self._get_selected()
        if row is None:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        if not self._pk:
            QMessageBox.warning(self, "Ошибка", "В таблице журнала нет первичного ключа")
            return
        ok = QMessageBox.question(self, "Подтвердите", "Удалить выбранную запись?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            journal_repo.delete_row(self.cfg, self._table, self._pk, pk)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить запись: {type(e).__name__}")
