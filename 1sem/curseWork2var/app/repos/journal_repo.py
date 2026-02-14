from typing import List, Tuple, Optional, Dict
from datetime import date

from psycopg.sql import SQL, Identifier

from ..config import PostgresConfig
from ..db import get_connection


def detect_journal_table(cfg: PostgresConfig) -> str:
    candidates = ['journal', 'loans', 'issues']
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            for t in candidates:
                cur.execute("SELECT to_regclass(%s)", ('public.' + t,))
                row = cur.fetchone()
                if row and row[0]:
                    return t
            # fallback: create public.journal
            cur.execute(
                "SELECT to_regclass('public.journal')"
            )
            if not cur.fetchone()[0]:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.journal (
                        id serial PRIMARY KEY,
                        client_id integer,
                        book_id integer,
                        issued_at date NOT NULL DEFAULT CURRENT_DATE,
                        due_at date,
                        returned_at date,
                        fine_amount numeric
                    )
                    """
                )
                conn.commit()
            return 'journal'
    finally:
        conn.close()


def get_columns(cfg: PostgresConfig, table_name: str) -> List[Dict]:
    sql = SQL("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name=%s
    ORDER BY ordinal_position
    """)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            rows = cur.fetchall()
            return [{"column_name": r[0], "data_type": r[1], "is_nullable": r[2]} for r in rows]
    finally:
        conn.close()


def get_journal_colmap(cfg: PostgresConfig, table_name: str) -> Dict[str, Optional[str]]:
    """
    Return mapping of standard logical journal columns to real column names in the table.

    Example return:
      {
        'pk': 'id',
        'client_id': 'client_id',
        'book_id': 'book_id',
        'issued_at': 'issued_at' or 'date_beg',
        'due_at': 'due_at' or 'date_end',
        'returned_at': 'returned_at' or 'date_ret' or None,
        'fine_amount': 'fine_amount' or None,
      }
    """
    cols = get_columns(cfg, table_name)
    colnames = [c['column_name'] for c in cols]
    lcs = [c.lower() for c in colnames]

    def find(cands):
        for cand in cands:
            if cand in lcs:
                return colnames[lcs.index(cand)]
        return None

    pk = get_pk(cfg, table_name)

    client_col = find(['client_id', 'id_client', 'client', 'reader_id'])
    book_col = find(['book_id', 'id_book', 'book'])
    issued_col = find(['issued_at', 'date_beg', 'date_begin', 'issue_date'])
    due_col = find(['due_at', 'date_end', 'due_date', 'return_due'])
    returned_col = find(['returned_at', 'date_ret', 'return_date', 'returned_date'])
    fine_col = find(['fine_amount', 'fine', 'penalty', 'sum_fine'])

    # critical columns for basic operations
    missing = []
    if not client_col:
        missing.append('client_id')
    if not book_col:
        missing.append('book_id')
    if not issued_col:
        missing.append('issued_at')
    if not due_col:
        missing.append('due_at')
    if missing:
        raise ValueError(f"Journal table '{table_name}' missing required columns: {', '.join(missing)}. Found: {', '.join(colnames)}")

    return {
        'pk': pk,
        'client_id': client_col,
        'book_id': book_col,
        'issued_at': issued_col,
        'due_at': due_col,
        'returned_at': returned_col,
        'fine_amount': fine_col,
    }


def get_pk(cfg: PostgresConfig, table_name: str) -> Optional[str]:
    sql = SQL("""
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public' AND tc.table_name = %s
    ORDER BY kcu.ordinal_position
    LIMIT 1
    """)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def get_fk_map(cfg: PostgresConfig, table_name: str) -> Dict[str, Dict]:
    # returns mapping column_name -> {'referenced_table': tbl, 'referenced_column': col}
    sql = SQL("""
    SELECT kcu.column_name, ccu.table_name, ccu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.constraint_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public' AND tc.table_name = %s
    """)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            rows = cur.fetchall()
            result = {}
            for r in rows:
                result[r[0]] = {"referenced_table": r[1], "referenced_column": r[2]}
            return result
    finally:
        conn.close()


