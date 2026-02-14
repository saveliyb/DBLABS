from PySide6.QtWidgets import (
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QMenuBar,
    QMenu,
    QToolBar,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from app.core.config import Config
from app.ui.widgets.grid_page import GridPage
from app.ui.forms.warehouse_form import WarehouseForm
from app.ui.forms.expense_item_form import ExpenseItemForm
from app.ui.forms.sale_form import SalesForm
from app.ui.forms.charge_form import ChargeForm
from app.ui.widgets.report_profit_page import ProfitReportPage
from app.ui.widgets.report_top5_page import Top5ReportPage


# Page keys
PAGE_GOODS = "goods"
PAGE_EXPENSES_ARTICLES = "expenses_articles"
PAGE_SALES = "sales"
PAGE_EXPENSES = "expenses"
PAGE_REPORT_PROFIT = "report_profit"
PAGE_REPORT_TOP5 = "report_top5"


class MainWindow(QMainWindow):
    def __init__(self, cfg: Config, login: str, role: str):
        super().__init__()
        self.cfg = cfg
        self.login = login
        self.role = role

        self.setWindowTitle("DB GUI – v0")
        central = QWidget()
        main_layout = QVBoxLayout(central)

        # Top info
        info_label = QLabel(f"Вы вошли как: {self.login} ({self.role})")
        info_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(info_label)

        # Stacked pages
        self.stacked = QStackedWidget()
        self.pages = {}
        # page_titles stores stable titles used for window caption
        self.page_titles: dict[str, str] = {}

        # Grid pages with real SQL (CP4)
        self._add_grid_page(
            PAGE_GOODS,
            "Справочники / Товары",
            sql="""
SELECT id, name, quantity, amount
FROM warehouses
ORDER BY id;
""",
            headers=["ID", "Название", "Кол-во", "Закупочная цена"],
        )

        self._add_grid_page(
            PAGE_EXPENSES_ARTICLES,
            "Справочники / Статьи расходов",
            sql="""
SELECT id, name
FROM expense_items
ORDER BY id;
""",
            headers=["ID", "Статья расхода"],
        )

        self._add_grid_page(
            PAGE_SALES,
            "Журналы / Продажи",
            sql="""
SELECT
  s.id,
  w.name AS good_name,
  s.quantity,
  s.amount,
  s.sale_date
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
ORDER BY s.id;
""",
            headers=["ID", "Товар", "Кол-во", "Цена за ед.", "Дата продажи"],
        )

        self._add_grid_page(
            PAGE_EXPENSES,
            "Журналы / Расходы",
            sql="""
SELECT
  c.id,
  e.name AS expense_item,
  c.amount,
  c.charge_date
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
ORDER BY c.id;
""",
            headers=["ID", "Статья", "Сумма", "Дата"],
        )
        # Reports pages
        rpt1 = ProfitReportPage(self.cfg, "Отчёты / Прибыль за месяц")
        self.pages[PAGE_REPORT_PROFIT] = rpt1
        self.stacked.addWidget(rpt1)
        self.page_titles[PAGE_REPORT_PROFIT] = "Отчёты / Прибыль за месяц"

        rpt2 = Top5ReportPage(self.cfg, "Отчёты / ТОП-5 доходных товаров")
        self.pages[PAGE_REPORT_TOP5] = rpt2
        self.stacked.addWidget(rpt2)
        self.page_titles[PAGE_REPORT_TOP5] = "Отчёты / ТОП-5 доходных товаров"

        main_layout.addWidget(self.stacked)
        self.setCentralWidget(central)

        # Menu (use canonical menuBar)
        menubar = self.menuBar()

        menu_refs = QMenu("СПРАВОЧНИКИ", self)
        act_goods = QAction("Товары", self)
        act_goods.triggered.connect(lambda: self.show_page(PAGE_GOODS))
        act_articles = QAction("Статьи расходов", self)
        act_articles.triggered.connect(lambda: self.show_page(PAGE_EXPENSES_ARTICLES))
        menu_refs.addAction(act_goods)
        menu_refs.addAction(act_articles)
        menubar.addMenu(menu_refs)

        menu_journals = QMenu("ЖУРНАЛЫ", self)
        act_sales = QAction("Продажи", self)
        act_sales.triggered.connect(lambda: self.show_page(PAGE_SALES))
        act_expenses = QAction("Расходы", self)
        act_expenses.triggered.connect(lambda: self.show_page(PAGE_EXPENSES))
        menu_journals.addAction(act_sales)
        menu_journals.addAction(act_expenses)
        menubar.addMenu(menu_journals)

        menu_reports = QMenu("ОТЧЁТЫ", self)
        act_profit = QAction("Прибыль за месяц", self)
        act_profit.triggered.connect(lambda: self.show_page(PAGE_REPORT_PROFIT))
        act_top5 = QAction("ТОП-5 доходных товаров", self)
        act_top5.triggered.connect(lambda: self.show_page(PAGE_REPORT_TOP5))
        menu_reports.addAction(act_profit)
        menu_reports.addAction(act_top5)
        menubar.addMenu(menu_reports)

        # Account menu: logout and exit
        menu_account = QMenu("АККАУНТ", self)
        act_logout = QAction("Выйти из аккаунта", self)
        act_exit = QAction("Выход", self)
        act_logout.triggered.connect(self.handle_logout)
        act_exit.triggered.connect(self.handle_exit)
        menu_account.addAction(act_logout)
        menu_account.addSeparator()
        menu_account.addAction(act_exit)
        menubar.addMenu(menu_account)

        # Toolbar with actions
        toolbar = QToolBar("Main toolbar", self)
        self.addToolBar(toolbar)

        self.act_add = QAction("Добавить", self)
        self.act_edit = QAction("Изменить", self)
        self.act_delete = QAction("Удалить", self)
        self.act_refresh = QAction("Обновить", self)

        for a in (self.act_add, self.act_edit, self.act_delete, self.act_refresh):
            toolbar.addAction(a)

        # Connect actions to CRUD handlers
        self.act_add.triggered.connect(self.handle_add)
        self.act_edit.triggered.connect(self.handle_edit)
        self.act_delete.triggered.connect(self.handle_delete)
        self.act_refresh.triggered.connect(self.on_refresh_triggered)

        # RBAC
        self.apply_rbac()

        # Status bar — final message (do not overwrite inside apply_rbac)
        if self.role in ("admin", "operator"):
            status = f"User: {self.login} | Role: {self.role}"
        else:
            status = f"User: {self.login} | Role: {self.role} (restricted mode)"
        self.statusBar().showMessage(status)

        # Show initial page (this will auto-load grid page)
        self.show_page(PAGE_GOODS)

    def _add_grid_page(self, key: str, title: str, sql: str, headers: list[str]) -> None:
        page = GridPage(self.cfg, title)
        page.set_query(sql, headers)
        self.pages[key] = page
        self.stacked.addWidget(page)
        self.page_titles[key] = title
        # connect double click to open editor/viewer
        try:
            page.view.doubleClicked.connect(lambda idx, k=key: self.on_table_double_click(k, idx.row()))
        except Exception:
            pass


    def _add_page(self, key: str, title: str) -> None:
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel(f"Раздел: {title} (в разработке)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.pages[key] = w
        self.stacked.addWidget(w)
        # store stable title (without developer suffix)
        self.page_titles[key] = title

    def show_page(self, key: str) -> None:
        widget = self.pages.get(key)
        if not widget:
            return
        self.stacked.setCurrentWidget(widget)
        self.current_page_key = key
        # Use stable page title for window caption
        title = self.page_titles.get(key, "")
        if title:
            self.setWindowTitle(f"DB GUI – {title}")
        else:
            self.setWindowTitle("DB GUI")

        # Auto-load grid pages once when shown
        if hasattr(widget, "refresh") and not getattr(widget, "loaded", False):
            # GridPage.refresh handles errors internally and will not re-raise
            widget.refresh()

    def on_refresh_triggered(self) -> None:
        widget = self.stacked.currentWidget()
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()
        else:
            QMessageBox.information(self, "Обновление", "Нечего обновлять")

    def apply_rbac(self) -> None:
        is_admin = (self.role == "admin")
        # Treat unknown roles as restricted/operator
        if not (self.role in ("admin", "operator")):
            is_admin = False

        self.act_add.setEnabled(is_admin)
        self.act_edit.setEnabled(is_admin)
        self.act_delete.setEnabled(is_admin)
        # Refresh always available
        self.act_refresh.setEnabled(True)

    # --- CRUD handlers ---
    def handle_add(self) -> None:
        key = getattr(self, "current_page_key", None)
        if key == PAGE_GOODS:
            dlg = WarehouseForm(self.cfg, self.role, record_id=None, parent=self)
        elif key == PAGE_EXPENSES_ARTICLES:
            dlg = ExpenseItemForm(self.cfg, self.role, record_id=None, parent=self)
        elif key == PAGE_SALES:
            dlg = SalesForm(self.cfg, self.role, record_id=None, parent=self)
        elif key == PAGE_EXPENSES:
            dlg = ChargeForm(self.cfg, self.role, record_id=None, parent=self)
        else:
            QMessageBox.information(self, "Добавить", "Добавление доступно только в справочниках и журналах")
            return
        res = dlg.exec()
        if getattr(dlg, "changed", False):
            # refresh the current page
            self.on_refresh_triggered()

    def handle_edit(self) -> None:
        key = getattr(self, "current_page_key", None)
        page = self.pages.get(key)
        if key == PAGE_GOODS:
            if not page:
                return
            rid = page.selected_id()
            if rid is None:
                QMessageBox.warning(self, "Изменить", "Выберите запись")
                return
            dlg = WarehouseForm(self.cfg, self.role, record_id=rid, parent=self)
        elif key == PAGE_EXPENSES_ARTICLES:
            if not page:
                return
            rid = page.selected_id()
            if rid is None:
                QMessageBox.warning(self, "Изменить", "Выберите запись")
                return
            dlg = ExpenseItemForm(self.cfg, self.role, record_id=rid, parent=self)
        elif key == PAGE_SALES:
            if not page:
                return
            rid = page.selected_id()
            if rid is None:
                QMessageBox.warning(self, "Изменить", "Выберите запись")
                return
            dlg = SalesForm(self.cfg, self.role, record_id=rid, parent=self)
        elif key == PAGE_EXPENSES:
            if not page:
                return
            rid = page.selected_id()
            if rid is None:
                QMessageBox.warning(self, "Изменить", "Выберите запись")
                return
            dlg = ChargeForm(self.cfg, self.role, record_id=rid, parent=self)
        else:
            QMessageBox.information(self, "Изменить", "Редактирование доступно только в справочниках и журналах")
            return
        res = dlg.exec()
        if getattr(dlg, "changed", False):
            self.on_refresh_triggered()

    def handle_delete(self) -> None:
        key = getattr(self, "current_page_key", None)
        page = self.pages.get(key)
        if key in (PAGE_GOODS, PAGE_EXPENSES_ARTICLES, PAGE_SALES, PAGE_EXPENSES):
            if not page:
                return
            rid = page.selected_id()
            if rid is None:
                QMessageBox.warning(self, "Удалить", "Выберите запись")
                return
            # open form so user can confirm delete
            if key == PAGE_GOODS:
                dlg = WarehouseForm(self.cfg, self.role, record_id=rid, parent=self)
            elif key == PAGE_EXPENSES_ARTICLES:
                dlg = ExpenseItemForm(self.cfg, self.role, record_id=rid, parent=self)
            elif key == PAGE_SALES:
                dlg = SalesForm(self.cfg, self.role, record_id=rid, parent=self)
            else:
                dlg = ChargeForm(self.cfg, self.role, record_id=rid, parent=self)
            res = dlg.exec()
            if getattr(dlg, "changed", False):
                self.on_refresh_triggered()
        else:
            QMessageBox.information(self, "Удалить", "Удаление доступно только в справочниках и журналах")

    def on_table_double_click(self, page_key: str, row: int) -> None:
        page = self.pages.get(page_key)
        if not page:
            return
        rid = None
        try:
            rid = page.id_at_row(row)
        except Exception:
            rid = None
        if rid is None:
            return
        # admin -> edit, operator -> view (buttons disabled by role)
        if page_key == PAGE_GOODS:
            dlg = WarehouseForm(self.cfg, self.role, record_id=rid, parent=self)
        elif page_key == PAGE_EXPENSES_ARTICLES:
            dlg = ExpenseItemForm(self.cfg, self.role, record_id=rid, parent=self)
        elif page_key == PAGE_SALES:
            dlg = SalesForm(self.cfg, self.role, record_id=rid, parent=self)
        elif page_key == PAGE_EXPENSES:
            dlg = ChargeForm(self.cfg, self.role, record_id=rid, parent=self)
        else:
            return
        res = dlg.exec()
        if getattr(dlg, "changed", False):
            self.on_refresh_triggered()

    def handle_logout(self) -> None:
        from PySide6.QtWidgets import QMessageBox, QDialog
        # confirmation
        ok = QMessageBox.question(self, "Выйти из аккаунта", "Выйти из текущего аккаунта?", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return

        # Prepare login window first — do not close current window until new main window is ready
        try:
            from app.ui.login_window import LoginWindow
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно входа: {e}")
            return

        try:
            login_win = LoginWindow(self.cfg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать окно входа: {e}")
            return

        if login_win.exec() == QDialog.Accepted:
            try:
                new_win = MainWindow(cfg=self.cfg, login=login_win.login, role=login_win.role)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать главное окно: {e}")
                return
            # store reference in a tiny app-level holder so GC won't collect it
            try:
                from app.ui import app_state
                app_state.main_window_ref = new_win
            except Exception:
                pass
            try:
                new_win.show()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось показать главное окно: {e}")
                return
            # close the old window safely on next event loop turn to avoid races
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.close)
            except Exception:
                # fallback to direct close if QTimer unavailable
                self.close()

    def handle_exit(self) -> None:
        from PySide6.QtWidgets import QMessageBox, QApplication
        ok = QMessageBox.question(self, "Выход", "Завершить приложение?", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        QApplication.quit()
