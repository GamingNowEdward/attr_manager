# Attribute Manager

A dockable attribute collection panel for Maya 2024/2025. Aggregates frequently used scene attributes into one panel with grouped management, drag-and-drop reordering, and per-scene persistence.

## Features

- Add attributes from Channel Box or manual plug input (auto-searches Shape nodes)
- "+ Last Attr" quick button: auto-fills the plug from the most recently modified attribute (panel edits or Script Editor log)
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
- Performance: 300ms debounced config saves; slider drags collapse into a single undo step

## Usage

Run in Maya Script Editor:

```python
exec(open(r"C:\opencode\attributeManager_maya\launch.py").read())
```

The panel docks to Maya's right side. Each call hot-reloads all modules for development iteration.

## Requirements

- Maya 2024 / 2025 (Python 3 + PySide6)
- Compatible with Maya 2022/2023 (PySide2 fallback)

## Project Structure

```
attributeManager_maya/
├── launch.py              # Portable launcher
├── attributeManager.py    # Entry point
├── __init__.py            # Package re-exports (launch/reload_modules)
├── core/
│   ├── attr_data.py       # Data model + JSON serialisation
│   ├── scene_io.py        # Scene node read/write
│   └── channel_box.py     # Channel Box queries + Last Attr
└── ui/
    ├── main_window.py     # Dockable main window
    ├── group_section.py   # Groups + drag-drop
    ├── attr_row_widget.py # Attribute row controls
    ├── add_attr_dialog.py # Add attribute dialog
    └── styles.py          # QSS stylesheet
```
