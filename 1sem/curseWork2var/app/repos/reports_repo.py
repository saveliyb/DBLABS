from typing import List, Tuple, Optional
from datetime import date

from psycopg.sql import SQL, Identifier

from ..config import PostgresConfig
from ..db import get_connection
from . import journal_repo


def _pick_display_column(cur, table_name: str, candidates: Tuple[str, ...]) -> Optional[str]:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table_name,))
    cols = [r[0] for r in cur.fetchall()]
    for c in candidates:
        if c in cols:
            return c
    return cols[0] if cols else None


def report_active_loans(cfg: PostgresConfig, date_from: Optional[date] = None, date_to: Optional[date] = None) -> Tuple[List[str], List[Tuple]]:
    tbl = journal_repo.detect_journal_table(cfg)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            # choose client display and book title columns
            client_disp = _pick_display_column(cur, 'clients', ('name', 'fio', 'full_name', 'email', 'phone'))
            book_title = _pick_display_column(cur, 'books', ('title', 'name'))

            # inspect journal columns for robustness
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (tbl,))
            journal_cols = [r[0] for r in cur.fetchall()]
            has_issued = 'issued_at' in journal_cols
            has_due = 'due_at' in journal_cols
            has_returned = 'returned_at' in journal_cols

            select_parts = []
            select_parts.append(SQL('c.{cdisp} AS client_display').format(cdisp=Identifier(client_disp)) if client_disp else SQL("NULL AS client_display"))
            select_parts.append(SQL('b.{btitle} AS book_title').format(btitle=Identifier(book_title)) if book_title else SQL("NULL AS book_title"))
            select_parts.append(SQL('j.issued_at') if has_issued else SQL('NULL AS issued_at'))
            select_parts.append(SQL('j.due_at') if has_due else SQL('NULL AS due_at'))
            select_parts.append(SQL("CASE WHEN j.due_at IS NOT NULL AND CURRENT_DATE > j.due_at THEN (CURRENT_DATE - j.due_at) ELSE 0 END AS days_overdue") if has_due else SQL('0 AS days_overdue'))

            select_sql = SQL(', ').join(select_parts)

            joins = [SQL('LEFT JOIN public.clients c ON j.client_id = c.id'), SQL('LEFT JOIN public.books b ON j.book_id = b.id')]

            where_parts = []
            params = []
            if has_returned:
                where_parts.append(SQL('j.returned_at IS NULL'))
            # date filters apply to issued_at when available
            if date_from is not None and has_issued:
                where_parts.append(SQL('j.issued_at >= %s'))
                params.append(date_from)
            if date_to is not None and has_issued:
                where_parts.append(SQL('j.issued_at <= %s'))
                params.append(date_to)

            joins_sql = SQL(' ').join(joins)
            # choose safe order column only if present in journal_cols
            order_col = None
            if has_issued:
                order_col = 'issued_at'
            elif 'book_id' in journal_cols:
                order_col = 'book_id'
            elif 'client_id' in journal_cols:
                order_col = 'client_id'

            if where_parts:
                where_sql = SQL(' AND ').join(where_parts)
                if order_col:
                    sql = SQL('SELECT {sel} FROM public.{tbl} j {joins} WHERE {where} ORDER BY j.{col} DESC').format(sel=select_sql, tbl=Identifier(tbl), joins=joins_sql, where=where_sql, col=Identifier(order_col))
                else:
                    sql = SQL('SELECT {sel} FROM public.{tbl} j {joins} WHERE {where}').format(sel=select_sql, tbl=Identifier(tbl), joins=joins_sql, where=where_sql)
            else:
                if order_col:
                    sql = SQL('SELECT {sel} FROM public.{tbl} j {joins} ORDER BY j.{col} DESC').format(sel=select_sql, tbl=Identifier(tbl), joins=joins_sql, col=Identifier(order_col))
                else:
                    sql = SQL('SELECT {sel} FROM public.{tbl} j {joins}').format(sel=select_sql, tbl=Identifier(tbl), joins=joins_sql)

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            return cols, rows
    finally:
        conn.close()


