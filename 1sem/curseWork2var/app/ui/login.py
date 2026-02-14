from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)
from PySide6.QtCore import Qt

from .main_window import MainWindow
from ..auth import authenticate
from ..config import PostgresConfig


class LoginWindow(QWidget):
    def __init__(self, db_cfg: PostgresConfig, db_ok: bool, db_msg: str, parent=None):
        super().__init__(parent)
        self.db_cfg = db_cfg
        self.db_ok = db_ok
        self.db_msg = db_msg

        self.setWindowTitle("Library — Login")

        self.user_label = QLabel("Username:")
        self.user_input = QLineEdit()

        self.pass_label = QLabel("Password:")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.status_label = QLabel()
        self.update_db_status()

        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self.on_login)

        form_layout = QVBoxLayout()
        form_layout.addWidget(self.user_label)
        form_layout.addWidget(self.user_input)
        form_layout.addWidget(self.pass_label)
        form_layout.addWidget(self.pass_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.login_btn)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def update_db_status(self):
        if self.db_ok:
            self.status_label.setText("DB: connected")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText(f"DB: error — {self.db_msg}")
            self.status_label.setStyleSheet("color: red")

    def on_login(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text().strip()

        if not username or not password:
            self.status_label.setText("Введите логин и пароль")
            self.status_label.setStyleSheet("color: orange")
            return

        if not self.db_ok:
            self.status_label.setText("Нет подключения к БД")
            self.status_label.setStyleSheet("color: red")
            return

        # Real authentication in CP2
        ok, role = authenticate(self.db_cfg, username, password)
        if not ok:
            self.status_label.setText("Неверный логин или пароль")
            self.status_label.setStyleSheet("color: red")
            return

        self.open_main(username=username, role=role)

    def open_main(self, username: str, role: str):
        self.main_win = MainWindow(cfg=self.db_cfg, username=username, role=role)
        self.main_win.show()
        self.close()
