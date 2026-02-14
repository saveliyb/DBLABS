from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QDateEdit,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QDate
from app.ui.forms._date_utils import _to_qdate
from app.core.config import Config
from app.core.db import get_conn


class ChargeForm(QDialog):
    def __init__(self, cfg: Config, role: str, record_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.record_id = record_id
        self.changed = False
        self.setWindowTitle("Списание")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Статья расхода:"))
        self.item_cb = QComboBox()
        layout.addWidget(self.item_cb)

        layout.addWidget(QLabel("Сумма:"))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.0, 1e12)
        self.amount_spin.setDecimals(2)
        layout.addWidget(self.amount_spin)

        layout.addWidget(QLabel("Дата списания:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addWidget(self.date_edit)

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

        self._load_items()

        if self.role != "admin":
            self.btn_add.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.item_cb.setEnabled(False)
            self.amount_spin.setEnabled(False)
            self.date_edit.setEnabled(False)

        if self.record_id is not None:
            self._load()
        else:
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)

    def _load_items(self) -> None:
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM expense_items ORDER BY name")
                    rows = cur.fetchall()
            self.item_cb.clear()
            for _id, name in rows:
                self.item_cb.addItem(str(name), _id)
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))

    def _load(self) -> None:
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, expense_item_id, amount, charge_date FROM charges WHERE id=%s", (self.record_id,))
                    row = cur.fetchone()
            if not row:
                QMessageBox.critical(self, "Ошибка", "Запись не найдена")
                self.reject()
                return
            _id, expense_item_id, amount, charge_date = row
            idx = -1
            for i in range(self.item_cb.count()):
                if self.item_cb.itemData(i) == expense_item_id:
                    idx = i
                    break
            if idx >= 0:
                self.item_cb.setCurrentIndex(idx)
            try:
                self.amount_spin.setValue(float(amount) if amount is not None else 0.0)
            except Exception:
                self.amount_spin.setValue(0.0)
            qd = _to_qdate(charge_date)
            if qd is not None:
                self.date_edit.setDate(qd)
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
            self.reject()

    def _validate(self) -> bool:
        if self.item_cb.currentIndex() < 0:
            QMessageBox.warning(self, "Validation", "Выберите статью расхода")
            return False
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Сумма должна быть больше 0")
            return False
        return True

    def on_add(self) -> None:
        if not self._validate():
            return
        try:
            item_id = self.item_cb.currentData()
            amt = float(self.amount_spin.value())
            d = self.date_edit.date().toPython()
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO charges (expense_item_id, amount, charge_date) VALUES (%s, %s, %s) RETURNING id",
                        (item_id, amt, d),
                    )
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
            item_id = self.item_cb.currentData()
            amt = float(self.amount_spin.value())
            d = self.date_edit.date().toPython()
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE charges SET expense_item_id=%s, amount=%s, charge_date=%s WHERE id=%s",
                        (item_id, amt, d, self.record_id),
                    )
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
                    cur.execute("DELETE FROM charges WHERE id=%s", (self.record_id,))
                conn.commit()
            QMessageBox.information(self, "Удалено", "Запись удалена")
            self.changed = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
