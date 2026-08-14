"""Dialog for adding attributes from the Channel Box or a manual plug."""

from __future__ import annotations

import maya.cmds as cmds

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                                   QDialogButtonBox, QHBoxLayout, QInputDialog,
                                   QLabel, QLineEdit, QListWidget, QListWidgetItem,
                                   QPushButton, QRadioButton, QStackedWidget,
                                   QVBoxLayout, QWidget)
except ImportError:
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import (QCheckBox, QComboBox, QDialog,
                                   QDialogButtonBox, QHBoxLayout, QInputDialog,
                                   QLabel, QLineEdit, QListWidget, QListWidgetItem,
                                   QPushButton, QRadioButton, QStackedWidget,
                                   QVBoxLayout, QWidget)

from core.attr_data import AttrEntry, AttrGroup
from core.channel_box import get_channelbox_selection, get_selected_objects, get_last_set_attr
from ui.styles import STYLESHEET

NEW_GROUP_LABEL = "New Group..."


def _nodes_with_shapes(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    return [node] + shapes


def _find_attr_owner(attr, node):
    for candidate in _nodes_with_shapes(node):
        if cmds.attributeQuery(attr, node=candidate, exists=True):
            return candidate
    return None


class AddAttrDialog(QDialog):
    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Attributes")
        self.setMinimumSize(440, 330)
        self.setStyleSheet(STYLESHEET)
        self.groups = groups
        self.entries = []
        self._created_group = None
        self._last_group_index = -1
        self._build()
        self.refresh_channel_box()

    def _build(self):
        root = QVBoxLayout(self)
        modes = QHBoxLayout()
        self.channel_mode = QRadioButton("Channel Box")
        self.manual_mode = QRadioButton("Manual")
        self.channel_mode.setChecked(True)
        self.channel_mode.toggled.connect(lambda checked: self.pages.setCurrentIndex(0 if checked else 1))
        modes.addWidget(self.channel_mode)
        modes.addWidget(self.manual_mode)
        modes.addStretch()
        root.addLayout(modes)
        self.pages = QStackedWidget()
        root.addWidget(self.pages)

        channel_page = QWidget()
        channel_layout = QVBoxLayout(channel_page)
        refresh = QPushButton("Refresh Channel Box selection")
        refresh.clicked.connect(self.refresh_channel_box)
        channel_layout.addWidget(refresh)
        self.channel_list = QListWidget()
        channel_layout.addWidget(self.channel_list)
        self.batch = QCheckBox("Add the selected attributes to every selected object")
        channel_layout.addWidget(self.batch)
        self.pages.addWidget(channel_page)

        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        manual_layout.addWidget(QLabel("Attribute plug (for example: |group|cube.translateX)"))
        self.plug_edit = QLineEdit()
        self.plug_edit.setPlaceholderText("node.attribute")
        manual_layout.addWidget(self.plug_edit)
        use_selected = QPushButton("Use selected object")
        use_selected.clicked.connect(self.use_selected_object)
        manual_layout.addWidget(use_selected)
        manual_layout.addStretch()
        self.pages.addWidget(manual_page)

        target = QHBoxLayout()
        target.addWidget(QLabel("Target group:"))
        self.group_combo = QComboBox()
        self._populate_group_combo()
        self.group_combo.currentIndexChanged.connect(self._on_group_combo_changed)
        target.addWidget(self.group_combo, 1)
        root.addLayout(target)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Display:"))
        self.type_auto = QRadioButton("Auto")
        self.type_number = QRadioButton("Number")
        self.type_color = QRadioButton("Color")
        self.type_auto.setChecked(True)
        type_row.addWidget(self.type_auto)
        type_row.addWidget(self.type_number)
        type_row.addWidget(self.type_color)
        type_row.addStretch()
        root.addLayout(type_row)

        buttons_row = QHBoxLayout()
        last_attr_btn = QPushButton("+ Last Lock Attr")
        last_attr_btn.setToolTip("Fill plug from the most recent Lock gesture on an Attribute Editor attribute")
        last_attr_btn.clicked.connect(self._fill_last_attr)
        buttons_row.addWidget(last_attr_btn)
        buttons_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.collect_and_accept)
        buttons.rejected.connect(self.reject)
        buttons_row.addWidget(buttons)
        root.addLayout(buttons_row)

    def _populate_group_combo(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        for index, group in enumerate(self.groups):
            if group.reference_namespace is not None:
                continue
            self.group_combo.addItem(group.name, index)
        self.group_combo.addItem(NEW_GROUP_LABEL, None)
        if self.group_combo.count() > 1:
            self.group_combo.setCurrentIndex(0)
        self.group_combo.blockSignals(False)

    def _on_group_combo_changed(self, _index):
        if self.group_combo.currentData() is not None:
            self._last_group_index = self.group_combo.currentIndex()
            return
        name, ok = QInputDialog.getText(self, "New Group", "Group name:", text="Group {}".format(len(self.groups) + 1))
        if not ok or not name.strip():
            self.group_combo.setCurrentIndex(max(self._last_group_index, 0))
            return
        group = AttrGroup(name.strip())
        self.groups.append(group)
        self._created_group = group
        new_index = len(self.groups) - 1
        insert_at = self.group_combo.count() - 1
        self.group_combo.blockSignals(True)
        self.group_combo.insertItem(insert_at, group.name, new_index)
        self.group_combo.setCurrentIndex(insert_at)
        self.group_combo.blockSignals(False)
        self._last_group_index = insert_at

    def reject(self):
        if self._created_group is not None and not self._created_group.entries:
            try:
                self.groups.remove(self._created_group)
            except ValueError:
                pass
        super().reject()

    def refresh_channel_box(self):
        self.channel_list.clear()
        nodes, attributes = get_channelbox_selection()
        for node in nodes:
            for attr in attributes:
                owner = _find_attr_owner(attr, node)
                if owner:
                    item = QListWidgetItem("{}.{}".format(owner.rsplit("|", 1)[-1], attr))
                    item.setData(Qt.UserRole, (owner, attr))
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self.channel_list.addItem(item)
        if not self.channel_list.count():
            placeholder = QListWidgetItem("No Channel Box attributes selected")
            placeholder.setFlags(Qt.NoItemFlags)
            self.channel_list.addItem(placeholder)
        self.batch.setVisible(len(get_selected_objects()) > 1)
        if not self.batch.isVisible():
            self.batch.setChecked(False)

    def use_selected_object(self):
        selected = get_selected_objects()
        if selected:
            self.plug_edit.setText(selected[0] + ".")
            self.plug_edit.setFocus()

    def _fill_last_attr(self):
        result = get_last_set_attr()
        if not result:
            cmds.warning("Attribute Manager: no recent Lock gesture found. Right-click an attribute in the Attribute Editor and choose Lock.")
            return
        node, attr = result
        self.manual_mode.setChecked(True)
        self.plug_edit.setText("{}.{}".format(node, attr))
        self.plug_edit.setFocus()

    @staticmethod
    def _entry(node, attr, display_type="auto"):
        long_node = (cmds.ls(node, long=True) or [node])[0]
        node_uuid = (cmds.ls(node, uuid=True) or [""])[0]
        nice_name = cmds.attributeQuery(attr, node=node, niceName=True) or attr
        entry = AttrEntry(nice_name, long_node, node_uuid, attr)
        entry.display_type = display_type
        return entry

    def _selected_display_type(self):
        if self.type_color.isChecked():
            return "color"
        if self.type_number.isChecked():
            return "number"
        return "auto"

    def collect_and_accept(self):
        self.entries = []
        dtype = self._selected_display_type()
        if self.channel_mode.isChecked():
            selected = []
            for index in range(self.channel_list.count()):
                item = self.channel_list.item(index)
                if item.checkState() == Qt.Checked and item.data(Qt.UserRole):
                    selected.append(item.data(Qt.UserRole))
            if self.batch.isChecked():
                attributes = {attr for _node, attr in selected}
                for node in get_selected_objects():
                    for attr in attributes:
                        owner = _find_attr_owner(attr, node)
                        if owner:
                            self.entries.append(self._entry(owner, attr, dtype))
            else:
                self.entries = [self._entry(node, attr, dtype) for node, attr in selected]
        else:
            plug = self.plug_edit.text().strip()
            if "." not in plug:
                cmds.warning("Attribute Manager: enter a node.attribute plug.")
                return
            node, attr = plug.rsplit(".", 1)
            nodes = cmds.ls(node, long=True) or []
            if not nodes:
                cmds.warning("Attribute Manager: node does not exist: {}".format(node))
                return
            owner = _find_attr_owner(attr, nodes[0])
            if not owner:
                cmds.warning("Attribute Manager: attribute does not exist: {}".format(plug))
                return
            self.entries = [self._entry(owner, attr, dtype)]
        if not self.entries:
            cmds.warning("Attribute Manager: no attributes were added.")
            return
        self.accept()

    def target_group_index(self):
        return self.group_combo.currentData()
