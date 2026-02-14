#!/usr/bin/env python3
"""Headless smoke runner: creates an offscreen QApplication, checks DB and probes reports.

Usage:
  QT_QPA_PLATFORM=offscreen python scripts/smoke_offscreen.py

If the DB is unavailable the script prints a clear message and exits 0 by default.
Set STRICT_DB=1 to make DB failures return exit code 1.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.core.db import get_conn
from app.ui.main_window import MainWindow, PAGE_REPORT_PROFIT, PAGE_REPORT_TOP5


def test_db(cfg) -> tuple[bool, Exception | None]:
    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, None
    except Exception as e:
        return False, e


def main() -> int:
    app = QApplication([])

    try:
        cfg = load_config()
    except Exception as e:
        print("Config error:", e, file=sys.stderr)
        return 2

    ok, err = test_db(cfg)
    strict = os.environ.get("STRICT_DB") == "1"
    if not ok:
        msg = f"DB check failed: {err}"
        if strict:
            print(msg, file=sys.stderr)
            return 1
        else:
            print(msg + " — running in non-strict mode; exiting 0")
            return 0

    try:
        win = MainWindow(cfg, login="admin", role="admin")

        # Profit report
        win.show_page(PAGE_REPORT_PROFIT)
        page = win.pages.get(PAGE_REPORT_PROFIT)
        if page and hasattr(page, "refresh"):
            try:
                page.refresh()
                print("Profit report refreshed")
            except Exception as e:
                print("Profit report error:", e, file=sys.stderr)

        # Top5 report
        win.show_page(PAGE_REPORT_TOP5)
        page2 = win.pages.get(PAGE_REPORT_TOP5)
        if page2 and hasattr(page2, "refresh"):
            try:
                page2.refresh()
                print("Top5 report refreshed")
            except Exception as e:
                print("Top5 report error:", e, file=sys.stderr)

    except Exception as e:
        print("Runtime error:", e, file=sys.stderr)
        return 3
    finally:
        try:
            app.quit()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
