from typing import List, Dict, Optional
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QPushButton,
    QComboBox,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import traceback

from ..config import PostgresConfig
from ..repos import journal_repo, clients_repo, books_repo, book_types_repo


class LoanForm(QDialog):
    def __init__(self, cfg: PostgresConfig, role: str, table: str, columns_meta: List[Dict], pk_col: Optional[str], initial_row: Optional[Dict], mode: str = 'view', parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.role = role
        self.table = table
        self.columns_meta = columns_meta
        self.pk_col = pk_col
        self.initial_row = initial_row or {}
        self.mode = mode

        # detect real journal column mapping for this table
        try:
            self._jmap = journal_repo.get_journal_colmap(self.cfg, self.table)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Невозможно определить колонки журнала: {type(e).__name__}: {e}')
            self._jmap = {}

        # ensure book types repo exists; we will cache types if needed
        try:
            self._book_types = {t.get('id'): t for t in book_types_repo.list_types(self.cfg)}
        except Exception:
            self._book_types = {}

        self.setWindowTitle('Выдача')

        self.form = QFormLayout()
        self.widgets = {}

        # prepare clients and books lists
        try:
            ccols, crows = clients_repo.list_rows(self.cfg)
            client_cols = ccols
            clients = crows
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить список клиентов: {type(e).__name__}: {e}')
            client_cols = []
            clients = []

        try:
            bcols, brows = books_repo.list_rows(self.cfg)
            book_cols = bcols
            books = brows
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить список книг: {type(e).__name__}: {e}')
            book_cols = []
            books = []

        # store for later lookups
        self._book_cols = book_cols
        self._book_rows = books

        # map client id -> display
        self.client_map = {}
        if client_cols:
            id_index = client_cols.index('id') if 'id' in client_cols else 0
            disp_col = None
            for cand in ('name', 'fio', 'full_name', 'email'):
                if cand in client_cols:
                    disp_col = cand
                    break
            disp_index = client_cols.index(disp_col) if disp_col in client_cols else (1 if len(client_cols) > 1 else id_index)
            for r in clients:
                cid = r[id_index]
                self.client_map[cid] = str(r[disp_index])

        # map book id -> title display and availability
        self.book_map = {}
        if book_cols:
            id_index_b = book_cols.index('id') if 'id' in book_cols else 0
            title_index = id_index_b
            for cand in ('title', 'name'):
                if cand in book_cols:
                    title_index = book_cols.index(cand)
                    break
            for r in books:
                bid = r[id_index_b]
                title = str(r[title_index])
                try:
                    avail = journal_repo.is_book_available(self.cfg, self.table, bid)
                except Exception:
                    avail = True
                self.book_map[bid] = (title, avail)

        # Build form fields
        cb_client = QComboBox()
        cb_client.addItem('', None)
        for cid, disp in self.client_map.items():
            cb_client.addItem(disp, cid)
        if self.initial_row:
            cur = self._row_get('client_id')
            if cur is not None:
                idx = cb_client.findData(cur)
                if idx >= 0:
                    cb_client.setCurrentIndex(idx)

        self.widgets['client_id'] = cb_client
        self.form.addRow(QLabel('Клиент'), cb_client)

        cb_book = QComboBox()
        cb_book.addItem('', None)
        for bid, (title, avail) in self.book_map.items():
            disp = f"{title} ({'доступна' if avail else 'выдана'})"
            cb_book.addItem(disp, bid)
        if self.initial_row:
            cur = self._row_get('book_id')
            if cur is not None:
                idx = cb_book.findData(cur)
                if idx >= 0:
                    cb_book.setCurrentIndex(idx)

        self.widgets['book_id'] = cb_book
        self.form.addRow(QLabel('Книга'), cb_book)

        # when book selection changes, try to recalc due date
        try:
            cb_book.currentIndexChanged.connect(self._on_book_changed)
        except Exception:
            pass

        issued_le = QLineEdit()
        issued_val = self._row_get('issued_at')
        if issued_val is None:
            issued_le.setText(str(date.today()))
        else:
            issued_le.setText(str(issued_val))
        issued_le.setReadOnly(True)
        self.widgets['issued_at'] = issued_le
        self.form.addRow(QLabel('Дата выдачи'), issued_le)

        due_le = QLineEdit()
        due_val = self._row_get('due_at')
        if due_val is not None:
            due_le.setText(str(due_val))
        due_le.setReadOnly(True)
        self.widgets['due_at'] = due_le
        self.form.addRow(QLabel('Срок возврата'), due_le)

        returned_le = QLineEdit()
        ret_val = self._row_get('returned_at')
        if ret_val is not None:
            returned_le.setText(str(ret_val))
        returned_le.setReadOnly(True)
        self.widgets['returned_at'] = returned_le
        self.form.addRow(QLabel('Дата возврата'), returned_le)

        self.btn_issue = QPushButton('ВЫДАТЬ')
        self.btn_return = QPushButton('ПРИНЯТЬ')
        self.btn_close = QPushButton('ЗАКРЫТЬ')

        self.btn_issue.clicked.connect(self.on_issue)
        self.btn_return.clicked.connect(self.on_return)
        self.btn_close.clicked.connect(self.reject)

        btn_layout = QVBoxLayout()
        btn_layout.addWidget(self.btn_issue)
        btn_layout.addWidget(self.btn_return)
        btn_layout.addWidget(self.btn_close)

        outer = QVBoxLayout(self)
        outer.addLayout(self.form)
        outer.addLayout(btn_layout)

        if self.role != 'admin':
            self.btn_issue.setEnabled(False)
            self.btn_return.setEnabled(False)
        # mode-specific UI adjustments
        if self.mode == 'issue':
            # allow selecting client/book, issued_at is today, due_at editable (manual allowed)
            cb_client.setEnabled(True)
            cb_book.setEnabled(True)
            issued_le.setReadOnly(True)
            due_le.setReadOnly(False)
            try:
                due_le.setPlaceholderText('введите срок YYYY-MM-DD')
            except Exception:
                pass
            returned_le.setEnabled(False)
            self.btn_return.setEnabled(False)
            self.btn_issue.setEnabled(self.role == 'admin')
            # trigger initial due calc if possible
            try:
                self._on_book_changed()
            except Exception:
                pass
        elif self.mode == 'return':
            # show details read-only, returned_at editable (autofill today)
            cb_client.setEnabled(False)
            cb_book.setEnabled(False)
            issued_le.setReadOnly(True)
            due_le.setReadOnly(True)
            returned_le.setReadOnly(False)
            if not returned_le.text().strip():
                returned_le.setText(str(date.today()))
            self.btn_issue.setEnabled(False)
            self.btn_return.setEnabled(self.role == 'admin')
        else:  # view
            cb_client.setEnabled(False)
            cb_book.setEnabled(False)
            issued_le.setReadOnly(True)
            due_le.setReadOnly(True)
            returned_le.setReadOnly(True)
            self.btn_issue.setEnabled(False)
            self.btn_return.setEnabled(False)

    def on_issue(self):
        # UI feedback and robust error handling
        self.btn_issue.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            client_id = self.widgets['client_id'].currentData()
            book_id = self.widgets['book_id'].currentData()
            if client_id is None or book_id is None:
                QMessageBox.warning(self, 'Ошибка', 'Выберите клиента и книгу')
                return
            cnt = journal_repo.count_active_loans_for_client(self.cfg, self.table, client_id)
            if cnt >= 10:
                QMessageBox.warning(self, 'Отказ', 'У клиента уже 10 активных выдач')
                return
            if not journal_repo.is_book_available(self.cfg, self.table, book_id):
                QMessageBox.warning(self, 'Отказ', 'Книга уже выдана')
                return
            # use due_at from widget (computed or user-provided)
            due_text = self.widgets['due_at'].text().strip()
            if not due_text:
                QMessageBox.warning(self, 'Ошибка', 'Срок возврата не задан')
                return
            try:
                due = date.fromisoformat(due_text)
            except Exception:
                QMessageBox.warning(self, 'Ошибка', 'Неверный формат даты срока возврата')
                return

            # issued_at: prefer widget value
            issued_text = self.widgets.get('issued_at').text().strip() if self.widgets.get('issued_at') else ''
            try:
                issued = date.fromisoformat(issued_text) if issued_text else date.today()
            except Exception:
                issued = date.today()

            journal_repo.issue_book(self.cfg, self.table, client_id, book_id, issued, due)
            QMessageBox.information(self, 'OK', 'Книга выдана')
            self.accept()
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, 'Ошибка выдачи', f"{type(e).__name__}: {e}\n\n{tb}")
            print(tb, flush=True)
        finally:
            QApplication.restoreOverrideCursor()
            if self.isVisible():
                self.btn_issue.setEnabled(True)

    def on_return(self):
        # UI feedback and robust error handling for return
        self.btn_return.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            if not self.initial_row:
                QMessageBox.warning(self, 'Ошибка', 'Нет записи для возврата')
                return
            if not self.pk_col:
                QMessageBox.warning(self, 'Ошибка', 'Нет первичного ключа')
                return

            journal_id = self.initial_row.get(self.pk_col)
            if journal_id is None:
                QMessageBox.warning(self, 'Ошибка', 'Нет PK для возврата')
                return
            # use returned_at from widget (user may have edited)
            returned_text = self.widgets.get('returned_at').text().strip() if self.widgets.get('returned_at') else ''
            if not returned_text:
                QMessageBox.warning(self, 'Ошибка', 'Дата возврата не указана')
                return
            try:
                returned = date.fromisoformat(returned_text)
            except Exception:
                QMessageBox.warning(self, 'Ошибка', 'Неверный формат даты возврата')
                return

            due_str = self._row_get('due_at')
            fine_amount = 0.0
            if due_str:
                try:
                    due_date = date.fromisoformat(str(due_str))
                    days_over = (returned - due_date).days
                    if days_over > 0:
                        # determine rate: prefer journal bt_fine, then book_types fine
                        rate = float(self._row_get('bt_fine') or 0)
                        if rate == 0:
                            # try to find type_id from cached book rows
                            try:
                                bcols = getattr(self, '_book_cols', [])
                                brows = getattr(self, '_book_rows', [])
                                bid_idx = bcols.index('id') if 'id' in bcols else 0
                                type_idx = bcols.index('type_id') if 'type_id' in bcols else None
                                book_id = self._row_get('book_id')
                                type_id = None
                                if book_id is not None and type_idx is not None:
                                    for r in brows:
                                        if r[bid_idx] == book_id:
                                            type_id = r[type_idx]
                                            break
                                if type_id is not None:
                                    t = self._book_types.get(type_id) if getattr(self, '_book_types', None) else None
                                    if not t:
                                        try:
                                            types = book_types_repo.list_types(self.cfg)
                                            for tt in types:
                                                if tt.get('id') == type_id or list(tt.values())[0] == type_id:
                                                    t = tt
                                                    break
                                        except Exception:
                                            t = None
                                    if t:
                                        # look for common fine keys
                                        for fk in ('fine', 'bt_fine', 'fine_amount', 'penalty', 'rate'):
                                            if fk in t and t.get(fk) is not None:
                                                try:
                                                    rate = float(t.get(fk))
                                                except Exception:
                                                    rate = 0
                                                break
                            except Exception:
                                rate = 0
                        fine_amount = rate * days_over
                except Exception:
                    fine_amount = 0.0

            journal_repo.return_book(self.cfg, self.table, self.pk_col, journal_id, returned, fine_amount)
            QMessageBox.information(self, 'OK', 'Книга принята')
            self.accept()
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, 'Ошибка при приёме', f"{type(e).__name__}: {e}\n\n{tb}")
            print(tb, flush=True)
        finally:
            QApplication.restoreOverrideCursor()
            if self.isVisible():
                self.btn_return.setEnabled(True)

    def _on_book_changed(self):
        """Recalculate due date when book selection changes."""
        try:
            cb = self.widgets.get('book_id')
            if cb is None:
                return
            book_id = cb.currentData()
            if book_id is None:
                # clear due
                w = self.widgets.get('due_at')
                if w and self.mode == 'issue':
                    w.setReadOnly(False)  # default editable всегда

                if w:
                    w.setText('')
                    if self.mode == 'issue':
                        try:
                            w.setReadOnly(False)
                        except Exception:
                            pass
                return

            # find book row
            bcols = getattr(self, '_book_cols', [])
            brows = getattr(self, '_book_rows', [])
            bid_idx = bcols.index('id') if 'id' in bcols else 0
            type_idx = bcols.index('type_id') if 'type_id' in bcols else None
            btype = None
            for r in brows:
                if r[bid_idx] == book_id:
                    if type_idx is not None:
                        btype = r[type_idx]
                    break

            day_count = None
            if btype is not None:
                # try cache first
                t = self._book_types.get(btype)
                if not t:
                    try:
                        types = book_types_repo.list_types(self.cfg)
                        for tt in types:
                            if tt.get('id') == btype or list(tt.values())[0] == btype:
                                t = tt
                                break
                    except Exception:
                        t = None
                if t:
                    day_count = t.get('day_count')

            w = self.widgets.get('due_at')
            # only treat day_count as valid if it parses to int > 0
            if day_count is not None and w is not None:
                try:
                    dc = int(day_count)
                except Exception:
                    dc = 0
                if dc > 0:
                    # base due on issued_at field when possible
                    issued_txt = self.widgets.get('issued_at').text().strip() if self.widgets.get('issued_at') else ''
                    try:
                        issued_dt = date.fromisoformat(issued_txt) if issued_txt else date.today()
                    except Exception:
                        issued_dt = date.today()
                    due = issued_dt + timedelta(days=dc)
                    w.setText(str(due))
                    # since we have a computed due, lock it in issue mode
                    if self.mode == 'issue':
                        try:
                            w.setReadOnly(True)
                        except Exception:
                            pass
                else:
                    # invalid/zero day_count: keep due editable
                    try:
                        w.setPlaceholderText('введите срок YYYY-MM-DD')
                    except Exception:
                        pass
                    if self.mode == 'issue':
                        try:
                            w.setReadOnly(False)
                        except Exception:
                            pass
            else:
                # no automatic day_count -> leave existing due_at (allow manual input)
                if w:
                    # set a placeholder to hint manual input
                    try:
                        w.setPlaceholderText('введите срок YYYY-MM-DD')
                    except Exception:
                        pass
                    if self.mode == 'issue':
                        # default editable in issue mode
                        try:
                            w.setReadOnly(False)
                        except Exception:
                            pass
        except Exception:
            return

    # helpers to adapt to journal column naming
    def _jr(self, key: str) -> Optional[str]:
        """Return real column name for logical journal key, or None."""
        return self._jmap.get(key) if getattr(self, '_jmap', None) else None

    def _row_get(self, key: str):
        """Get value from initial_row using real column name or fallback key."""
        if not self.initial_row:
            return None
        real = self._jr(key)
        if real and real in self.initial_row:
            return self.initial_row.get(real)
        # fallback to logical key name if present
        return self.initial_row.get(key)
