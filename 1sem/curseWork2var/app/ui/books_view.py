from typing import List

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
from ..repos import books_repo
from .book_form import BookForm


class BooksTableModel(QAbstractTableModel):
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


class BooksView(QWidget):
    def __init__(self, cfg: PostgresConfig, role: str, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role

        self.setWindowTitle("Книги")
        self.resize(900, 400)

        self.table = QTableView()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_open = QPushButton("Открыть")
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Изменить")
        self.btn_delete = QPushButton("Удалить")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_open)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.table)
        main_layout.addLayout(btn_layout)

        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_open.clicked.connect(self.on_open)
        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_delete.clicked.connect(self.on_delete)
        self.table.doubleClicked.connect(self.on_double_click)

        if self.role != "admin":
            self.btn_add.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)

        self._columns = []
        self._rows = []
        self._pk = None
        self._fk = None

        self.load_data()

    def load_data(self):
        try:
            self._columns, self._rows = books_repo.list_rows_joined(self.cfg)
            self._pk = books_repo.get_pk(self.cfg)
            self._fk = books_repo.get_fk_to_table(self.cfg, 'book_types')
            self.model = BooksTableModel(self._columns, self._rows)
            self.table.setModel(self.model)
            self.table.resizeColumnsToContents()
            # disable edit/delete if no primary key
            if not self._pk:
                self.btn_edit.setEnabled(False)
                self.btn_delete.setEnabled(False)
            else:
                if self.role == "admin":
                    self.btn_edit.setEnabled(True)
                    self.btn_delete.setEnabled(True)
            # Hide extra bt_ columns, keep preferred ones if present
            bt_cols = [c for c in self._columns if c.startswith('bt_')]
            if bt_cols:
                preferred = [c for c in ('bt_type', 'bt_day_count', 'bt_fine') if c in self._columns]
                if not preferred:
                    # pick first up to 3 bt_ columns except those ending with '_id'
                    filtered = [c for c in bt_cols if not c.endswith('_id')]
                    preferred = filtered[:3] if filtered else bt_cols[:3]
                # hide others
                for i, col in enumerate(self._columns):
                    if col.startswith('bt_') and col not in preferred:
                        self.table.setColumnHidden(i, True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить книги: {type(e).__name__}")

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
        mode = "view" if self.role != "admin" else "edit"
        dlg = BookForm(self.cfg, self.role, books_repo.get_columns(self.cfg), self._pk, row, mode, parent=self)
        dlg.exec()
        self.load_data()

    def on_add(self):
        dlg = BookForm(self.cfg, self.role, books_repo.get_columns(self.cfg), self._pk, None, "add", parent=self)
        if dlg.exec() == 1:
            self.load_data()

    def on_edit(self):
        pk, row = self._get_selected()
        if row is None:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        if not self._pk:
            QMessageBox.warning(self, "Ошибка", "В таблице books нет первичного ключа")
            return
        dlg = BookForm(self.cfg, self.role, books_repo.get_columns(self.cfg), self._pk, row, "edit", parent=self)
        if dlg.exec() == 1:
            self.load_data()

    def on_delete(self):
        pk, row = self._get_selected()
        if row is None:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        if not self._pk:
            QMessageBox.warning(self, "Ошибка", "В таблице books нет первичного ключа")
            return
        ok = QMessageBox.question(self, "Подтвердите", "Удалить выбранную запись?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            books_repo.delete_row(self.cfg, self._pk, pk)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить запись: {type(e).__name__}")
