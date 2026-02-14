from typing import List, Tuple, Optional, Dict

from psycopg.sql import SQL, Identifier

from ..config import PostgresConfig
from ..db import get_connection


def get_columns(cfg: PostgresConfig) -> List[Dict]:
    sql = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clients'
    ORDER BY ordinal_position
    """
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {"column_name": r[0], "data_type": r[1], "is_nullable": r[2]}
                for r in rows
            ]
    finally:
        conn.close()


def get_pk(cfg: PostgresConfig) -> Optional[str]:
    sql = """
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public' AND tc.table_name = 'clients'
    ORDER BY kcu.ordinal_position
    LIMIT 1
    """
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def list_rows(cfg: PostgresConfig) -> Tuple[List[str], List[Tuple]]:
    pk = get_pk(cfg)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            if pk:
                sql = SQL("SELECT * FROM public.clients ORDER BY {} DESC").format(Identifier(pk))
            else:
                sql = SQL("SELECT * FROM public.clients")
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            return cols, rows
    finally:
        conn.close()


def insert_row(cfg: PostgresConfig, data: Dict, pk_col: Optional[str]) -> None:
    # insert only keys with non-None values and excluding pk
    cols = [k for k, v in data.items() if v is not None and k != pk_col]
    if not cols:
        raise ValueError("Нет значимых полей для вставки")
    vals = [data[c] for c in cols]
    # build SQL safely with identifiers
    cols_ident = SQL(', ').join(Identifier(c) for c in cols)
    placeholders = SQL(', ').join(SQL('%s') for _ in cols)
    sql = SQL("INSERT INTO public.clients ({}) VALUES ({})").format(cols_ident, placeholders)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals))
        conn.commit()
    finally:
        conn.close()


def update_row(cfg: PostgresConfig, pk_col: str, pk_value, data: Dict) -> None:
    cols = [k for k, v in data.items() if k != pk_col]
    if not cols:
        return
    set_clause = SQL(', ').join(SQL("{} = %s").format(Identifier(c)) for c in cols)
    vals = [data[c] for c in cols]
    sql = SQL("UPDATE public.clients SET {} WHERE {} = %s").format(set_clause, Identifier(pk_col))
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals) + (pk_value,))
        conn.commit()
    finally:
        conn.close()


def delete_row(cfg: PostgresConfig, pk_col: str, pk_value) -> None:
    sql = SQL("DELETE FROM public.clients WHERE {} = %s").format(Identifier(pk_col))
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (pk_value,))
        conn.commit()
    finally:
        conn.close()
