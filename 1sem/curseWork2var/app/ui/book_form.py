from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QCheckBox,
    QVBoxLayout,
    QPushButton,
    QComboBox,
)
from PySide6.QtCore import Qt

from ..config import PostgresConfig
from ..repos import books_repo, book_types_repo


class BookForm(QDialog):
    def __init__(
        self,
        cfg: PostgresConfig,
        role: str,
        columns_meta: List[Dict],
        pk_col: Optional[str],
        initial_row: Optional[Dict],
        mode: str = "view",
        parent=None,
    ):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.columns_meta = columns_meta
        self.pk_col = pk_col
        self.initial_row = initial_row or {}
        self.mode = mode

        self.setWindowTitle("Книга")

        self.form = QFormLayout()
        self.widgets: Dict[str, any] = {}

        # detect fk to book_types
        fk_info = books_repo.get_fk_to_table(self.cfg, 'book_types')
        fk_col = fk_info['column_name'] if fk_info else None

        # prepare book types for combo
        types = []
        if fk_col:
            try:
                types = book_types_repo.list_types(self.cfg)
            except Exception:
                types = []

        for col in self.columns_meta:
            name = col["column_name"]
            dtype = col["data_type"]
            is_nullable = col["is_nullable"]

            # skip pk in add mode
            if name == self.pk_col and self.mode == "add":
                continue

            if name == fk_col:
                cb = QComboBox()
                cb.addItem("", None)
                for t in types:
                    # determine id
                    keys = list(t.keys())
                    tid = t.get('id') if 'id' in t else t[keys[0]]
                    # improved display: prefer type/name/day_count/fine
                    type_name = t.get('type') or t.get('name') or t.get('type_name')
                    day_count = t.get('day_count')
                    fine = t.get('fine')
                    if type_name:
                        parts = [str(type_name)]
                        extra = []
                        if day_count is not None:
                            extra.append(f"days={day_count}")
                        if fine is not None:
                            extra.append(f"fine={fine}")
                        if extra:
                            parts.append(f"({', '.join(extra)})")
                        disp = " ".join(parts)
                    else:
                        disp_parts = [str(t[k]) for k in keys if k != (keys[0])]
                        disp = " | ".join(disp_parts) if disp_parts else str(tid)
                    cb.addItem(disp, tid)
                # select current
                cur = self.initial_row.get(name)
                if cur is not None:
                    idx = cb.findData(cur)
                    if idx >= 0:
                        cb.setCurrentIndex(idx)
                w = cb
            elif dtype in ("boolean",):
                w = QCheckBox()
                val = self.initial_row.get(name)
                w.setChecked(bool(val))
            else:
                w = QLineEdit()
                val = self.initial_row.get(name)
                if val is not None:
                    w.setText(str(val))

            if name == self.pk_col:
                try:
                    w.setReadOnly(True)
                except Exception:
                    pass
                try:
                    w.setEnabled(False)
                except Exception:
                    pass

            self.widgets[name] = w
            label = QLabel(f"{name}")
            self.form.addRow(label, w)

        # buttons
        self.btn_add = QPushButton("ДОБАВИТЬ")
        self.btn_update = QPushButton("ИЗМЕНИТЬ")
        self.btn_delete = QPushButton("УДАЛИТЬ")
        self.btn_close = QPushButton("ЗАКРЫТЬ")

        self.btn_add.clicked.connect(self.on_add)
        self.btn_update.clicked.connect(self.on_update)
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_close.clicked.connect(self.reject)

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_update)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_close)

        outer = QVBoxLayout(self)
        outer.addLayout(self.form)
        outer.addLayout(btn_layout)

        # Mode/role adjustments (same rules as ClientForm)
        self.btn_add.setEnabled(True)
        self.btn_update.setEnabled(True)
        self.btn_delete.setEnabled(True)
        if self.role != "admin":
            self.btn_add.setEnabled(False)
            self.btn_update.setEnabled(False)
            self.btn_delete.setEnabled(False)

        if self.mode == "add":
            self.btn_update.setEnabled(False)
            self.btn_delete.setEnabled(False)
            if self.pk_col and self.widgets.get(self.pk_col):
                try:
                    self.widgets[self.pk_col].setText("")
                except Exception:
                    pass
        elif self.mode == "edit":
            self.btn_add.setEnabled(False)
        elif self.mode == "view":
            self.btn_add.setEnabled(False)
            self.btn_update.setEnabled(False)
            self.btn_delete.setEnabled(False)

    def _gather(self) -> Dict:
        data = {}
        for col in self.columns_meta:
            name = col["column_name"]
            widget = self.widgets.get(name)
            if widget is None:
                data[name] = None
                continue
            if isinstance(widget, QCheckBox):
                data[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                data[name] = widget.currentData()
            else:
                text = widget.text().strip()
                data[name] = text if text != "" else None
        return data

    def _validate_not_null(self, data: Dict) -> Optional[str]:
        for col in self.columns_meta:
            if col["is_nullable"] == "NO":
                name = col["column_name"]
                if name == self.pk_col:
                    continue
                if data.get(name) is None:
                    return name
        return None

    def on_add(self):
        data = self._gather()
        missing = self._validate_not_null(data)
        if missing:
            QMessageBox.warning(self, "Ошибка", f"Поле {missing} обязательно")
            return
        try:
            books_repo.insert_row(self.cfg, data, self.pk_col)
            QMessageBox.information(self, "OK", "Запись добавлена")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить запись: {type(e).__name__}")

    def on_update(self):
        if not self.pk_col:
            QMessageBox.warning(self, "Ошибка", "Нет PK для обновления")
            return
        data = self._gather()
        pk_val = self.initial_row.get(self.pk_col)
        if pk_val is None:
            QMessageBox.warning(self, "Ошибка", "Отсутствует значение PK")
            return
        try:
            books_repo.update_row(self.cfg, self.pk_col, pk_val, data)
            QMessageBox.information(self, "OK", "Запись обновлена")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить запись: {type(e).__name__}")

    def on_delete(self):
        if not self.pk_col:
            QMessageBox.warning(self, "Ошибка", "Нет PK для удаления")
            return
        pk_val = self.initial_row.get(self.pk_col)
        if pk_val is None:
            QMessageBox.warning(self, "Ошибка", "Отсутствует значение PK")
            return
        ok = QMessageBox.question(self, "Подтвердите", "Удалить запись?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            books_repo.delete_row(self.cfg, self.pk_col, pk_val)
            QMessageBox.information(self, "OK", "Запись удалена")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить запись: {type(e).__name__}")
