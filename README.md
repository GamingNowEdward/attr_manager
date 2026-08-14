# Attribute Manager

A dockable attribute collection panel for Maya 2024/2025. Aggregates frequently used scene attributes into one panel with grouped management, drag-and-drop reordering, and per-scene persistence.

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
- Reference support: referenced scenes' `attrManager` configs display read-only (grouped, italic rows, drag/drop blocked); editing a referenced attribute creates an **in-place override** — the row stays in its original group, gains an `override` badge, and can be removed with the × button to restore the read-only entry. The panel re-reads configs automatically when references are created/loaded/unloaded and when files are imported
- Main-scene entries pointing at referenced nodes (e.g. Translate Z added manually) also show the `override` badge
- Performance: 300ms debounced config saves; slider drags collapse into a single undo step

## Testing

Pure-Python unit tests covering the data model, JSON serialisation and the merge/collect round trips (no Maya or PySide6 required):

```bash
python -m unittest discover -s tests
```

## Quick Start

1. Download and extract the repository
2. Double-click `copy_to_clipboard.bat` — the launch command is copied to clipboard
3. Paste into Maya Script Editor and run

## Usage

Or manually run in Maya Script Editor:

```python
__file__ = r"PATH_TO\launch.py"; exec(compile(open(__file__).read(), __file__, "exec"))
```

> **Note**: If downloaded as ZIP from GitHub, the folder will be named `attr_manager-main`. Adjust the path accordingly.

The panel docks to Maya's right side. Each call hot-reloads all modules for development iteration.

## Requirements

- Maya 2024 / 2025 (Python 3 + PySide6)
- Compatible with Maya 2022/2023 (PySide2 fallback)

## Project Structure

```
attributeManager_maya/
├── copy_to_clipboard.bat  # Auto-generate launch command
├── launch.py              # Portable launcher
├── attributeManager.py    # Entry point
├── __init__.py            # Package re-exports (launch/reload_modules)
├── core/
│   ├── attr_data.py       # Data model + JSON serialisation
│   ├── merge.py           # Display/persist merge transforms (pure Python)
│   ├── scene_io.py        # Scene node read/write
│   └── channel_box.py     # Channel Box queries + Last Lock Attr hook
├── tests/
│   ├── test_attr_data.py      # Serialisation round-trip tests
│   └── test_merge_roundtrip.py # Merge/collect round-trip tests
└── ui/
    ├── main_window.py     # Dockable main window
    ├── group_section.py   # Groups + drag-drop
    ├── attr_row_widget.py # Attribute row controls
    ├── add_attr_dialog.py # Add attribute dialog
    └── styles.py          # QSS stylesheet
```
