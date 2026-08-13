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
    from shiboken6 import isValid, wrapInstance
except ImportError:
    from PySide2.QtCore import Qt, QTimer
    from PySide2.QtGui import QPainter, QPen, QColor
    from PySide2.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                                   QMainWindow, QMessageBox, QPushButton,
                                   QScrollArea, QVBoxLayout, QWidget)
    from shiboken2 import isValid, wrapInstance

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
        self._slider_chunks = set()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._save_timeout)
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
        self._apply_merged(load_config())

    def _apply_merged(self, merged_config):
        self.config = merged_config
        self._main_groups = [g for g in merged_config.groups if g.reference_namespace is None]
        self._ref_groups = [g for g in merged_config.groups if g.reference_namespace is not None]

        main_entries = {}
        for group in self._main_groups:
            for entry in group.entries:
                key = (entry.node_uuid or entry.node_path, entry.attr)
                main_entries.setdefault(key, []).append(entry)

        merged_ref_groups = []
        shown_main_keys = set()
        for ref_group in self._ref_groups:
            merged_entries = []
            for entry in ref_group.entries:
                key = (entry.node_uuid or entry.node_path, entry.attr)
                if key in main_entries:
                    merged_entries.append(main_entries[key][0])
                    shown_main_keys.add(key)
                else:
                    merged_entries.append(entry)
            if merged_entries:
                ref_group.entries = merged_entries
                merged_ref_groups.append(ref_group)

        visible_groups = []
        for group in self._main_groups:
            remaining = [e for e in group.entries
                         if (e.node_uuid or e.node_path, e.attr) not in shown_main_keys]
            if group.entries and not remaining:
                continue
            group.entries = remaining
            visible_groups.append(group)
        visible_groups.extend(merged_ref_groups)

        self.config.groups = visible_groups
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
        for row in list(self._slider_chunks):
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        self._slider_chunks.clear()
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
        if not any(g.reference_namespace is None for g in self.config.groups):
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

    def remove_override_entry(self, entry):
        key = (entry.node_uuid or entry.node_path, entry.attr)
        for group in self.config.groups:
            group.entries = [e for e in group.entries
                             if (group.reference_namespace is not None and e.is_referenced)
                             or (e.node_uuid or e.node_path, e.attr) != key]

    def move_entry(self, source_group_index, source_entry_index, target_section, target_index):
        if source_group_index < 0 or source_group_index >= len(self.config.groups):
            return
        source = self.config.groups[source_group_index]
        if source_entry_index < 0 or source_entry_index >= len(source.entries):
            return
        target = target_section.group
        if target.reference_namespace is not None:
            return
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
        if group.reference_namespace is not None:
            self.config.groups.insert(source_index, group)
            return
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

    def _save_timeout(self):
        m_utils.executeDeferred(self._save_guard, lowPriority=True)

    def _save_guard(self, *args, **kwargs):
        try:
            if isValid(self):
                self._do_save()
        except Exception:
            pass

    def _do_save(self):
        main_groups = []
        for group in self.config.groups:
            if group.reference_namespace is None:
                main_groups.append(group)
            else:
                overrides = [e for e in group.entries if not e.is_referenced]
                if overrides:
                    main_groups.append(AttrGroup(
                        name=group.name,
                        order=group.order,
                        collapsed=False,
                        entries=overrides,
                    ))
        main_config = Config(
            version=self.config.version,
            slider_float_precision=self.config.slider_float_precision,
            groups=main_groups,
        )
        main_config.normalise_orders()
        ok = save_config(main_config)
        if not ok:
            cmds.warning("Attribute Manager: failed to save configuration to scene.")

    def _teardown(self):
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
        if _window is self:
            _window = None

    def closeEvent(self, event):
        self._teardown()
        self.deleteLater()
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


def _set_panel_visibility_callback(workspace):
    """On panel reopen, refetch the scene config; on close, flush any pending save."""
    def _on_visibility(*args, **kwargs):
        global _window
        if _window is None:
            return
        try:
            visible = cmds.workspaceControl(workspace, query=True, visible=True)
        except Exception:
            return
        try:
            if visible:
                _window.load_scene_config()
            else:
                timer = getattr(_window, "_save_timer", None)
                if timer is not None and timer.isActive():
                    _window._do_save()
        except Exception as exc:
            cmds.warning("Attribute Manager: panel visibility callback failed: {}".format(exc))

    try:
        cmds.workspaceControl(workspace, edit=True, visibleChangeCommand=_on_visibility)
    except Exception:
        pass


LEGACY_WORKSPACE_NAME = "attrManagerMainWindowWorkspaceControl"


def _attach_to_workspace(window, workspace):
    """Attach the window to an existing workspace control, preserving its layout."""
    try:
        window.show()
        for _ in range(20):
            QApplication.processEvents()
        wc_ptr = omui.MQtUtil.findControl(workspace)
        win_ptr = omui.MQtUtil.findControl(WINDOW_OBJECT_NAME)
        if wc_ptr is None or win_ptr is None:
            return False
        omui.MQtUtil.addWidgetToMayaLayout(int(win_ptr), int(wc_ptr))
        for _ in range(20):
            QApplication.processEvents()
        parent = window.parentWidget()
        if parent is None or parent.objectName() != workspace:
            return False
        _set_panel_visibility_callback(workspace)
        return True
    except Exception:
        return False


def _set_ui_script(workspace):
    """Let Maya rebuild the panel automatically when it restores this workspace control.

    The Python flavour of workspaceControl treats ``uiScript`` as Python code, so pass
    bare Python (no ``python("...")`` MEL wrapper); Maya wraps it when persisting.
    Forward slashes avoid backslash escaping through the MEL/JSON layers.
    """
    import os as _os
    launch_path = _os.path.abspath(
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "launch.py")
    ).replace("\\", "/")
    script = (
        "__file__ = r'{path}'; exec(compile(open(__file__).read(), __file__, 'exec'))"
    ).format(path=launch_path)
    try:
        cmds.workspaceControl(workspace, edit=True, uiScript=script)
    except Exception:
        pass


def _restore_from_ui_script(*args, **kwargs):
    """Called by Maya's workspace control uiScript when the session is restored."""
    global _window
    if _window is not None and isValid(_window):
        return
    try:
        launch(dockable=True)
    except Exception as exc:
        cmds.warning("Attribute Manager: session restore failed: {}".format(exc))


def launch(dockable=True):
    global _window
    _kill_stale_jobs()
    workspace = WINDOW_OBJECT_NAME + "WorkspaceControl"
    if cmds.workspaceControl(LEGACY_WORKSPACE_NAME, exists=True):
        try:
            cmds.deleteUI(LEGACY_WORKSPACE_NAME, control=True)
        except Exception:
            pass
    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT_NAME:
            try:
                timer = getattr(widget, "_save_timer", None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
            widget.close()
            widget.deleteLater()

    if cmds.workspaceControl(workspace, exists=True):
        cmds.workspaceControl(workspace, edit=True, close=True)
        _window = AttrManagerWindow()
        if dockable:
            if not _attach_to_workspace(_window, workspace):
                cmds.deleteUI(workspace, control=True)
                _window.show(dockable=True, floating=True)
                _window.show(dockable=True, area="right", floating=False)
                _set_ui_script(workspace)
                _set_panel_visibility_callback(workspace)
        else:
            _window.show()
        return _window

    _window = AttrManagerWindow()
    if dockable:
        _window.show(dockable=True, floating=True)
        _window.show(dockable=True, area="right", floating=False)
        _set_ui_script(workspace)
        _set_panel_visibility_callback(workspace)
    else:
        _window.show()
    return _window
