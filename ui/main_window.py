"""Dockable Attribute Manager main window."""

from __future__ import annotations

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.OpenMayaUI as omui
import maya.utils as m_utils

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPainter, QPen, QColor
    from PySide6.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                                   QMessageBox, QPushButton,
                                   QScrollArea, QVBoxLayout, QWidget)
    from shiboken6 import isValid, wrapInstance
except ImportError:
    from PySide2.QtCore import Qt, QTimer
    from PySide2.QtGui import QPainter, QPen, QColor
    from PySide2.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                                   QMessageBox, QPushButton,
                                   QScrollArea, QVBoxLayout, QWidget)
    from shiboken2 import isValid, wrapInstance

from core.attr_data import AttrGroup, Config
from core.channel_box import enable_command_hook, disable_command_hook, unlock_attr
from core.merge import collect_for_save, merge_for_display
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
_scene_callbacks = []


def _enable_scene_message_callbacks(window):
    """Register MSceneMessage callbacks so reference/import changes re-read the config.

    There is NO scriptJob event for reference changes ("referenceStateChanged"
    does not exist in Maya 2024 — the scriptJob call raises), so the OpenMaya
    API 2.0 message callbacks are used instead (same pattern as the command
    hook in core/channel_box.py). The enum constants differ across Maya
    builds (e.g. kAfterReferenceEdit does not exist in Maya 2024's API 2.0),
    so each one is probed with getattr and silently skipped when missing.
    """
    global _scene_callbacks
    if _scene_callbacks:
        return
    message_names = (
        "kAfterReference",
        "kAfterReferenceEdit",
        "kAfterCreateReference",
        "kAfterImportReference",
        "kAfterRemoveReference",
        "kAfterLoadReference",
        "kAfterUnloadReference",
        "kAfterImport",
    )
    for name in message_names:
        msg = getattr(om2.MSceneMessage, name, None)
        if msg is None:
            continue
        try:
            _scene_callbacks.append(om2.MSceneMessage.addCallback(msg, window._schedule_reload))
        except Exception:
            pass


def _disable_scene_message_callbacks():
    """Remove all registered MSceneMessage callbacks (safe to call repeatedly)."""
    global _scene_callbacks
    for cb in _scene_callbacks:
        try:
            om2.MMessage.removeCallback(cb)
        except Exception:
            pass
    _scene_callbacks = []


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


