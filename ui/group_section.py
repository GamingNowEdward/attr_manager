"""Collapsible group section with cross-group drop support."""

from __future__ import annotations

import json

try:
    from PySide6.QtCore import Qt, Signal, QMimeData, QTimer
    from PySide6.QtGui import QPainter, QPen, QColor, QDrag
    from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                                   QPushButton, QVBoxLayout, QWidget)
except ImportError:
    from PySide2.QtCore import Qt, Signal, QMimeData, QTimer
    from PySide2.QtGui import QPainter, QPen, QColor, QDrag
    from PySide2.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                                   QPushButton, QVBoxLayout, QWidget)

from core.attr_data import AttrGroup
from ui.attr_row_widget import AttrRowWidget, MIME_TYPE

GROUP_MIME_TYPE = "application/x-attribute-manager-group"


class GroupDragHandle(QLabel):
    def __init__(self, section):
        super().__init__()
        self.section = section
        self._start = None
        self.setObjectName("groupArrow")
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Click to collapse, drag to reorder group")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.position().toPoint() if hasattr(event, "position") else event.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._start is None:
            return
        current = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if (current - self._start).manhattanLength() < 8:
            return
        self._start = None
        index = self.section.group_index()
        if index < 0:
            return
        mime = QMimeData()
        mime.setData(GROUP_MIME_TYPE, json.dumps({"group_index": index}).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction) if hasattr(drag, "exec") else drag.exec_(Qt.MoveAction)

    def mouseReleaseEvent(self, event):
        if self._start is not None and event.button() == Qt.LeftButton:
            self._start = None
            self.section._toggle()

    def setText(self, text):
        super().setText(text)


class EntryContainer(QWidget):
    def __init__(self, section):
        super().__init__(section)
        self.section = section
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)
        self._indicator_y = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(MIME_TYPE):
            event.ignore()
            return
        event.acceptProposedAction()
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        self._indicator_y = self._calc_indicator_y(point.y())
        self.update()

    def dragLeaveEvent(self, event):
        self._indicator_y = None
        self.update()

    def dropEvent(self, event):
        self._indicator_y = None
        self.update()
        try:
            data = json.loads(bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8"))
        except (TypeError, ValueError):
            event.ignore()
            return
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target = self._calc_drop_index(point.y())
        self.section.request_move(data["group_index"], data["entry_index"], target)
        event.acceptProposedAction()

    def _calc_drop_index(self, y):
        for index in range(self._layout.count()):
            child = self._layout.itemAt(index).widget()
            if child and y < child.geometry().center().y():
                return index
        return self._layout.count()

    def _calc_indicator_y(self, y):
        for index in range(self._layout.count()):
            child = self._layout.itemAt(index).widget()
            if not child:
                continue
            geo = child.geometry()
            if y < geo.center().y():
                return geo.top()
        last = self._layout.itemAt(self._layout.count() - 1)
        if last and last.widget():
            return last.widget().geometry().bottom() + 1
        return 0

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._indicator_y is None:
            return
        painter = QPainter(self)
        painter.setPen(QPen(QColor(80, 160, 255), 2))
        painter.drawLine(4, self._indicator_y, self.width() - 4, self._indicator_y)
        painter.end()


class GroupSection(QWidget):
    changed = Signal()
    remove_requested = Signal(object)
    move_requested = Signal(int, int, object, int)

    def __init__(self, group: AttrGroup, parent=None, float_precision=False):
        super().__init__(parent)
        self.group = group
        self.rows = []
        self._float_precision = float_precision
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)
        outer.setSpacing(1)
        header = QHBoxLayout()
        self.arrow = GroupDragHandle(self)
        header.addWidget(self.arrow)
        self.title = QLabel(self.group.name)
        self.title.setObjectName("groupTitle")
        self.title.mouseDoubleClickEvent = self._begin_rename
        header.addWidget(self.title)
        self.edit = QLineEdit(self.group.name)
        self.edit.hide()
        self.edit.editingFinished.connect(self._finish_rename)
        header.addWidget(self.edit)
        header.addStretch()
        remove = QPushButton("×")
        remove.setObjectName("delBtn")
        remove.setFixedSize(20, 20)
        remove.setToolTip("Remove group")
        remove.clicked.connect(lambda: self.remove_requested.emit(self))
        header.addWidget(remove)
        outer.addLayout(header)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        outer.addWidget(line)
        self.container = EntryContainer(self)
        outer.addWidget(self.container)
        self.populate(float_precision=self._float_precision)
        self._apply_collapsed()

    def group_index(self):
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "config"):
                try:
                    return widget.config.groups.index(self.group)
                except ValueError:
                    return -1
            widget = widget.parent()
        return -1

    def row_index(self, row):
        return self.rows.index(row)

    def populate(self, float_precision=False):
        while self.container._layout.count():
            child = self.container._layout.takeAt(0).widget()
            if child:
                child.deleteLater()
        self.rows = []
        for entry in self.group.entries:
            row = AttrRowWidget(entry, self, float_precision=float_precision)
            row.removed.connect(self._remove_entry)
            row.changed.connect(self.changed)
            self.container._layout.addWidget(row)
            self.rows.append(row)

    def _remove_entry(self, row):
        index = self.rows.index(row)
        self.group.entries.pop(index)
        self.populate()
        self.changed.emit()

    def request_move(self, source_group, source_entry, target_index):
        self.move_requested.emit(source_group, source_entry, self, target_index)

    def _toggle(self):
        self.group.collapsed = not self.group.collapsed
        self._apply_collapsed()
        self.changed.emit()

    def _apply_collapsed(self):
        self.arrow.setText("▾" if not self.group.collapsed else "▸")
        self.container.setVisible(not self.group.collapsed)

    def _begin_rename(self, _event):
        self.title.hide()
        self.edit.show()
        self.edit.setFocus()
        self.edit.selectAll()
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(200)
        self._focus_timer.timeout.connect(self._check_focus)
        self._focus_timer.start()

    def _check_focus(self):
        if not self.edit.hasFocus():
            self._finish_rename()

    def _finish_rename(self):
        if hasattr(self, "_focus_timer"):
            self._focus_timer.stop()
        name = self.edit.text().strip()
        if name and name != self.group.name:
            self.group.name = name
            self.title.setText(name)
            self.changed.emit()
        self.edit.hide()
        self.title.show()

    def refresh_all_values(self):
        for row in self.rows:
            row.refresh_value()
