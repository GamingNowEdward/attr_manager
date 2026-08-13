# Attribute Manager — Agent Guide

## What This Is
A dockable Maya 2024/2025 panel (Python 3 + PySide6) that aggregates scene attributes into grouped, draggable, editable rows. Config persists inside the scene file on a locked `network` node named `attrManager`.

## Running
No build step. In Maya Script Editor:
```python
exec(open(r"C:\opencode\attributeManager_maya\launch.py").read())
```
`launch()` hot-reloads all modules automatically. The launcher auto-configures `sys.path` — no manual setup needed.

## Architecture
- `attributeManager.py` — entry point, module reload, `__init__.py` re-exports `launch`/`reload_modules` from it.
- `core/attr_data.py` — pure dataclasses (AttrEntry, AttrGroup, Config) + JSON serialisation. No Maya imports except `resolve_entries()`. `Config.slider_float_precision` is a global Int/Float Snap flag.
- `core/scene_io.py` — reads/writes config JSON to a locked `network` node (`attrManager.config`). `save_config()` disables undo around the WHOLE operation (node create, `lockNode`, lock-state `setAttr`, JSON write) so it adds zero undo entries. `get_or_create_node()` handles a same-named non-network node by warning + creating `attrManager1`; `_config_nodes()` falls back to prefix matching.
- `core/channel_box.py` — queries Channel Box selected attributes (main + shape); also holds `record_set_attr`/`get_last_set_attr` for the "+ Last Attr" feature (reads panel-recorded plug first, then parses MEL `$gCommandReporter` history via `_parse_set_attr_line`).
- `ui/main_window.py` — `MayaQWidgetDockableMixin` + `QMainWindow`. Contains `GroupContainer` (group-level drop target) and `move_group`/`move_entry` logic. `save()` is 300ms-debounced via a single-shot `QTimer`; toolbar has Int/Float Snap toggle. Registers `SceneOpened`/`Undo`/`Redo` scriptJobs; Undo/Redo run a deferred `refresh_all_values()` so panel values re-sync after undo. `launch()` calls `_kill_stale_jobs()` (kills jobs in the module-level `_active_jobs` registry AND scans `cmds.scriptJob(listJobs=True)` by name) before rebuilding, because closing a docked panel does NOT fire `closeEvent`.
- `ui/group_section.py` — collapsible group with `EntryContainer` (entry-level drop target, #5285a6 indicator line). `GroupDragHandle` distinguishes click (collapse) vs drag (reorder) by 8px threshold. Empty groups show a `dropPlaceholder` QLabel (via `_ensure_placeholder()`) so they stay a visible, valid drop target; `_entry_widgets()` excludes the placeholder from index math.
- `ui/attr_row_widget.py` — per-attribute row: DragHandle, name (double-click rename), type-matched editor. Numeric rows: SpinBox + Slider; slider right-click opens Set Min/Max/Range/Reset menu (`RangeDialog`); slider drags are wrapped in ONE undo chunk via `sliderPressed/Released` + `_set_value(..., skip_chunk=True)`. `ColorButton` opens `cmds.colorEditor`. `display_type` (auto/number/color) can override auto-detection.
- `ui/add_attr_dialog.py` — non-modal dialog; Channel Box or manual plug input; searches transform + shapes via `_find_attr_owner`. Has Display type (Auto/Number/Color) radio group and a "+ Last Attr" button that fills the plug from the last modified attribute.
- `ui/styles.py` — global QSS (Maya Channel Box gray theme, #464646 bg; #5285a6 accent for text/list selection highlight and drag indicators).

## Critical Gotchas
- **UUID lookup**: Use `cmds.ls(uuid_string, long=True)`. Do NOT use `cmds.ls(uuid=uuid_string)` — the `-uuid` flag is boolean and returns ALL uuids.
- **Dockable window reopen**: Must `cmds.deleteUI(objectName + "WorkspaceControl")` before creating a new instance, or Maya raises "name not unique". Also kill the old window's scriptJobs before closing, or stale jobs survive and reference destroyed objects.
- **PySide6 `exec`**: `QDialog.exec_()` and `QDrag.exec_()` removed in PySide6. Use `hasattr(obj, "exec")` guard.
- **PySide2 `QAction`**: Lives in `QtWidgets` (PySide2), NOT `QtGui`. PySide6 moved it to `QtGui`. Import from the correct module in each try/except branch.
- **Maya focus**: `QApplication.focusChanged` does not fire when clicking Maya viewport. Use `QTimer(200ms)` polling `hasFocus()` for rename confirmation.
- **`attributeQuery` min/max**: `minimum=True` throws if attr has no min. Must check `min=True` first (returns [bool]) or wrap in try/except.
- **`EntryContainer._layout`**: Named `_layout` (not `layout`) to avoid shadowing `QWidget.layout()`.
- **Drag events**: `QLabel` does not accept mouse press by default. Must call `event.accept()` in `mousePressEvent` to get implicit grab and receive `mouseMoveEvent`.
- **`normalise_orders()`**: Sorts by `.order` field. After any list reorder, update `.order` values BEFORE calling `rebuild()` (which calls `normalise_orders`), or the move is silently reverted.
- **Shape attributes**: `cmds.ls(sl=True)` returns transforms only. Use `cmds.listRelatives(node, shapes=True)` to find shape attrs. Channel Box shape attrs need `-selectedShapeAttributes` flag.
- **`evalDeferred`**: Takes a string, not a Python callable. For deferred Python function calls use `maya.utils.executeDeferred(func, lowPriority=True)`.
- **Slider precision**: Slider is integer-based; precision comes from `_get_slider_precision()` (1 for Int Snap, 1000 for Float Snap). `refresh_value` MUST use the same helper or values get clamped to wrong positions.
- **Slider undo**: `sliderPressed` opens an undo chunk, `sliderReleased` closes it, and `_slider_changed` calls `_set_value(..., skip_chunk=True)` so the whole drag is ONE undoable action.
- **`executeDeferred` kwargs**: Some Maya builds forward keyword args (e.g. `lowPriority`) to the deferred callable, causing `unexpected keyword argument`. Wrap callbacks in a guard that accepts `*args, **kwargs` (see `_load_guard`/`_refresh_guard`) rather than passing the target method directly.
- **Dock close ≠ `closeEvent`**: Closing a docked `MayaQWidgetDockableMixin` window does NOT fire `closeEvent`, so its scriptJobs survive. `launch()` must scan `cmds.scriptJob(listJobs=True)` and kill jobs matching the window (see `_kill_stale_jobs`/`_active_jobs`), or stale `Undo`/`Redo` jobs accumulate across reloads.
- **Config save undo**: `lockNode`, lock-state `setAttr`, `addAttr`, and `createNode` are ALL undoable. Disable undo (`undoInfo(stateWithoutFlush=False)`) around the ENTIRE `save_config()` — not just the JSON `setAttr` — or every save injects several blank undo entries (pressing Ctrl+Z many times before a real undo).
- **Deleted Qt widgets**: After a rebuild/reload, row Python objects can outlive their C++ widgets. Guard `refresh_value()` with `shiboken.isValid(widget)` before `property()`/`setValue`, or it raises "Internal C++ object already deleted".
- **Rename focus jump**: Hiding a focused `QLineEdit` hands focus to the next widget in the chain (value editor / delete button). Capture `hasFocus()` before hiding and, if true, redirect focus to the row/group itself (which needs `setFocusPolicy(Qt.ClickFocus)`).
- **Empty-group drop**: An empty `EntryContainer` collapses to ~0 height and cannot receive drops. Show a placeholder widget when a group has no entries to keep it a droppable area.

## Conventions
- No comments unless requested.
- `from __future__ import annotations` in every module.
- PySide6 primary, PySide2 fallback via try/except at top of each UI file.
- Non-slider `cmds.setAttr` wrapped in `undoInfo(openChunk/closeChunk)`; slider drags use the press/release chunk pattern instead.
- `record_set_attr` is called ONLY after a successful `cmds.setAttr` (so failed sets don't poison the Last Attr feature).
- Config saves disable undo (`undoInfo(stateWithoutFlush=False)`) around the WHOLE `save_config()` (including `lockNode`/lock toggles) to keep the undo stack clean; window-level `save()` is debounced 300ms via `QTimer`.
- Data model is single source of truth; UI rebuilds from it.
