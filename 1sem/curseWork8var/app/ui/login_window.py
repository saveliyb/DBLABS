from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)
from app.core.db import get_conn
from app.core.auth import verify_password
from app.core.config import Config


class LoginWindow(QDialog):
    """Simple login dialog. On success sets `login` and `role` attributes.

    Construct with a `Config` instance to allow DB access.
    """

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.login = None
        self.role = None
        self.setWindowTitle("Login")

        self.login_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # Buttons
        ok_btn = QPushButton("Войти")
        ok_btn.clicked.connect(self._try_login)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        # Enter key triggers: pressing Enter in login moves focus to password,
        # pressing Enter in password attempts login
        self.login_edit.returnPressed.connect(self.pass_edit.setFocus)
        self.pass_edit.returnPressed.connect(self._try_login)

        # UX niceties
        self.login_edit.setPlaceholderText("admin / operator")
        self.login_edit.setFocus()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Login:"))
        layout.addWidget(self.login_edit)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.pass_edit)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(ok_btn)
        h.addWidget(cancel_btn)
        layout.addLayout(h)

    def _try_login(self):
        login = self.login_edit.text().strip()
        password = self.pass_edit.text()
        # Minimal client-side validation — avoid unnecessary DB calls
        if not login:
            QMessageBox.warning(self, "Auth", "Введите логин")
            return
        if not password:
            QMessageBox.warning(self, "Auth", "Введите пароль")
            return
        try:
            with get_conn(self.cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pass_hash, role FROM app_users WHERE login = %s", (login,))
                    row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "Auth", "Пользователь не найден")
                return
            pass_hash, role = row
            ok = verify_password(password, pass_hash)
            if ok:
                self.login = login
                self.role = role
                self.accept()
            else:
                QMessageBox.warning(self, "Auth", "Неверный пароль")
        except Exception as e:
            QMessageBox.critical(self, "Auth error", str(e))
