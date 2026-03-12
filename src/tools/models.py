from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtWidgets import QItemDelegate, QComboBox

class ComboBoxDelegate(QItemDelegate):
    def __init__(self, items, parent=None):
        super(ComboBoxDelegate, self).__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.items)
        return combo

    def setEditorData(self, editor, index):
        value = index.data()
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

class countingLinesTableModel(QAbstractTableModel):
    def __init__(self, counting_lines = None):
        super(countingLinesTableModel, self).__init__()
        self.lines = counting_lines or []
        self.headers = ['ID', 'Acceso', 'Nombre']

    def rowCount(self, parent=None):
        return len(self.lines)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid():
            return None
        line = self.lines[index.row()]
        column = index.column()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if column == 0:
                return line.id
            elif column == 1:
                return line.access
            elif column == 2:
                return line.name
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            line = self.lines[index.row()]
            if index.column() == 0:
                line.id = value
            elif index.column() == 1:
                line.access = value
            elif index.column() == 2:
                line.name = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return None

class movementsTableModel(QAbstractTableModel):
    def __init__(self, movements = None):
        super(movementsTableModel, self).__init__()
        self.movements = movements or []
        self.headers = ['ID', 'Origen', 'Destino', 'Modo']

    def rowCount(self, parent=None):
        return len(self.movements)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid():
            return None
        movement = self.movements[index.row()]
        column = index.column()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if column == 0:
                return movement['id']
            elif column == 1:
                return movement['o']
            elif column == 2:
                return movement['d']
            elif column == 3:
                return movement.get('mode', 'Vehicular')
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            movement = self.movements[index.row()]
            if index.column() == 0:
                movement['id'] = value
            elif index.column() == 1:
                movement['o'] = value
            elif index.column() == 2:
                movement['d'] = value
            elif index.column() == 3:
                movement['mode'] = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return None