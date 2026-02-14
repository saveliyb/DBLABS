import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .config import load_config
from .db import healthcheck
from .auth import ensure_users_table, ensure_default_users
from .ui.login import LoginWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("app")

    # locate config in current working directory
    cfg_path = Path("config.ini")
    try:
        cfg = load_config(str(cfg_path))
    except FileNotFoundError as e:
        logger.error(str(e))
        return
    except Exception as e:
        logger.error("Ошибка чтения config.ini: %s", e)
        return

    # Ensure users table and default users exist (best-effort)
    try:
        ensure_users_table(cfg)
        ensure_default_users(cfg)
    except Exception as e:
        logger.warning("Не удалось создать/инициализировать таблицу пользователей: %s", e)

    ok, msg = healthcheck(cfg)
    if ok:
        logger.info("DB: connected to %s:%s/%s", cfg.host, cfg.port, cfg.dbname)
    else:
        logger.error("DB healthcheck failed: %s", msg)

    app = QApplication(sys.argv)

    # Show a message box if DB not found? We'll show status inside LoginWindow
    login = LoginWindow(cfg, db_ok=ok, db_msg=msg)
    login.show()

    sys.exit(app.exec())
