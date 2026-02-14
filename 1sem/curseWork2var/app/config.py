from dataclasses import dataclass
from configparser import ConfigParser
from pathlib import Path
from typing import Optional


@dataclass
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    connect_timeout: int = 3


def load_config(path: Optional[str | Path] = None) -> PostgresConfig:
    cfg_path = Path(path or "config.ini")
    if not cfg_path.exists():
        raise FileNotFoundError("создай config.ini на основе config.ini.example")

    parser = ConfigParser()
    parser.read(cfg_path, encoding="utf-8")

    if "postgres" not in parser:
        raise ValueError("В config.ini отсутствует секция [postgres]")

    section = parser["postgres"]
    try:
        host = section.get("host")
        port = section.getint("port")
        dbname = section.get("dbname")
        user = section.get("user")
        password = section.get("password")
        connect_timeout = section.getint("connect_timeout", fallback=3)
    except Exception as e:
        raise ValueError(f"Неверный формат config.ini: {e}") from e

    if not all([host, port, dbname, user]):
        raise ValueError("Заполните host, port, dbname и user в секции [postgres]")

    return PostgresConfig(host=host, port=port, dbname=dbname, user=user, password=password or "", connect_timeout=connect_timeout)
