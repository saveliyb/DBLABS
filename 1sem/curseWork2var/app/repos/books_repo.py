from typing import List, Tuple, Optional, Dict

from psycopg.sql import SQL, Identifier

from ..config import PostgresConfig
from ..db import get_connection


def get_columns(cfg: PostgresConfig) -> List[Dict]:
    sql = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='books'
    ORDER BY ordinal_position
    """
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [{"column_name": r[0], "data_type": r[1], "is_nullable": r[2]} for r in rows]
    finally:
        conn.close()


def list_rows(cfg: PostgresConfig) -> Tuple[List[str], List[Tuple]]:
    """Simple select all rows from books, returning columns and rows.

    Similar shape to clients_repo.list_rows.
    """
    pk = get_pk(cfg)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            if pk:
                sql = SQL("SELECT * FROM public.books ORDER BY {pk} DESC").format(pk=Identifier(pk))
            else:
                sql = SQL("SELECT * FROM public.books")
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            return cols, rows
    finally:
        conn.close()


def get_pk(cfg: PostgresConfig) -> Optional[str]:
    sql = """
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public' AND tc.table_name = 'books'
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


def get_fk_to_table(cfg: PostgresConfig, referenced_table: str = 'book_types') -> Optional[Dict]:
    sql = """
    SELECT kcu.column_name, ccu.column_name as foreign_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.constraint_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public' AND tc.table_name = 'books'
      AND ccu.table_name = %s
    LIMIT 1
    """
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (referenced_table,))
            row = cur.fetchone()
            if not row:
                return None
            return {"column_name": row[0], "foreign_column": row[1]}
    finally:
        conn.close()


def list_rows_joined(cfg: PostgresConfig) -> Tuple[List[str], List[Tuple]]:
    # detect pk and fk
    pk = get_pk(cfg)
    fk = get_fk_to_table(cfg, 'book_types')

    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            if fk:
                fk_col = fk['column_name']
                # fetch book_types columns
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='book_types' ORDER BY ordinal_position")
                bt_cols = [r[0] for r in cur.fetchall()]

                # build select list: books.*, then bt.col AS bt_col
                books_cols_sql = SQL('b.*')
                bt_cols_sql = SQL(', ').join(SQL("bt.{c} AS {alias}").format(c=Identifier(c), alias=Identifier("bt_" + c)) for c in bt_cols)
                if pk:
                    sql = SQL("SELECT {books}, {bt} FROM public.books b LEFT JOIN public.book_types bt ON b.{fk} = bt.{fkref} ORDER BY b.{pk} DESC").format(
                        books=books_cols_sql,
                        bt=bt_cols_sql,
                        fk=Identifier(fk_col),
                        fkref=Identifier(fk['foreign_column']),
                        pk=Identifier(pk),
                    )
                else:
                    sql = SQL("SELECT {books}, {bt} FROM public.books b LEFT JOIN public.book_types bt ON b.{fk} = bt.{fkref}").format(
                        books=books_cols_sql,
                        bt=bt_cols_sql,
                        fk=Identifier(fk_col),
                        fkref=Identifier(fk['foreign_column']),
                    )
                cur.execute(sql)
                rows = cur.fetchall()
                cols = [d.name for d in cur.description]
                return cols, rows
            else:
                # no fk: simple select all from books
                if pk:
                    sql = SQL("SELECT * FROM public.books ORDER BY {pk} DESC").format(pk=Identifier(pk))
                else:
                    sql = SQL("SELECT * FROM public.books")
                cur.execute(sql)
                rows = cur.fetchall()
                cols = [d.name for d in cur.description]
                return cols, rows
    finally:
        conn.close()


def insert_row(cfg: PostgresConfig, data: Dict, pk_col: Optional[str]) -> None:
    cols = [k for k, v in data.items() if v is not None and k != pk_col]
    if not cols:
        raise ValueError("Нет значимых полей для вставки")
    vals = [data[c] for c in cols]
    cols_ident = SQL(', ').join(Identifier(c) for c in cols)
    placeholders = SQL(', ').join(SQL('%s') for _ in cols)
    sql = SQL("INSERT INTO public.books ({}) VALUES ({})").format(cols_ident, placeholders)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals))
        conn.commit()
    finally:
        conn.close()


def update_row(cfg: PostgresConfig, pk_col: str, pk_value, data: Dict) -> None:
    cols = [k for k, v in data.items() if k != pk_col and v is not None]
    if not cols:
        return
    set_clause = SQL(', ').join(SQL("{} = %s").format(Identifier(c)) for c in cols)
    vals = [data[c] for c in cols]
    sql = SQL("UPDATE public.books SET {} WHERE {} = %s").format(set_clause, Identifier(pk_col))
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals) + (pk_value,))
        conn.commit()
    finally:
        conn.close()


def delete_row(cfg: PostgresConfig, pk_col: str, pk_value) -> None:
    sql = SQL("DELETE FROM public.books WHERE {} = %s").format(Identifier(pk_col))
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (pk_value,))
        conn.commit()
    finally:
        conn.close()
