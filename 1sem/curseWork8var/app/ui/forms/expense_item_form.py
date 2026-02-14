from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from app.core.config import Config
from app.core.db import get_conn


class ExpenseItemForm(QDialog):
    def __init__(self, cfg: Config, role: str, record_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.record_id = record_id
        self.changed = False
        self.setWindowTitle("Статья расхода")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Название:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("ДОБАВИТЬ")
        self.btn_edit = QPushButton("ИЗМЕНИТЬ")
        self.btn_delete = QPushButton("УДАЛИТЬ")
        self.btn_close = QPushButton("ЗАКРЫТЬ")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_delete)
        btns.addStretch()
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self.btn_close.clicked.connect(self.reject)
        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_delete.clicked.connect(self.on_delete)

        if self.role != "admin":
            self.btn_add.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            # view-only for non-admin
            self.name_edit.setReadOnly(True)

        if self.record_id is not None:
            self._load()
        else:
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            if self.role != "admin":
                self.btn_add.setEnabled(False)

    def _load(self) -> None:
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM expense_items WHERE id = %s", (self.record_id,))
                    row = cur.fetchone()
            if not row:
                QMessageBox.critical(self, "Ошибка", "Запись не найдена")
                self.reject()
                return
            _id, name = row
            self.name_edit.setText(name)
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
            self.reject()

    def _validate(self) -> bool:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Введите название")
            return False
        return True

    def on_add(self) -> None:
        if not self._validate():
            return
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO expense_items(name) VALUES (%s) RETURNING id", (self.name_edit.text().strip(),))
                    new_id = cur.fetchone()[0]
                conn.commit()
            QMessageBox.information(self, "Добавлено", f"Добавлена запись id={new_id}")
            self.changed = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))

    def on_edit(self) -> None:
        if self.record_id is None:
            QMessageBox.warning(self, "Edit", "Нет выбранной записи")
            return
        if not self._validate():
            return
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE expense_items SET name=%s WHERE id=%s", (self.name_edit.text().strip(), self.record_id))
                conn.commit()
            QMessageBox.information(self, "Изменено", "Запись обновлена")
            self.changed = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))

    def on_delete(self) -> None:
        if self.record_id is None:
            QMessageBox.warning(self, "Delete", "Нет выбранной записи")
            return
        ok = QMessageBox.question(self, "Удалить", "Вы уверены?", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM expense_items WHERE id=%s", (self.record_id,))
                conn.commit()
            QMessageBox.information(self, "Удалено", "Запись удалена")
            self.changed = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
