from .config import Config
import psycopg


def get_conn(cfg: Config):
    """Return a new psycopg connection using values from Config.

    Caller is responsible for closing the connection.
    """
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
    )
