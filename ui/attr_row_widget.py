# -*- coding: utf-8 -*-
"""Editor widget for one Maya attribute."""

from __future__ import annotations

import json

import maya.cmds as cmds

try:
    from PySide6.QtCore import Qt, Signal, QMimeData, QTimer
    from PySide6.QtGui import QDrag, QAction
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                                   QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                                   QSlider, QSpinBox, QWidget)
except ImportError:  # Maya 2024 normally uses PySide6; retain older compatibility.
    from PySide2.QtCore import Qt, Signal, QMimeData, QTimer
    from PySide2.QtGui import QDrag
    from PySide2.QtWidgets import (QApplication, QAction, QCheckBox, QComboBox, QDialog,
                                   QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                                   QSlider, QSpinBox, QWidget)

from core.attr_data import AttrEntry

from core.channel_box import record_set_attr

MIME_TYPE = "application/x-attribute-manager-entry"


class ColorButton(QPushButton):
    def __init__(self, node, attr, parent=None):
        super().__init__(parent)
        self.node = node
        self.attr = attr
        self.setFixedWidth(40)
        self.setMinimumHeight(20)
        self.setMaximumHeight(22)
        self.setToolTip("{}.{}".format(node, attr))
        self.clicked.connect(self._pick_color)
        self._update_swatch()

    def _get_rgb(self):
        val = cmds.getAttr("{}.{}".format(self.node, self.attr))
        if val and isinstance(val[0], (list, tuple)):
            return val[0][:3]
        return (0.0, 0.0, 0.0)

    def _update_swatch(self):
        r, g, b = self._get_rgb()
        self.setStyleSheet(
            "background-color: rgb({},{},{}); border: 1px solid #666; border-radius: 2px;".format(
                int(r * 255), int(g * 255), int(b * 255)
            )
        )

    def _pick_color(self):
        record_set_attr(self.node, self.attr)
        r, g, b = self._get_rgb()
        result = cmds.colorEditor(rgb=[r, g, b])
        if result and cmds.colorEditor(query=True, result=True):
            values = cmds.colorEditor(query=True, rgb=True)
            nr, ng, nb = values[0], values[1], values[2]
            cmds.undoInfo(openChunk=True, chunkName="Attribute Manager: color {}.{}".format(self.node, self.attr))
            try:
                cmds.setAttr("{}.{}".format(self.node, self.attr), nr, ng, nb)
            except Exception as exc:
                cmds.warning("Attribute Manager: could not set color: {}".format(exc))
            finally:
                cmds.undoInfo(closeChunk=True)
            self._update_swatch()


