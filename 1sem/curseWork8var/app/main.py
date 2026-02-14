import sys
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from app.core.config import load_config
from app.core.db import get_conn
from app.ui.main_window import MainWindow
from app.ui.login_window import LoginWindow


def test_db(cfg) -> None:
    """Raises on failure, returns None on success."""
    with get_conn(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def main():
    # Note: to run headless (CI / server without X) set env:
    #   QT_QPA_PLATFORM=offscreen  python -m app.main
    # or
    #   QT_QPA_PLATFORM=minimal   python -m app.main
    # We intentionally do not force any platform here — Qt will honor
    # `QT_QPA_PLATFORM` if provided by the caller.
    app = QApplication(sys.argv)

    try:
        cfg = load_config()
    except Exception as e:
        QMessageBox.critical(None, "Config error", str(e))
        return 1

    try:
        test_db(cfg)
    except Exception as e:
        QMessageBox.critical(None, "Database error", str(e))
        return 1

    login_win = LoginWindow(cfg)
    if login_win.exec() != QDialog.Accepted:
        return 0
    login = login_win.login
    role = login_win.role

    win = MainWindow(cfg=cfg, login=login, role=role)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