def list_rows_joined(cfg: PostgresConfig, table_name: str) -> Tuple[List[str], List[Tuple]]:
    # Determine fk columns to clients and books
    fk_map = get_fk_map(cfg, table_name)
    client_fk = None
    book_fk = None
    for col, meta in fk_map.items():
        if meta['referenced_table'] == 'clients':
            client_fk = {'col': col, 'ref_col': meta['referenced_column']}
        if meta['referenced_table'] == 'books':
            book_fk = {'col': col, 'ref_col': meta['referenced_column']}

    # detect book_types fk through books
    # we'll build join dynamically
    pk = get_pk(cfg, table_name)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            # get columns for journal table
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table_name,))
            journal_cols = [r[0] for r in cur.fetchall()]

            select_parts = [SQL("j.*")]
            joins = []

            if client_fk:
                # pick client display column
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' ORDER BY ordinal_position")
                client_cols = [r[0] for r in cur.fetchall()]
                disp = None
                for cand in ('name', 'fio', 'full_name', 'email', 'phone'):
                    if cand in client_cols:
                        disp = cand
                        break
                if not disp and client_cols:
                    disp = client_cols[0]
                # alias as identifier c_<col>
                select_parts.append(SQL("c.{col} AS {alias}").format(col=Identifier(disp), alias=Identifier("c_" + disp)))
                joins.append(SQL("LEFT JOIN public.clients c ON j.{fk} = c.{ref}").format(fk=Identifier(client_fk['col']), ref=Identifier(client_fk['ref_col'])))

            if book_fk:
                # join books
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='books' ORDER BY ordinal_position")
                book_cols = [r[0] for r in cur.fetchall()]
                b_title = None
                for cand in ('title', 'name'):
                    if cand in book_cols:
                        b_title = cand
                        break
                if not b_title and book_cols:
                    b_title = book_cols[0]
                select_parts.append(SQL("b.{col} AS {alias}").format(col=Identifier(b_title), alias=Identifier("b_" + b_title)))
                # detect book_types fk on books
                cur.execute("SELECT kcu.column_name, ccu.table_name, ccu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.constraint_schema WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public' AND tc.table_name = 'books'")
                b_fk_rows = cur.fetchall()
                bt_fk_col = None
                bt_ref_col = None
                for r in b_fk_rows:
                    if r[1] == 'book_types':
                        bt_fk_col = r[0]
                        bt_ref_col = r[2]
                        break
                if bt_fk_col:
                    # fetch book_types cols
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='book_types' ORDER BY ordinal_position")
                    bt_cols = [r[0] for r in cur.fetchall()]
                    for c in bt_cols:
                        select_parts.append(SQL("bt.{col} AS {alias}").format(col=Identifier(c), alias=Identifier("bt_" + c)))
                    joins.append(SQL("LEFT JOIN public.books b ON j.{bk_fk} = b.{bk_ref}").format(bk_fk=Identifier(book_fk['col']), bk_ref=Identifier(book_fk['ref_col'])))
                    joins.append(SQL("LEFT JOIN public.book_types bt ON b.{bt_fk} = bt.{bt_ref}").format(bt_fk=Identifier(bt_fk_col), bt_ref=Identifier(bt_ref_col)))
                else:
                    # no book_types
                    joins.append(SQL("LEFT JOIN public.books b ON j.{bk_fk} = b.{bk_ref}").format(bk_fk=Identifier(book_fk['col']), bk_ref=Identifier(book_fk['ref_col'])))

            # Build final SQL
            select_sql = SQL(', ').join(select_parts)
            join_sql = SQL(' ').join(joins) if joins else SQL('')
            if pk:
                sql = SQL("SELECT {sel} FROM public.{tbl} j {joins} ORDER BY j.{pk} DESC").format(sel=select_sql, tbl=Identifier(table_name), joins=join_sql, pk=Identifier(pk))
            else:
                sql = SQL("SELECT {sel} FROM public.{tbl} j {joins}").format(sel=select_sql, tbl=Identifier(table_name), joins=join_sql)

            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            return cols, rows
    finally:
        conn.close()


