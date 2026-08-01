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
- Entry management: drag reorder, cross-group drag, double-click rename
- Config persistence: stored on a locked `attrManager` network node in the scene
- UUID-based node resolution survives renames and reparenting
- Performance: 300ms debounced config saves; slider drags collapse into a single undo step

## Installation

Add the **parent directory** of `attributeManager/` to Maya's Python path:

**Option 1: Maya.env (recommended)**
```
MAYA_SCRIPT_PATH += C:/opencode
```
Location: `~/Documents/maya/2024/Maya.env`

**Option 2: Manual**
```python
import sys
sys.path.insert(0, r"C:\opencode")
```

## Usage

```python
import attributeManager
attributeManager.launch()
```

The panel docks to Maya's right side. `launch()` hot-reloads all modules on each call.

## Requirements

- Maya 2024 / 2025 (Python 3 + PySide6)
- Compatible with Maya 2022/2023 (PySide2 fallback)

## Project Structure

```
attributeManager/
├── attributeManager.py      # Entry point
├── __init__.py              # Package re-exports (launch/reload_modules)
├── core/
│   ├── attr_data.py         # Data model + JSON serialisation
│   ├── scene_io.py          # Scene node read/write
│   └── channel_box.py       # Channel Box queries + Last Attr
└── ui/
    ├── main_window.py       # Dockable main window
    ├── group_section.py     # Groups + drag-drop
    ├── attr_row_widget.py   # Attribute row controls
    ├── add_attr_dialog.py   # Add attribute dialog
    └── styles.py            # QSS stylesheet
```
