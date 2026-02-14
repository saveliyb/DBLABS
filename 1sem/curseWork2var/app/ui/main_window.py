from typing import Dict

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtGui import QAction


class MainWindow(QMainWindow):
    def __init__(self, cfg, username: str | None = None, role: str | None = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.username = username
        self.role = role
        self.setWindowTitle("Library — Main")
        self.resize(800, 600)
        # central stacked widget to host different screens
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._views: Dict[str, QMainWindow] = {}

        self._init_menu()
        self._init_status()

    def _init_menu(self):
        menubar = self.menuBar()

        self.refs_menu = menubar.addMenu("СПРАВОЧНИКИ")
        self.journals_menu = menubar.addMenu("ЖУРНАЛЫ")
        self.reports_menu = menubar.addMenu("ОТЧЕТЫ")

        # Clients action
        clients_action = QAction("Клиенты", self)
        clients_action.triggered.connect(self.open_clients)
        self.refs_menu.addAction(clients_action)

        # Books action
        books_action = QAction("Книги", self)
        books_action.triggered.connect(self.open_books)
        self.refs_menu.addAction(books_action)

        # Loans/Issues
        loans_action = QAction("Выдачи", self)
        loans_action.triggered.connect(self.open_loans)
        self.journals_menu.addAction(loans_action)

        active_action = QAction("Активные выдачи", self)
        active_action.triggered.connect(self.open_report_active_loans)
        self.reports_menu.addAction(active_action)

        fines_action = QAction("Штрафы", self)
        fines_action.triggered.connect(self.open_report_fines)
        self.reports_menu.addAction(fines_action)

        # Do not disable whole СПРАВОЧНИКИ menu; CRUD restrictions handled in views/forms

    def _init_status(self):
        if self.username and self.role:
            if self.role == "admin":
                self.statusBar().showMessage(f"Вы вошли как {self.username} (admin)")
            else:
                self.statusBar().showMessage(f"Вы вошли как {self.username} ({self.role}) — только просмотр")
        else:
            self.statusBar().showMessage("Добро пожаловать")

    def open_clients(self):
        try:
            from .clients_view import ClientsView

            key = 'clients'
            if key not in self._views:
                view = ClientsView(self.cfg, self.role, parent=self._stack)
                self._views[key] = view
                self._stack.addWidget(view)
            view = self._views[key]
            self._stack.setCurrentWidget(view)
            # update main window title to reflect current view
            self.setWindowTitle(f"Library — {view.windowTitle()}")
        except Exception as e:
            self.statusBar().showMessage(f"Не удалось открыть Клиенты: {type(e).__name__}")

    def open_books(self):
        try:
            from .books_view import BooksView

            key = 'books'
            if key not in self._views:
                view = BooksView(self.cfg, self.role, parent=self._stack)
                self._views[key] = view
                self._stack.addWidget(view)
            view = self._views[key]
            self._stack.setCurrentWidget(view)
            self.setWindowTitle(f"Library — {view.windowTitle()}")
        except Exception as e:
            self.statusBar().showMessage(f"Не удалось открыть Книги: {type(e).__name__}")

    def open_loans(self):
        try:
            from .loans_view import LoansView

            key = 'loans'
            if key not in self._views:
                view = LoansView(self.cfg, self.role, parent=self._stack)
                self._views[key] = view
                self._stack.addWidget(view)
            view = self._views[key]
            self._stack.setCurrentWidget(view)
            self.setWindowTitle(f"Library — {view.windowTitle()}")
        except Exception as e:
            self.statusBar().showMessage(f"Не удалось открыть Выдачи: {type(e).__name__}")

    def open_report_active_loans(self):
        try:
            from .reports.active_loans_report import ActiveLoansReport

            key = 'report_active_loans'
            if key not in self._views:
                view = ActiveLoansReport(self.cfg, self.role, parent=self._stack)
                self._views[key] = view
                self._stack.addWidget(view)
            view = self._views[key]
            self._stack.setCurrentWidget(view)
            self.setWindowTitle(f"Library — {view.windowTitle()}")
        except Exception as e:
            self.statusBar().showMessage(f"Не удалось открыть отчёт: {type(e).__name__}")

    def open_report_fines(self):
        try:
            from .reports.fines_report import FinesReport

            key = 'report_fines'
            if key not in self._views:
                view = FinesReport(self.cfg, self.role, parent=self._stack)
                self._views[key] = view
                self._stack.addWidget(view)
            view = self._views[key]
            self._stack.setCurrentWidget(view)
            self.setWindowTitle(f"Library — {view.windowTitle()}")
        except Exception as e:
            self.statusBar().showMessage(f"Не удалось открыть отчёт: {type(e).__name__}")
