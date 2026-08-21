"""Attribute Manager — single entry point.

Usage in Maya Script Editor:
    __file__ = r"C:\\opencode\\attributeManager_maya\\launch.py"; __name__ = "__main__"; exec(compile(open(__file__).read(), __file__, "exec"))
"""

from __future__ import annotations

import importlib
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _purge_foreign_modules():
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("ui", "core") or mod_name.startswith(("ui.", "core.")):
            module = sys.modules[mod_name]
            file = getattr(module, "__file__", None) or ""
            if "attributeManager_maya" not in file:
                del sys.modules[mod_name]


def _disable_stale_callbacks():
    """Disable previously registered OpenMaya callbacks BEFORE reloading.

    Old callbacks survive in the OpenMaya layer and would leak (writing
    into the old module's globals that the reloaded module can't see).
    Covers the MCommandMessage hook (core.channel_box) and the
    MSceneMessage reference/import callbacks (ui.main_window).
    """
    for mod_name, disabler_name in (
        ("core.channel_box", "disable_command_hook"),
        ("ui.main_window", "_disable_scene_message_callbacks"),
    ):
        module = sys.modules.get(mod_name)
        if module is None:
            continue
        disabler = getattr(module, disabler_name, None)
        try:
            if disabler is not None:
                disabler()
        except Exception:
            pass


def reload_modules():
    """Reload every ui./core. module belonging to this project."""
    for mod_name in list(sys.modules.keys()):
        if not mod_name.startswith(("ui.", "core.")):
            continue
        module = sys.modules[mod_name]
        file = getattr(module, "__file__", None) or ""
        if "attributeManager_maya" in file:
            importlib.reload(module)


def launch(dockable=True):
    _purge_foreign_modules()

    main_window = sys.modules.get("ui.main_window")
    saved_window = None
    if main_window is not None:
        saved_window = getattr(main_window, "_window", None)

    _disable_stale_callbacks()
    reload_modules()

    if saved_window is not None and "ui.main_window" in sys.modules:
        sys.modules["ui.main_window"]._window = saved_window

    if SCRIPT_DIR in sys.path:
        sys.path.remove(SCRIPT_DIR)
    sys.path.insert(0, SCRIPT_DIR)

    try:
        from ui.main_window import launch as show_window
        return show_window(dockable=dockable)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        try:
            import maya.cmds as cmds
            cmds.warning("Attribute Manager launch failed: {}".format(exc))
        except Exception:
            pass
        return None


if __name__ == "__main__":
    launch()