def report_fines(cfg: PostgresConfig, date_from: Optional[date] = None, date_to: Optional[date] = None) -> Tuple[List[str], List[Tuple]]:
    tbl = journal_repo.detect_journal_table(cfg)
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            client_disp = _pick_display_column(cur, 'clients', ('name', 'fio', 'full_name', 'email', 'phone'))
            book_title = _pick_display_column(cur, 'books', ('title', 'name'))

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

            # inspect journal columns
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (tbl,))
            journal_cols = [r[0] for r in cur.fetchall()]
            has_returned = 'returned_at' in journal_cols
            has_due = 'due_at' in journal_cols
            has_fine = 'fine_amount' in journal_cols

            # if neither returned_at nor fine_amount exist, nothing to show
            if not has_returned and not has_fine:
                return ['client_display', 'book_title', 'returned_at', 'due_at', 'days_overdue', 'fine_amount'], []

            select_parts = []
            select_parts.append(SQL('c.{cdisp} AS client_display').format(cdisp=Identifier(client_disp)) if client_disp else SQL("NULL AS client_display"))
            select_parts.append(SQL('b.{btitle} AS book_title').format(btitle=Identifier(book_title)) if book_title else SQL("NULL AS book_title"))
            select_parts.append(SQL('j.returned_at') if has_returned else SQL('NULL AS returned_at'))
            select_parts.append(SQL('j.due_at') if has_due else SQL('NULL AS due_at'))
            select_parts.append(SQL("CASE WHEN j.returned_at IS NOT NULL AND j.due_at IS NOT NULL AND j.returned_at > j.due_at THEN (j.returned_at - j.due_at) ELSE 0 END AS days_overdue"))
            if has_fine:
                select_parts.append(SQL('j.fine_amount AS journal_fine'))
            else:
                select_parts.append(SQL('NULL AS journal_fine'))

            joins = [SQL('LEFT JOIN public.clients c ON j.client_id = c.id'), SQL('LEFT JOIN public.books b ON j.book_id = b.id')]
            bt_cols = []
            if bt_fk_col and bt_ref_col:
                # include all book_types columns aliased as bt_<col>
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='book_types' ORDER BY ordinal_position")
                bt_cols = [r[0] for r in cur.fetchall()]
                for c in bt_cols:
                    select_parts.append(SQL('bt.{col} AS {alias}').format(col=Identifier(c), alias=Identifier('bt_' + c)))
                joins.append(SQL('LEFT JOIN public.book_types bt ON b.{bk_fk} = bt.{bk_ref}').format(bk_fk=Identifier(bt_fk_col), bk_ref=Identifier(bt_ref_col)))

            # base OR condition: (fine_amount > 0) OR (returned_at > due_at)
            base_conds = []
            if has_fine:
                base_conds.append(SQL('j.fine_amount IS NOT NULL AND j.fine_amount > 0'))
            if has_returned and has_due:
                base_conds.append(SQL('j.returned_at IS NOT NULL AND j.due_at IS NOT NULL AND j.returned_at > j.due_at'))

            # if no base conditions, nothing to show
            if not base_conds:
                return ['client_display', 'book_title', 'returned_at', 'due_at', 'days_overdue', 'fine_amount'], []

            base_or_sql = SQL('({base})').format(base=SQL(' OR ').join(base_conds)) if len(base_conds) > 1 else base_conds[0]

            # date filters (ANDed) apply only when returned_at exists
            date_parts = []
            params = []
            if has_returned:
                if date_from is not None:
                    date_parts.append(SQL('j.returned_at >= %s'))
                    params.append(date_from)
                if date_to is not None:
                    date_parts.append(SQL('j.returned_at <= %s'))
                    params.append(date_to)

            if date_parts:
                date_and_sql = SQL(' AND ').join(date_parts)
                where_sql = SQL('{base} AND ({date})').format(base=base_or_sql, date=date_and_sql)
            else:
                where_sql = base_or_sql

            sel = SQL(', ').join(select_parts)
            joins_sql = SQL(' ').join(joins)
            order_clause = SQL('ORDER BY j.returned_at DESC') if has_returned else SQL('')
            sql = SQL('SELECT {sel} FROM public.{tbl} j {joins} WHERE {where} {order}').format(sel=sel, tbl=Identifier(tbl), joins=joins_sql, where=where_sql, order=order_clause)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            # post-process to compute effective fine if journal_fine is NULL
            result_rows = []
            # find candidate bt fine column name
            bt_fine_col = None
            if bt_cols:
                for c in bt_cols:
                    if c in ('fine', 'bt_fine', 'fine_amount', 'penalty', 'rate'):
                        bt_fine_col = 'bt_' + c
                        break

            for r in rows:
                row = {cols[i]: r[i] for i in range(len(cols))}
                due = row.get('due_at')
                returned = row.get('returned_at')
                days_over = 0
                if returned and due and returned > due:
                    days_over = (returned - due).days
                journal_fine = row.get('journal_fine')
                fine = journal_fine if journal_fine is not None else None
                if fine is None:
                    # try compute using bt fine rate
                    if bt_fine_col and row.get(bt_fine_col) is not None and days_over > 0:
                        try:
                            rate = float(row.get(bt_fine_col))
                            fine = rate * days_over
                        except Exception:
                            fine = 0
                    else:
                        fine = 0
                result_rows.append((row.get('client_display'), row.get('book_title'), returned, due, days_over, fine))

            out_cols = ['client_display', 'book_title', 'returned_at', 'due_at', 'days_overdue', 'fine_amount']
            return out_cols, result_rows
    finally:
        conn.close()
