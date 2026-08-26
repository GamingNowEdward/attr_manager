# Attribute Manager

A dockable attribute collection panel for Maya 2024.2. Aggregates frequently used scene attributes into one panel with grouped management, drag-and-drop reordering, and per-scene persistence.

> 中文文档见 [README_zh.md](README_zh.md)。

## Features

- Add attributes from Channel Box or manual plug input (auto-searches Shape nodes)
- "+ Last Lock Attr" quick button: fills the plug from the most recent "Lock" gesture — right-click an attribute in the Attribute Editor and choose **Lock** to record it (a global command hook captures the `setAttr -lock` command, no Script Editor needed). The attribute stays locked, and is unlocked automatically when actually added through the Add dialog (real lock intentions are never hijacked)
- Auto-matched controls by type: Slider+SpinBox / CheckBox / ComboBox / Color swatch
- Display type override: Auto / Number / Color; color attributes open Maya's color editor
- Custom slider range: right-click the slider → Set Min/Max/Range/Reset (default range wraps the current value)
- Global Int/Float Snap toggle: integer steps vs float steps (3 decimal places)
- Group management: collapse, rename (double-click), drag reorder
- Entry management: drag reorder, cross-group drag, double-click rename; empty groups show a placeholder and remain a valid drop target
- Full undo support: attribute edits (including slider drags) are undoable; config saves never pollute the undo stack
- Undo/redo sync: panel values auto-refresh after Ctrl+Z / Ctrl+Shift+Z
- Config persistence: stored on a locked `attrManager` network node in the scene
- UUID-based node resolution survives renames and reparenting
- Reference support: referenced scenes' `attrManager` configs display read-only (grouped, `namespace:`-prefixed names, italic rows, drag/drop and rename blocked); editing a referenced attribute creates an **in-place override** — the row stays in its original group, gains an `override` badge, and can be removed with the × button to restore the read-only entry. The panel re-reads configs automatically when references are created/loaded/unloaded/removed and when files are imported; renaming a reference's namespace fires no event, so use the toolbar Refresh button to re-read and correct the prefixes
- Main-scene entries pointing at referenced nodes (e.g. Translate Z added manually) also show the `override` badge

## Performance

- Config saves are 300ms debounced; slider drags collapse into a single undo step
- Reference namespace detection: creating/loading/unloading/removing a reference and importing files re-read the config automatically via MSceneMessage events. Renaming a reference's namespace in the Reference Editor fires no Maya event at all (`MNamespaceMessage` does not exist in either Python API and `NameChanged` is not triggered), so use the toolbar Refresh button to re-read the scene config (pending saves are flushed first, then the config is reloaded and prefixes/ref groups correct themselves)
- No background polling: the panel performs no periodic queries, so playback and interaction incur zero extra overhead

## Testing

The suite is split into two halves:

- **Pure-Python (no Maya)** — `tests/test_attr_data_pure.py` and `tests/test_merge_pure.py`, run with `pytest` under any system Python. CI runs this automatically (GitHub Actions, Python 3.13, aligned with Maya 2027).

  ```bash
  python -m pytest -v
  ```

- **mayapy (Maya required)** — drives the live kernel (scene I/O, references, command hooks). Run locally with Maya's `mayapy.exe`:

  ```bash
  mayapy -m unittest discover -s tests/mayapy -t tests -v
  ```

Coverage table and headless gotchas: see `tests/README.md`.

## Quick Start

1. Download and extract the repository
2. Double-click `copy_to_clipboard.bat` — the launch command is copied to clipboard
3. Paste into Maya Script Editor and run

## Usage

Or manually run in Maya Script Editor:

```python
__file__ = r"PATH_TO\launch.py"; __name__ = "__main__"; exec(compile(open(__file__).read(), __file__, "exec"))
```

> **Note**: If downloaded as ZIP from GitHub, the folder will be named `attr_manager-main`. Adjust the path accordingly.

The panel docks to Maya's right side. Each call hot-reloads all modules for development iteration. After restarting Maya, the panel automatically restores to its previous dock position (via the workspace control's uiScript mechanism).

## Requirements

- Maya 2024.2 (Python 3; UI layer supports PySide6 or PySide2 — it falls back to PySide2 automatically)
- **Tested on Maya 2024.2 only. Other Maya versions are not tested — please test them yourself.**

## Project Structure

```
attributeManager_maya/
├── copy_to_clipboard.bat  # Auto-generate launch command
├── launch.py              # Single entry point (hot-reload + launch)
├── __init__.py            # Package re-exports (launch/reload_modules)
├── core/
│   ├── attr_data.py       # Data model + JSON serialisation
│   ├── merge.py           # Display/persist/convergence merge transforms (pure Python)
│   ├── scene_io.py        # Scene node read/write
│   └── channel_box.py     # Channel Box queries + Last Lock Attr hook
├── tests/
│   ├── pytest.ini                     # testpaths=tests, ignores tests/mayapy
│   ├── conftest.py                   # pytest bootstrap (sys.path)
│   ├── _fixtures.py                  # pure-Python data factories (no Maya)
│   ├── test_attr_data_pure.py        # core.attr_data: data model + serialisation
│   ├── test_merge_pure.py            # core.merge: merge_for_display / collect_for_save / merge_configs
│   ├── support.py                    # shared mayapy harness (import-safe)
│   └── mayapy/                       # MAYA-DEPENDENT tests (local only, not in CI)
│       ├── test_attr_data.py         # Serialisation + resolve_entries (real nodes)
│       ├── test_scene_io.py          # Persistence / locks / undo footprint
│       ├── test_channel_box.py       # setAttr parsing + command hook
│       └── test_reference_integration.py # Reference lifecycle end-to-end
└── ui/
    ├── main_window.py     # Dockable main window
    ├── group_section.py   # Groups + drag-drop
    ├── attr_row_widget.py # Attribute row controls
    ├── add_attr_dialog.py # Add attribute dialog
    └── styles.py          # QSS stylesheet
```
