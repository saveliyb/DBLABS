import logging
from typing import Tuple

import psycopg

from .config import PostgresConfig

logger = logging.getLogger(__name__)


def get_connection(cfg: PostgresConfig):
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=cfg.connect_timeout,
    )


def healthcheck(cfg: PostgresConfig) -> Tuple[bool, str]:
    try:
        conn = get_connection(cfg)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        finally:
            conn.close()
        return True, "OK"
    except Exception as e:
        logger.error("DB connection failed to %s:%s/%s: %s", cfg.host, cfg.port, cfg.dbname, str(e))
        # Return a readable message without password or full DSN
        return False, f"Не удалось подключиться к {cfg.host}:{cfg.port}/{cfg.dbname}: {e.__class__.__name__}"
