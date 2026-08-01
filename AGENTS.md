# Attribute Manager — Agent Guide

## What This Is
A dockable Maya 2024/2025 panel (Python 3 + PySide6) that aggregates scene attributes into grouped, draggable, editable rows. Config persists inside the scene file on a locked `network` node named `attrManager`.

## Running
No build step. In Maya Script Editor:
```python
import sys; sys.path.insert(0, r"<parent_dir_of_attributeManager>")
import attributeManager; attributeManager.launch()
```
`launch()` hot-reloads all modules automatically.

## Architecture
- `attributeManager.py` — entry point, module reload, `__init__.py` re-exports `launch`/`reload_modules` from it.
- `core/attr_data.py` — pure dataclasses (AttrEntry, AttrGroup, Config) + JSON serialisation. No Maya imports except `resolve_entries()`. `Config.slider_float_precision` is a global Int/Float Snap flag.
- `core/scene_io.py` — reads/writes config JSON to a locked `network` node (`attrManager.config`). Config writes bypass undo. `get_or_create_node()` handles a same-named non-network node by warning + creating `attrManager1`; `_config_nodes()` falls back to prefix matching.
- `core/channel_box.py` — queries Channel Box selected attributes (main + shape); also holds `record_set_attr`/`get_last_set_attr` for the "+ Last Attr" feature (reads panel-recorded plug first, then parses MEL `$gCommandReporter` history via `_parse_set_attr_line`).
- `ui/main_window.py` — `MayaQWidgetDockableMixin` + `QMainWindow`. Contains `GroupContainer` (group-level drop target) and `move_group`/`move_entry` logic. `save()` is 300ms-debounced via a single-shot `QTimer`; toolbar has Int/Float Snap toggle. `launch()` cleans up lingering scriptJobs before rebuilding the window.
- `ui/group_section.py` — collapsible group with `EntryContainer` (entry-level drop target, blue indicator line). `GroupDragHandle` distinguishes click (collapse) vs drag (reorder) by 8px threshold.
- `ui/attr_row_widget.py` — per-attribute row: DragHandle, name (double-click rename), type-matched editor. Numeric rows: SpinBox + Slider; slider right-click opens Set Min/Max/Range/Reset menu (`RangeDialog`); slider drags are wrapped in ONE undo chunk via `sliderPressed/Released` + `_set_value(..., skip_chunk=True)`. `ColorButton` opens `cmds.colorEditor`. `display_type` (auto/number/color) can override auto-detection.
- `ui/add_attr_dialog.py` — non-modal dialog; Channel Box or manual plug input; searches transform + shapes via `_find_attr_owner`. Has Display type (Auto/Number/Color) radio group and a "+ Last Attr" button that fills the plug from the last modified attribute.
- `ui/styles.py` — global QSS (dark theme, #232323 bg, #00AFFF accent).

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

## Conventions
- No comments unless requested.
- `from __future__ import annotations` in every module.
- PySide6 primary, PySide2 fallback via try/except at top of each UI file.
- Non-slider `cmds.setAttr` wrapped in `undoInfo(openChunk/closeChunk)`; slider drags use the press/release chunk pattern instead.
- `record_set_attr` is called ONLY after a successful `cmds.setAttr` (so failed sets don't poison the Last Attr feature).
- Config saves use `undoInfo(stateWithoutFlush=False)` to avoid polluting undo stack; window-level `save()` is debounced 300ms via `QTimer`.
- Data model is single source of truth; UI rebuilds from it.
