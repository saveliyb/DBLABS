import logging
from typing import Optional, Tuple

import bcrypt

from .config import PostgresConfig
from .db import get_connection

logger = logging.getLogger(__name__)


def ensure_users_table(cfg: PostgresConfig) -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS app_users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('admin','user')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
    finally:
        conn.close()


def ensure_default_users(cfg: PostgresConfig) -> None:
    # default credentials (for CP2 demo)
    defaults = [
        ("admin", "admin123", "admin"),
        ("user", "user123", "user"),
    ]

    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            for username, password, role in defaults:
                ph = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                cur.execute(
                    "INSERT INTO app_users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                    (username, ph, role),
                )
        conn.commit()
    finally:
        conn.close()


def authenticate(cfg: PostgresConfig, username: str, password: str) -> Tuple[bool, Optional[str]]:
    try:
        conn = get_connection(cfg)
    except Exception as e:
        logger.error("DB connection failed during authenticate: %s", type(e).__name__)
        return False, None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, role FROM app_users WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                return False, None

            stored_hash, role = row
            if stored_hash is None:
                return False, None

            try:
                ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
            except Exception:
                return False, None

            if ok:
                return True, role
            return False, None
    finally:
        conn.close()