class AttrManagerWindow(MayaQWidgetDockableMixin, QWidget):
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
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(150)
        self._reload_timer.timeout.connect(self._deferred_load)
        self._build()
        self._create_jobs()
        self.load_scene_config()

    def _build(self):
        layout = QVBoxLayout(self)
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
        enable_command_hook()
        _enable_scene_message_callbacks(self)
        self.script_jobs.append(cmds.scriptJob(event=["SceneOpened", self._deferred_load], protected=True))
        self.script_jobs.append(cmds.scriptJob(event=["Undo", self._deferred_refresh], protected=True))
        self.script_jobs.append(cmds.scriptJob(event=["Redo", self._deferred_refresh], protected=True))
        global _active_jobs
        _active_jobs = list(self.script_jobs)

    def _schedule_reload(self, *args, **kwargs):
        # Reference create/load/unload fires scene messages several times
        # mid-operation; debounce so the config is re-read once, after the
        # reference has settled.
        if not isValid(self):
            return
        self._reload_timer.start()

    def _deferred_load(self):
        m_utils.executeDeferred(self._load_guard, lowPriority=True)

    def _load_guard(self, *args, **kwargs):
        if isValid(self):
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
        self.config = merge_for_display(merged_config)
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
            # A right-click "Lock" on an Attribute Editor attribute is the
            # "add to Attribute Manager" gesture: the plug was recorded while
            # staying locked, so unlock it now that the add is confirmed.
            unlock_attr(entry.node_path, entry.attr)
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
        """Re-read the scene config, picking up reference namespace changes."""
        self._do_save()
        self.load_scene_config()

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
        ok = save_config(collect_for_save(self.config))
        if not ok:
            cmds.warning("Attribute Manager: failed to save configuration to scene.")

    def _teardown(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._do_save()
        if self._reload_timer.isActive():
            self._reload_timer.stop()
        disable_command_hook()
        _disable_scene_message_callbacks()
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
    tokens = (WINDOW_OBJECT_NAME, AttrManagerWindow.__name__, "_deferred_load", "_deferred_refresh", "_schedule_reload")
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
                _window._schedule_reload()
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


def _purge_stray_workspace_widgets(*args, **kwargs):
    """Close stray blank workspace-control windows restored by Maya.

    The legacy floating control (see LEGACY_WORKSPACE_NAME) can be restored
    by Maya AFTER launch() has already run (workspace layout restores before
    the floating-window list), so a delete-only-in-launch strategy misses it.
    Blank workspace windows that are not the panel are torn down here.
    """
    try:
        from PySide6.QtWidgets import QApplication as _App
    except ImportError:
        from PySide2.QtWidgets import QApplication as _App
    for widget in _App.topLevelWidgets():
        if widget.property("WorkspaceZOrderWidgetID") is None:
            continue
        name = widget.objectName()
        if name in (WINDOW_OBJECT_NAME, WINDOW_OBJECT_NAME + "WorkspaceControl"):
            continue
        if widget.windowTitle().strip():
            continue
        try:
            widget.deleteLater()
        except Exception:
            pass


def _delete_legacy_workspace(*args, **kwargs):
    """Delete the legacy workspace control, retried after Maya's window
    restore runs so a late-restored floating legacy control is still caught.
    Also purges any stray blank workspace widgets as a Qt-level fallback."""
    try:
        if cmds.workspaceControl(LEGACY_WORKSPACE_NAME, exists=True):
            cmds.deleteUI(LEGACY_WORKSPACE_NAME, control=True)
    except Exception:
        pass
    try:
        _purge_stray_workspace_widgets()
    except Exception:
        pass


def _set_ui_script(workspace):
    """Let Maya rebuild the panel automatically when it restores this workspace control.

    The Python flavour of workspaceControl treats ``uiScript`` as Python code, so pass
    bare Python (no ``python("...")`` MEL wrapper); Maya wraps it when persisting.
    Forward slashes avoid backslash escaping through the MEL/JSON layers.

    The script routes through ``_restore_from_ui_script`` (NOT ``exec launch.py``):
    when Maya re-initialises the control mid-session (e.g. re-docking a torn-out
    panel), the window is still alive and the script must NOT rebuild it — an
    unconditional rebuild races Maya's layout operation and corrupts the window's
    native QWindow (crash on the next tab switch). Only a real session restore
    (no live window) rebuilds, deferred to Maya's idle time.
    """
    import os as _os
    script_dir = _os.path.abspath(
        _os.path.dirname(_os.path.abspath(__file__)) + "/.."
    ).replace("\\", "/")
    script = (
        "import sys; sys.path.insert(0, r'{dir}'); "
        "from ui.main_window import _restore_from_ui_script; "
        "_restore_from_ui_script()"
    ).format(dir=script_dir)
    try:
        cmds.workspaceControl(workspace, edit=True, uiScript=script)
    except Exception:
        pass


def _restore_guard(*args, **kwargs):
    try:
        launch(dockable=True, restore=True)
    except Exception as exc:
        cmds.warning("Attribute Manager: session restore failed: {}".format(exc))


def _restore_from_ui_script(*args, **kwargs):
    """Called by Maya's workspace control uiScript when it (re)initialises the control.

    If the panel window is still alive (re-dock of a live panel), do nothing —
    rebuilding here races Maya's layout operation and corrupts the native window.
    If there is no live window (Maya session restore), rebuild, deferred to idle
    so the workspace layout has settled.
    """
    global _window
    if _window is not None and isValid(_window):
        return
    try:
        m_utils.executeDeferred(_restore_guard, lowPriority=True)
    except Exception as exc:
        cmds.warning("Attribute Manager: session restore failed: {}".format(exc))


def _ensure_panel_width(window, workspace):
    """Reset a docked panel to its minimum width so Maya's layout cache
    does not lock the splitter at a larger width.

    Maya caches the workspace control container's sizeHint at dock time (from
    the retained layout record); that cached value becomes the splitter's
    minimum, so a panel widened in a previous session cannot be shrunk again.
    Cycling the control through floating (at 330px) and back into the dock
    re-initialises the container at 330px. The uiScript is cleared first so
    Maya does not rebuild the window mid-cycle, then restored.
    """
    if not isValid(window):
        return
    try:
        page = window.parentWidget()
        if page is None or page.minimumSizeHint().width() <= 340:
            return
    except Exception:
        return
    try:
        cmds.workspaceControl(workspace, edit=True, floating=True)
        for _ in range(10):
            QApplication.processEvents()
        cmds.workspaceControl(workspace, edit=True, resizeWidth=330, resizeHeight=420)
        cmds.workspaceControl(workspace, edit=True, uiScript="")
        cmds.workspaceControl(workspace, edit=True, dockToMainWindow=("right", False))
        for _ in range(20):
            QApplication.processEvents()
        _set_ui_script(workspace)
        _set_panel_visibility_callback(workspace)
    except Exception:
        pass


def _close_old_windows():
    for widget in QApplication.allWidgets():
        if not isValid(widget):
            continue
        if widget.objectName() == WINDOW_OBJECT_NAME:
            try:
                timer = getattr(widget, "_save_timer", None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
            widget.close()
            widget.deleteLater()


def _delete_workspace_control(workspace):
    try:
        cmds.workspaceControl(workspace, edit=True, close=True)
    except Exception:
        pass
    try:
        cmds.deleteUI(workspace, control=True)
    except Exception:
        pass


def _create_window():
    return AttrManagerWindow()


def _attach_to_restored_control(window, workspace):
    """Attach ``window`` into a workspace control Maya already restored.

    Returns False (without touching anything) if the container is gone or
    the attach fails, so the caller can fall back to the fresh-dock path.
    """
    container = omui.MQtUtil.findControl(workspace)
    if container is None:
        return False
    try:
        omui.MQtUtil.addWidgetToMayaLayout(int(window), int(container))
        window.show()
        return True
    except Exception:
        return False


def _finalize(window, workspace):
    _set_ui_script(workspace)
    _set_panel_visibility_callback(workspace)


def _dock_fresh(window, workspace):
    window.show(dockable=True, floating=True)
    window.show(dockable=True, area="right", floating=False)
    _finalize(window, workspace)
    _ensure_panel_width(window, workspace)
    m_utils.executeDeferred(_purge_stray_workspace_widgets, lowPriority=False)


def launch(dockable=True, restore=False):
    """Build and dock the panel.

    ``restore=True`` is used ONLY by the session-restore path
    (``_restore_from_ui_script`` → ``_restore_guard``): Maya has already
    recreated the workspace control at its saved position (tab groups
    included), so the fresh container is reused and the saved tab placement
    is preserved. Every other call goes through the fresh path below.
    """
    global _window
    _kill_stale_jobs()
    workspace = WINDOW_OBJECT_NAME + "WorkspaceControl"
    # Delete the legacy control immediately AND after Maya finishes restoring
    # the floating-window list (which can recreate it after this function runs).
    _delete_legacy_workspace()
    m_utils.executeDeferred(_delete_legacy_workspace, lowPriority=False)
    _close_old_windows()

    # Session restore: reuse the container Maya just rebuilt. Its container is
    # fresh for this session (no accumulated Qt state), so this does not touch
    # the "never reuse" crash path below, which applies to mid-session
    # retained/restored containers.
    if restore and cmds.workspaceControl(workspace, exists=True):
        window = _create_window()
        if _attach_to_restored_control(window, workspace):
            _finalize(window, workspace)
            _window = window
            return window
        _delete_workspace_control(workspace)

    # Fresh path: never reuse an existing workspace control — re-attaching a
    # fresh window into a retained/restored container leaves Maya's layout
    # unstable (tear-out/re-dock/tab-switch of the panel then accumulates
    # Qt-internal corruption — QStackedLayout::takeAt / QWindow::screen crashes,
    # verified in Maya 2024). Delete the old control entirely and rebuild fresh.
    _delete_workspace_control(workspace)
    _window = _create_window()
    if dockable:
        _dock_fresh(_window, workspace)
    else:
        _window.show()
    return _window
