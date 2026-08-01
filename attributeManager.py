"""Maya-styled Attribute Manager entry point."""

from __future__ import annotations

import importlib
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def reload_modules():
    """Reload the package during Maya tool development."""
    names = [
        "core.attr_data", "core.scene_io", "core.channel_box",
        "ui.styles", "ui.attr_row_widget", "ui.group_section", "ui.add_attr_dialog", "ui.main_window",
    ]
    for name in names:
        module = importlib.import_module(name)
        importlib.reload(module)


def launch():
    reload_modules()
    from ui.main_window import launch as show_window
    return show_window(dockable=True)


if __name__ == "__main__":
    launch()
