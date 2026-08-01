"""Dockable Attribute Manager main window."""

from __future__ import annotations

import maya.cmds as cmds
import maya.OpenMayaUI as omui
import maya.utils as m_utils

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPainter, QPen, QColor
    from PySide6.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                                   QMainWindow, QMessageBox, QPushButton,
                                   QScrollArea, QVBoxLayout, QWidget)
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2.QtCore import Qt, QTimer
    from PySide2.QtGui import QPainter, QPen, QColor
    from PySide2.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                                   QMainWindow, QMessageBox, QPushButton,
                                   QScrollArea, QVBoxLayout, QWidget)
    from shiboken2 import wrapInstance

from core.attr_data import AttrGroup, Config, resolve_entries
from core.scene_io import load_config, save_config
from ui.add_attr_dialog import AddAttrDialog
from ui.group_section import GroupSection, GROUP_MIME_TYPE
from ui.styles import STYLESHEET

import json

try:
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
except ImportError:
    class MayaQWidgetDockableMixin:
        pass


WINDOW_OBJECT_NAME = "attributeManagerMayaMainWindow"

_active_jobs = []


class GroupContainer(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ref = window
        self.setAcceptDrops(True)
        self._indicator_y = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(GROUP_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(GROUP_MIME_TYPE):
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
        if not event.mimeData().hasFormat(GROUP_MIME_TYPE):
            event.ignore()
            return
        try:
            data = json.loads(bytes(event.mimeData().data(GROUP_MIME_TYPE)).decode("utf-8"))
        except (TypeError, ValueError):
            event.ignore()
            return
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target = self._calc_drop_index(point.y())
        self.window_ref.move_group(data["group_index"], target)
        event.acceptProposedAction()

    def _sections(self):
        return [w for w in (self.layout().itemAt(i).widget() for i in range(self.layout().count())) if isinstance(w, GroupSection)]

    def _calc_drop_index(self, y):
        sections = self._sections()
        for index, section in enumerate(sections):
            if y < section.geometry().center().y():
                return index
        return len(sections)

    def _calc_indicator_y(self, y):
        sections = self._sections()
        for section in sections:
            geo = section.geometry()
            if y < geo.center().y():
                return geo.top()
        if sections:
            return sections[-1].geometry().bottom() + 1
        return 0

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._indicator_y is None:
            return
        painter = QPainter(self)
        painter.setPen(QPen(QColor(82, 133, 166), 3))
        painter.drawLine(4, self._indicator_y, self.width() - 4, self._indicator_y)
        painter.end()


def maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QWidget)


class AttrManagerWindow(MayaQWidgetDockableMixin, QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent or maya_main_window())
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("Attribute Manager")
        self.setMinimumSize(330, 420)
        self.setStyleSheet(STYLESHEET)
        self.config = Config()
        self.sections = []
        self.script_jobs = []
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._do_save)
        self._build()
        self._create_jobs()
        self.load_scene_config()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("attributeToolbar")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(4, 4, 4, 4)
        toolbar.setSpacing(3)
        add = QPushButton("Add")
        add.setToolTip("Add attributes from the Channel Box or a plug")
        add.clicked.connect(self.add_attributes)
        toolbar.addWidget(add)
        new_group = QPushButton("New Group")
        new_group.clicked.connect(self.add_group)
        toolbar.addWidget(new_group)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        renderer = QHBoxLayout()
        self.int_btn = QPushButton("Int Snap")
        self.int_btn.setCheckable(True)
        self.int_btn.setChecked(True)
        self.int_btn.clicked.connect(lambda: self._set_snap(False))
        renderer.addWidget(self.int_btn)
        self.float_btn = QPushButton("Float Snap")
        self.float_btn.setCheckable(True)
        self.float_btn.clicked.connect(lambda: self._set_snap(True))
        renderer.addWidget(self.float_btn)
        toolbar.addStretch()
        toolbar.addLayout(renderer)
        layout.addWidget(toolbar_widget)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = GroupContainer(self)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(3, 3, 3, 3)
        self.content_layout.setSpacing(3)
        self.content_layout.addStretch()
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def _create_jobs(self):
        self.script_jobs.append(cmds.scriptJob(event=["SceneOpened", self._deferred_load], protected=True))
        self.script_jobs.append(cmds.scriptJob(event=["Undo", self._deferred_refresh], protected=True))
        self.script_jobs.append(cmds.scriptJob(event=["Redo", self._deferred_refresh], protected=True))
        global _active_jobs
        _active_jobs = list(self.script_jobs)

    def _deferred_load(self):
        m_utils.executeDeferred(self._load_guard, lowPriority=True)

    def _load_guard(self, *args, **kwargs):
        self.load_scene_config()

    def _deferred_refresh(self):
        m_utils.executeDeferred(self._refresh_guard, lowPriority=True)

    def _refresh_guard(self, *args, **kwargs):
        self.refresh_all_values()

    def refresh_all_values(self):
        for section in self.sections:
            try:
                section.refresh_all_values()
            except Exception as exc:
                cmds.warning("Attribute Manager: refresh failed: {}".format(exc))

    def load_scene_config(self):
        self.config = load_config()
        self._update_snap_buttons()
        self.rebuild()

    def _update_snap_buttons(self):
        is_float = self.config.slider_float_precision
        self.int_btn.setChecked(not is_float)
        self.float_btn.setChecked(is_float)

    def _set_snap(self, use_float: bool):
        self.config.slider_float_precision = use_float
        self._update_snap_buttons()
        self.rebuild()
        self.save()

    def rebuild(self):
        self.sections = []
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.config.normalise_orders()
        for group in self.config.groups:
            try:
                section = GroupSection(group, float_precision=self.config.slider_float_precision)
            except Exception as exc:
                cmds.warning("Attribute Manager: failed to build group '{}': {}".format(group.name, exc))
                continue
            section.changed.connect(self.save)
            section.remove_requested.connect(self.remove_group)
            section.move_requested.connect(self.move_entry)
            self.content_layout.insertWidget(self.content_layout.count() - 1, section)
            self.sections.append(section)
        self.content.update()

    def add_group(self):
        default = "Group {}".format(len(self.config.groups) + 1)
        name, ok = QInputDialog.getText(self, "New Group", "Group name:", text=default)
        if not ok or not name.strip():
            return
        self.config.groups.append(AttrGroup(name.strip()))
        self.rebuild()
        self.save()

    def add_attributes(self):
        if not self.config.groups:
            self.add_group()
            if not self.config.groups:
                return
        dialog = AddAttrDialog(self.config.groups, self)
        dialog.setWindowModality(Qt.NonModal)
        dialog.accepted.connect(lambda: self._on_add_accepted(dialog))
        dialog.show()
        dialog.raise_()

    def _on_add_accepted(self, dialog):
        target = dialog.target_group_index()
        if target is None or target >= len(self.config.groups):
            return
        group = self.config.groups[target]
        existing = {(entry.node_uuid or entry.node_path, entry.attr) for entry in group.entries}
        for entry in dialog.entries:
            key = (entry.node_uuid or entry.node_path, entry.attr)
            if key not in existing:
                entry.order = len(group.entries)
                group.entries.append(entry)
                existing.add(key)
        self.rebuild()
        self.save()

    def remove_group(self, section):
        answer = QMessageBox.question(self, "Remove Group", "Remove this group and its attributes?")
        if answer != QMessageBox.Yes:
            return
        self.config.groups.remove(section.group)
        self.rebuild()
        self.save()

    def move_entry(self, source_group_index, source_entry_index, target_section, target_index):
        if source_group_index < 0 or source_group_index >= len(self.config.groups):
            return
        source = self.config.groups[source_group_index]
        if source_entry_index < 0 or source_entry_index >= len(source.entries):
            return
        target = target_section.group
        entry = source.entries.pop(source_entry_index)
        if source is target and target_index > source_entry_index:
            target_index -= 1
        target.entries.insert(min(target_index, len(target.entries)), entry)
        for i, e in enumerate(target.entries):
            e.order = i
        if source is not target:
            for i, e in enumerate(source.entries):
                e.order = i
        self.rebuild()
        self.save()

    def move_group(self, source_index, target_index):
        if source_index < 0 or source_index >= len(self.config.groups):
            return
        group = self.config.groups.pop(source_index)
        if target_index > source_index:
            target_index -= 1
        self.config.groups.insert(min(target_index, len(self.config.groups)), group)
        for i, g in enumerate(self.config.groups):
            g.order = i
        self.rebuild()
        self.save()

    def refresh(self):
        resolve_entries(self.config)
        self.rebuild()

    def save(self):
        self._save_timer.start()

    def _do_save(self):
        self.config.normalise_orders()
        ok = save_config(self.config)
        if not ok:
            cmds.warning("Attribute Manager: failed to save configuration to scene.")

    def closeEvent(self, event):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._do_save()
        for job in self.script_jobs:
            try:
                if cmds.scriptJob(exists=job):
                    cmds.scriptJob(kill=job, force=True)
            except Exception:
                pass
        self.script_jobs = []
        global _active_jobs
        _active_jobs = []
        global _window
        _window = None
        super().closeEvent(event)


_window = None


def _kill_stale_jobs():
    global _active_jobs
    for job in _active_jobs:
        try:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        except Exception:
            pass
    _active_jobs = []
    try:
        jobs = cmds.scriptJob(listJobs=True) or []
    except Exception:
        return
    tokens = (WINDOW_OBJECT_NAME, AttrManagerWindow.__name__, "_deferred_load", "_deferred_refresh")
    for job in jobs:
        if not any(tok in job for tok in tokens):
            continue
        try:
            job_id = int(job.split(":", 1)[0].strip())
            cmds.scriptJob(kill=job_id, force=True)
        except Exception:
            pass


def launch(dockable=True):
    global _window
    _kill_stale_jobs()
    workspace = WINDOW_OBJECT_NAME + "WorkspaceControl"
    if cmds.workspaceControl(workspace, exists=True):
        cmds.workspaceControl(workspace, edit=True, close=True)
        cmds.deleteUI(workspace, control=True)
    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT_NAME:
            widget.close()
            widget.deleteLater()
    _window = AttrManagerWindow()
    if dockable:
        _window.show(dockable=True, area="right", floating=False)
    else:
        _window.show()
    return _window
