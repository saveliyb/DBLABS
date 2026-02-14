from datetime import date, datetime
from typing import Optional
from PySide6.QtCore import QDate


def _to_qdate(d) -> Optional[QDate]:
    """Convert a date/datetime or QDate to QDate, or return None if not convertible."""
    if d is None:
        return None
    if isinstance(d, QDate):
        return d
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return QDate(d.year, d.month, d.day)
    return None