class RangeDialog(QDialog):
    def __init__(self, current_min, current_max, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Slider Range")
        self.setMinimumWidth(280)
        form = QFormLayout(self)
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1000000.0, 1000000.0)
        self.min_spin.setDecimals(4)
        self.min_spin.setValue(current_min)
        form.addRow("Min:", self.min_spin)
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1000000.0, 1000000.0)
        self.max_spin.setDecimals(4)
        self.max_spin.setValue(current_max)
        form.addRow("Max:", self.max_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_values(self):
        return self.min_spin.value(), self.max_spin.value()


def writable_reason(node: str, attr: str) -> str:
    plug = "{}.{}".format(node, attr)
    if not cmds.objExists(plug):
        return "Attribute not found"
    try:
        if cmds.getAttr(plug, lock=True):
            return "Attribute is locked"
        inputs = cmds.listConnections(plug, source=True, destination=False) or []
        if inputs:
            return "Driven by {}".format(inputs[0])
    except Exception as exc:
        return "Cannot read attribute: {}".format(exc)
    return ""


class DragHandle(QLabel):
    def __init__(self, row: "AttrRowWidget"):
        super().__init__("≡")
        self.row = row
        self._start = None
        self.setObjectName("dragHandle")
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to reorder or move to another group")

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
        section = self.row.group_section
        if section is None:
            return
        payload = {"group_index": section.group_index(), "entry_index": section.row_index(self.row)}
        mime = QMimeData()
        mime.setData(MIME_TYPE, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction) if hasattr(drag, "exec") else drag.exec_(Qt.MoveAction)


class AttrRowWidget(QWidget):
    removed = Signal(object)
    changed = Signal()

    def __init__(self, entry: AttrEntry, group_section=None, parent=None, float_precision=False):
        super().__init__(parent)
        self.entry = entry
        self.group_section = group_section
        self._float_precision = float_precision
        self._value_widgets = []
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(5)
        layout.addWidget(DragHandle(self))

        self.name_label = QLabel(self.entry.display_name)
        self.name_label.setObjectName("nameLabel")
        self.name_label.setFixedHeight(20)
        self.name_label.setToolTip("{}.{}".format(self.entry.node_path, self.entry.attr))
        self.name_label.mouseDoubleClickEvent = self._begin_rename
        layout.addWidget(self.name_label)
        self.name_edit = QLineEdit(self.entry.display_name)
        self.name_edit.setFixedHeight(20)
        self.name_edit.hide()
        self.name_edit.editingFinished.connect(self._finish_rename)
        layout.addWidget(self.name_edit)

        node = self._resolve_node()
        reason = self.entry.invalid_reason or (writable_reason(node, self.entry.attr) if node else "Node not found")
        if reason:
            warning = QLabel(reason)
            warning.setStyleSheet("color: #d45a5a; font-size: 10px;")
            warning.setToolTip(reason)
            layout.addWidget(warning, 1)
            self.setStyleSheet("QLabel { color: #9a9a9a; }")
        else:
            try:
                self._build_editor(layout, node)
            except Exception as exc:
                warning = QLabel("Build error: {}".format(exc))
                warning.setStyleSheet("color: #d45a5a; font-size: 10px;")
                layout.addWidget(warning, 1)

        layout.addStretch(1)

        remove = QPushButton("×")
        remove.setObjectName("delBtn")
        remove.setFixedSize(20, 20)
        remove.setToolTip("Remove attribute")
        remove.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove)

    def _resolve_node(self):
        if self.entry.node_uuid:
            try:
                matches = cmds.ls(self.entry.node_uuid, long=True) or []
                if matches:
                    return matches[0]
            except Exception:
                pass
        return self.entry.node_path if cmds.objExists(self.entry.node_path) else None

    def _build_editor(self, layout, node):
        attr_type = cmds.getAttr("{}.{}".format(node, self.entry.attr), type=True)

        if self.entry.display_type == "color":
            if attr_type not in {"double3", "float3"}:
                cmds.warning(
                    "Attribute Manager: '{}' is type '{}', not a color; falling back to Auto.".format(
                        self.entry.attr, attr_type
                    )
                )
                self.entry.display_type = "auto"
            else:
                color_btn = ColorButton(node, self.entry.attr)
                layout.addWidget(color_btn)
                self._value_widgets.append(color_btn)
                return

        if self.entry.display_type == "number":
            if attr_type in {"bool", "enum", "message", "string"}:
                cmds.warning(
                    "Attribute Manager: '{}' is type '{}', not a number; falling back to Auto.".format(
                        self.entry.attr, attr_type
                    )
                )
                self.entry.display_type = "auto"
            else:
                if attr_type in {"double3", "float3", "double2", "float2"}:
                    children = cmds.attributeQuery(self.entry.attr, node=node, listChildren=True) or []
                    for child in children:
                        self._add_number(layout, node, child)
                else:
                    self._add_number(layout, node, self.entry.attr)
                return

        if attr_type == "bool":
            widget = QCheckBox()
            widget.setProperty("attrManagerPlug", "{}.{}".format(node, self.entry.attr))
            widget.setChecked(bool(cmds.getAttr("{}.{}".format(node, self.entry.attr))))
            widget.toggled.connect(lambda value: self._set_value(node, self.entry.attr, value))
            layout.addWidget(widget)
            self._value_widgets.append(widget)
        elif attr_type == "enum":
            widget = QComboBox()
            widget.setProperty("attrManagerPlug", "{}.{}".format(node, self.entry.attr))
            enum_data = cmds.attributeQuery(self.entry.attr, node=node, listEnum=True) or [""]
            widget.addItems(enum_data[0].split(":"))
            widget.setCurrentIndex(int(cmds.getAttr("{}.{}".format(node, self.entry.attr))))
            widget.currentIndexChanged.connect(lambda value: self._set_value(node, self.entry.attr, value))
            layout.addWidget(widget)
            self._value_widgets.append(widget)
        elif attr_type in {"double3", "float3", "double2", "float2"}:
            is_color = False
            try:
                is_color = cmds.attributeQuery(self.entry.attr, node=node, usedAsColor=True)[0]
            except Exception:
                pass
            if not is_color:
                is_color = "color" in self.entry.attr.lower()
            if is_color and attr_type in {"double3", "float3"}:
                color_btn = ColorButton(node, self.entry.attr)
                layout.addWidget(color_btn)
                self._value_widgets.append(color_btn)
            else:
                children = cmds.attributeQuery(self.entry.attr, node=node, listChildren=True) or []
                for child in children:
                    self._add_number(layout, node, child)
        elif attr_type in {"double", "float", "doubleLinear", "doubleAngle", "long", "short", "byte", "int"}:
            self._add_number(layout, node, self.entry.attr)
        else:
            value = QLineEdit(str(cmds.getAttr("{}.{}".format(node, self.entry.attr))))
            value.setReadOnly(True)
            value.setToolTip("This attribute type is display-only")
            layout.addWidget(value, 1)

    def _add_number(self, layout, node, attr):
        plug = "{}.{}".format(node, attr)
        kind = cmds.getAttr(plug, type=True)
        is_integer = kind in {"long", "short", "byte", "int"}
        attr_min = None
        attr_max = None
        try:
            if cmds.attributeQuery(attr, node=node, min=True)[0]:
                attr_min = cmds.attributeQuery(attr, node=node, minimum=True)[0]
        except Exception:
            pass
        try:
            if cmds.attributeQuery(attr, node=node, max=True)[0]:
                attr_max = cmds.attributeQuery(attr, node=node, maximum=True)[0]
        except Exception:
            pass

        value = cmds.getAttr(plug) or 0.0

        if self.entry.custom_min is not None and self.entry.custom_max is not None:
            effective_min = self.entry.custom_min
            effective_max = self.entry.custom_max
        elif attr_min is not None and attr_max is not None:
            effective_min = attr_min
            effective_max = attr_max
        else:
            span = max(10.0, abs(value) * 0.5)
            effective_min = value - span
            effective_max = value + span

        precision = self._get_slider_precision()

        spin = QSpinBox() if is_integer else QDoubleSpinBox()
        if not is_integer:
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
        spin.setRange(-1000000 if is_integer else -1000000.0, 1000000 if is_integer else 1000000.0)
        spin.setValue(value)
        spin.setProperty("attrManagerPlug", plug)
        spin.setMinimumWidth(72)
        spin.valueChanged.connect(lambda current, n=node, a=attr: self._set_value(n, a, current))
        layout.addWidget(spin)
        self._value_widgets.append(spin)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimumWidth(80)
        slider.setMaximumWidth(160)
        slider.setMinimum(int(effective_min * precision))
        slider.setMaximum(int(effective_max * precision))
        slider.setValue(int(value * precision))
        slider.setProperty("attrManagerPlug", plug)
        slider.setContextMenuPolicy(Qt.CustomContextMenu)
        slider.customContextMenuRequested.connect(
            lambda pos, s=slider, mn=effective_min, mx=effective_max, n=node, a=attr:
            self._slider_context_menu(s, mn, mx, n, a)
        )
        layout.addWidget(slider)
        self._value_widgets.append(slider)

        def _slider_changed(v, _spin=spin, _precision=precision, n=node, a=attr):
            real = v / _precision
            _spin.blockSignals(True)
            _spin.setValue(real)
            _spin.blockSignals(False)
            self._set_value(n, a, real if not is_integer else int(real), skip_chunk=True)

        def _spin_to_slider(v, _slider=slider, _precision=precision):
            _slider.blockSignals(True)
            _slider.setValue(int(v * _precision))
            _slider.blockSignals(False)

        def _slider_pressed(n=node, a=attr):
            cmds.undoInfo(openChunk=True, chunkName="Attribute Manager slider: {}.{}".format(n, a))

        def _slider_released():
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass

        slider.sliderPressed.connect(_slider_pressed)
        slider.sliderReleased.connect(_slider_released)
        slider.valueChanged.connect(_slider_changed)
        spin.valueChanged.connect(_spin_to_slider)

    def _slider_context_menu(self, slider, cur_min, cur_max, node, attr):
        menu = QMenu(self)
        lo = self.entry.custom_min if self.entry.custom_min is not None else cur_min
        hi = self.entry.custom_max if self.entry.custom_max is not None else cur_max

        set_min = menu.addAction("Set Min: {:.3f}".format(lo))
        set_max = menu.addAction("Set Max: {:.3f}".format(hi))
        menu.addSeparator()
        set_range = menu.addAction("Set Range...")
        menu.addSeparator()
        reset = menu.addAction("Reset Range")

        action = menu.exec_(slider.mapToGlobal(slider.rect().center())) if hasattr(menu, "exec_") else menu.exec(slider.mapToGlobal(slider.rect().center()))

        if action == reset:
            self.entry.custom_min = None
            self.entry.custom_max = None
            self._update_slider_range(slider, node, attr)
        elif action == set_range:
            dlg = RangeDialog(lo, hi, self)
            if dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec():
                new_lo, new_hi = dlg.get_values()
                if new_lo < new_hi:
                    self.entry.custom_min = new_lo
                    self.entry.custom_max = new_hi
                    self._update_slider_range(slider, node, attr)
        elif action == set_min:
            from PySide6.QtWidgets import QInputDialog
            val, ok = QInputDialog.getDouble(self, "Set Min", "Minimum:", lo, -1000000, 1000000, 4)
            if ok and val < hi:
                self.entry.custom_min = val
                self._update_slider_range(slider, node, attr)
        elif action == set_max:
            from PySide6.QtWidgets import QInputDialog
            val, ok = QInputDialog.getDouble(self, "Set Max", "Maximum:", hi, -1000000, 1000000, 4)
            if ok and val > lo:
                self.entry.custom_max = val
                self._update_slider_range(slider, node, attr)

    def _update_slider_range(self, slider, node, attr):
        precision = self._get_slider_precision()
        at_min = None
        at_max = None
        try:
            if cmds.attributeQuery(attr, node=node, min=True)[0]:
                at_min = cmds.attributeQuery(attr, node=node, minimum=True)[0]
        except Exception:
            pass
        try:
            if cmds.attributeQuery(attr, node=node, max=True)[0]:
                at_max = cmds.attributeQuery(attr, node=node, maximum=True)[0]
        except Exception:
            pass
        if self.entry.custom_min is not None and self.entry.custom_max is not None:
            lo = self.entry.custom_min
            hi = self.entry.custom_max
        elif at_min is not None and at_max is not None:
            lo = at_min
            hi = at_max
        else:
            value = 0.0
            try:
                value = cmds.getAttr("{}.{}".format(node, attr)) or 0.0
            except Exception:
                pass
            span = max(10.0, abs(value) * 0.5)
            lo = value - span
            hi = value + span
        slider.blockSignals(True)
        slider.setMinimum(int(lo * precision))
        slider.setMaximum(int(hi * precision))
        slider.blockSignals(False)
        self.changed.emit()

    def _get_slider_precision(self):
        return 1000 if self._float_precision else 1

    def _set_value(self, node, attr, value, skip_chunk=False):
        if skip_chunk:
            try:
                cmds.setAttr("{}.{}".format(node, attr), value)
                record_set_attr(node, attr)
            except Exception as exc:
                cmds.warning("Attribute Manager: could not set {}.{}: {}".format(node, attr, exc))
            self.changed.emit()
            return
        try:
            cmds.undoInfo(openChunk=True, chunkName="Attribute Manager: {}.{}".format(node, attr))
            cmds.setAttr("{}.{}".format(node, attr), value)
            record_set_attr(node, attr)
        except Exception as exc:
            cmds.warning("Attribute Manager: could not set {}.{}: {}".format(node, attr, exc))
        finally:
            cmds.undoInfo(closeChunk=True)
        self.changed.emit()

    def _begin_rename(self, _event):
        self.name_label.hide()
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(200)
        self._focus_timer.timeout.connect(self._check_focus)
        self._focus_timer.start()

    def _check_focus(self):
        if not self.name_edit.hasFocus():
            self._finish_rename()

    def _finish_rename(self):
        if hasattr(self, "_focus_timer"):
            self._focus_timer.stop()
        name = self.name_edit.text().strip()
        if name and name != self.entry.display_name:
            self.entry.display_name = name
            self.name_label.setText(name)
            self.changed.emit()
        self.name_edit.hide()
        self.name_label.show()

    def refresh_value(self):
        node = self._resolve_node()
        if not node:
            return
        precision = self._get_slider_precision()
        for widget in self._value_widgets:
            plug = widget.property("attrManagerPlug")
            if not plug:
                continue
            widget.blockSignals(True)
            try:
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(cmds.getAttr(plug)))
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(int(cmds.getAttr(plug)))
                elif isinstance(widget, QSlider):
                    val = cmds.getAttr(plug) or 0.0
                    widget.setValue(int(val * precision))
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(cmds.getAttr(plug))
            except Exception:
                pass
            finally:
                widget.blockSignals(False)