def count_active_loans_for_client(cfg: PostgresConfig, table: str, client_id: int) -> int:
    # use dynamic column names; if returned_at not present, skip active-loans limit (return 0)
    colmap = get_journal_colmap(cfg, table)
    client_col = colmap.get('client_id')
    returned_col = colmap.get('returned_at')
    if not returned_col:
        # no returned indicator — don't block issuance
        return 0
    sql = SQL("SELECT COUNT(*) FROM public.{tbl} WHERE {client} = %s AND {ret} IS NULL").format(
        tbl=Identifier(table), client=Identifier(client_col), ret=Identifier(returned_col)
    )
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (client_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def is_book_available(cfg: PostgresConfig, table: str, book_id: int) -> bool:
    colmap = get_journal_colmap(cfg, table)
    book_col = colmap.get('book_id')
    returned_col = colmap.get('returned_at')
    # if returned column missing, treat book as available (avoid accidental blocking)
    if not returned_col:
        return True
    sql = SQL("SELECT 1 FROM public.{tbl} WHERE {book} = %s AND {ret} IS NULL LIMIT 1").format(
        tbl=Identifier(table), book=Identifier(book_col), ret=Identifier(returned_col)
    )
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (book_id,))
            return cur.fetchone() is None
    finally:
        conn.close()


def issue_book(cfg: PostgresConfig, table: str, client_id: int, book_id: int, issued_at: date, due_at: Optional[date]) -> None:
    colmap = get_journal_colmap(cfg, table)
    client_col = colmap.get('client_id')
    book_col = colmap.get('book_id')
    issued_col = colmap.get('issued_at')
    due_col = colmap.get('due_at')
    # build column list depending on whether due_at is provided
    if due_at is None:
        cols = [client_col, book_col, issued_col]
        sql = SQL("INSERT INTO public.{tbl} ({cols}) VALUES (%s, %s, %s)").format(
            tbl=Identifier(table), cols=SQL(', ').join([Identifier(c) for c in cols])
        )
        params = (client_id, book_id, issued_at)
    else:
        cols = [client_col, book_col, issued_col, due_col]
        sql = SQL("INSERT INTO public.{tbl} ({cols}) VALUES (%s, %s, %s, %s)").format(
            tbl=Identifier(table), cols=SQL(', ').join([Identifier(c) for c in cols])
        )
        params = (client_id, book_id, issued_at, due_at)

    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def return_book(cfg: PostgresConfig, table: str, pk_col: str, journal_id: int, returned_at: date, fine_amount: Optional[float]) -> None:
    colmap = get_journal_colmap(cfg, table)
    returned_col = colmap.get('returned_at')
    fine_col = colmap.get('fine_amount')
    if not returned_col:
        raise ValueError(f"Table '{table}' has no return/returned column; cannot accept returns")

    if fine_amount is not None and fine_col:
        sql = SQL("UPDATE public.{tbl} SET {ret} = %s, {fine} = %s WHERE {pk} = %s").format(
            tbl=Identifier(table), ret=Identifier(returned_col), fine=Identifier(fine_col), pk=Identifier(pk_col)
        )
        params = (returned_at, fine_amount, journal_id)
    else:
        sql = SQL("UPDATE public.{tbl} SET {ret} = %s WHERE {pk} = %s").format(
            tbl=Identifier(table), ret=Identifier(returned_col), pk=Identifier(pk_col)
        )
        params = (returned_at, journal_id)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def delete_row(cfg: PostgresConfig, table: str, pk_col: str, pk_value) -> None:
    sql = SQL("DELETE FROM public.{tbl} WHERE {pk} = %s").format(tbl=Identifier(table), pk=Identifier(pk_col))
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (pk_value,))
        conn.commit()
    finally:
        conn.close()
