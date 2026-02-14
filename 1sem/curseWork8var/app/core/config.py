import os
import configparser
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _require(s: configparser.SectionProxy, key: str) -> str:
    val = s.get(key)
    if not val:
        raise KeyError(f"Missing required key '{key}' in [postgresql]")
    return val


def load_config(path: str | None = None) -> Config:
    """
    Load config from `path` or from APP_CONFIG env or ./config.ini.

    Expects an INI file with a [postgresql] section containing:
    host, port, dbname, user, password.
    """
    path = path or os.environ.get("APP_CONFIG", "./config.ini")
    parser = configparser.ConfigParser()
    read = parser.read(path)
    if not read:
        raise FileNotFoundError(f"Config file not found: {path}")
    if "postgresql" not in parser:
        raise KeyError("Missing [postgresql] section in config")

    s = parser["postgresql"]
    host = _require(s, "host")
    port_str = _require(s, "port")
    dbname = _require(s, "dbname")
    user = _require(s, "user")
    password = _require(s, "password")

    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"Invalid port value: {port_str!r}") from e

    return Config(host=host, port=port, dbname=dbname, user=user, password=password)
