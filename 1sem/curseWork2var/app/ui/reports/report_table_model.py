from typing import List, Tuple

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class ReportTableModel(QAbstractTableModel):
    def __init__(self, columns: List[str], rows: List[tuple]):
        super().__init__()
        self._columns = columns
        self._rows = rows

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._rows[index.row()][index.column()]
            return "" if val is None else str(val)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section]
        return section + 1


def _truncate(s: str, max_len: int) -> str:
    if s is None:
        return ""
    s = str(s)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'


def format_table_txt(columns: List[str], rows: List[Tuple], max_col_width: int = 30) -> str:
    # compute column widths up to max_col_width
    widths = [min(max(len(str(h)), 0), max_col_width) for h in columns]
    for r in rows:
        for i, v in enumerate(r):
            ln = len(str(v)) if v is not None else 0
            widths[i] = min(max(widths[i], min(ln, max_col_width)), max_col_width)

    parts = []
    # header
    header = ' | '.join(columns[i].ljust(widths[i]) for i in range(len(columns)))
    parts.append(header)
    parts.append('-' * len(header))
    for r in rows:
        line = ' | '.join(_truncate(r[i], widths[i]).ljust(widths[i]) for i in range(len(columns)))
        parts.append(line)
    return '\n'.join(parts)
