from typing import List, Dict

from ..config import PostgresConfig
from ..db import get_connection


def list_types(cfg: PostgresConfig) -> List[Dict]:
    sql = "SELECT * FROM public.book_types ORDER BY 1"
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            result = []
            for r in rows:
                item = {cols[i]: r[i] for i in range(len(cols))}
                result.append(item)
            return result
    finally:
        conn.close()
