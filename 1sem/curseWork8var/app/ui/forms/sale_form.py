from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QDate
from app.ui.forms._date_utils import _to_qdate
from app.core.config import Config
from app.core.db import get_conn


class SalesForm(QDialog):
    def __init__(self, cfg: Config, role: str, record_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.record_id = record_id
        self.changed = False
        self.setWindowTitle("Продажа")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Товар:"))
        self.goods_cb = QComboBox()
        layout.addWidget(self.goods_cb)

        layout.addWidget(QLabel("Кол-во:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 10 ** 9)
        layout.addWidget(self.qty_spin)

        layout.addWidget(QLabel("Цена за ед.:"))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.0, 1e9)
        self.amount_spin.setDecimals(2)
        layout.addWidget(self.amount_spin)

        layout.addWidget(QLabel("Дата продажи:"))
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

        # load goods for combobox
        self._load_goods()

        if self.role != "admin":
            self.btn_add.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            # view-only
            self.goods_cb.setEnabled(False)
            self.qty_spin.setEnabled(False)
            self.amount_spin.setEnabled(False)
            self.date_edit.setEnabled(False)

        if self.record_id is not None:
            self._load()
        else:
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)

    def _load_goods(self) -> None:
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, name FROM warehouses ORDER BY name")
                    rows = cur.fetchall()
            self.goods_cb.clear()
            for _id, name in rows:
                self.goods_cb.addItem(str(name), _id)
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))

    def _load(self) -> None:
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, warehouse_id, quantity, amount, sale_date FROM sales WHERE id=%s", (self.record_id,))
                    row = cur.fetchone()
            if not row:
                QMessageBox.critical(self, "Ошибка", "Запись не найдена")
                self.reject()
                return
            _id, warehouse_id, quantity, amount, sale_date = row
            # select warehouse in combobox
            idx = -1
            for i in range(self.goods_cb.count()):
                if self.goods_cb.itemData(i) == warehouse_id:
                    idx = i
                    break
            if idx >= 0:
                self.goods_cb.setCurrentIndex(idx)
            self.qty_spin.setValue(int(quantity) if quantity is not None else 1)
            try:
                self.amount_spin.setValue(float(amount) if amount is not None else 0.0)
            except Exception:
                self.amount_spin.setValue(0.0)
            qd = _to_qdate(sale_date)
            if qd is not None:
                self.date_edit.setDate(qd)
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
            self.reject()

    def _validate(self) -> bool:
        if self.goods_cb.currentIndex() < 0:
            QMessageBox.warning(self, "Validation", "Выберите товар")
            return False
        if self.qty_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Количество должно быть больше 0")
            return False
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Цена должна быть больше 0")
            return False
        return True

    def on_add(self) -> None:
        if not self._validate():
            return
        try:
            wid = self.goods_cb.currentData()
            qty = int(self.qty_spin.value())
            amt = float(self.amount_spin.value())
            d = self.date_edit.date().toPython()
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sales (warehouse_id, quantity, amount, sale_date) VALUES (%s, %s, %s, %s) RETURNING id",
                        (wid, qty, amt, d),
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
            wid = self.goods_cb.currentData()
            qty = int(self.qty_spin.value())
            amt = float(self.amount_spin.value())
            d = self.date_edit.date().toPython()
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE sales SET warehouse_id=%s, quantity=%s, amount=%s, sale_date=%s WHERE id=%s",
                        (wid, qty, amt, d, self.record_id),
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
                    cur.execute("DELETE FROM sales WHERE id=%s", (self.record_id,))
                conn.commit()
            QMessageBox.information(self, "Удалено", "Запись удалена")
            self.changed = True
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB error", str(e))
