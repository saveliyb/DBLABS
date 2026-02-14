from typing import Sequence, Any
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class TableModel(QAbstractTableModel):
    def __init__(self, headers: Sequence[str] | None = None, rows: Sequence[Sequence[Any]] | None = None):
        super().__init__()
        self._headers = list(headers) if headers else []
        self._rows = list(rows) if rows else []

    def set_data(self, headers: Sequence[str], rows: Sequence[Sequence[Any]]):
        self.beginResetModel()
        self._headers = list(headers)
        self._rows = [list(r) for r in rows]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            try:
                value = self._rows[index.row()][index.column()]
            except Exception:
                return ""
            if value is None:
                return ""
            return str(value)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return self._headers[section]
            except Exception:
                return None
        else:
            return str(section + 1)

    def row_values(self, row: int) -> list[Any] | None:
        """Return a copy of the values for given row index, or None if OOB."""
        try:
            return list(self._rows[row])
        except Exception:
            return None

    def value_at(self, row: int, col: int) -> Any | None:
        try:
            return self._rows[row][col]
        except Exception:
            return None
