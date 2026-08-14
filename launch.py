"""Portable launcher for Attribute Manager.

Usage in Maya Script Editor:
    __file__ = r"C:\opencode\attributeManager_maya\launch.py"; exec(compile(open(__file__).read(), __file__, "exec"))
"""
from __future__ import annotations

import importlib
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

for _mod_name in list(sys.modules.keys()):
    if _mod_name in ("ui", "core") or _mod_name.startswith(("ui.", "core.")):
        _mod = sys.modules[_mod_name]
        _file = getattr(_mod, "__file__", None) or ""
        if "attributeManager_maya" not in _file:
            del sys.modules[_mod_name]

_saved_window = None
if "ui.main_window" in sys.modules:
    _saved_window = getattr(sys.modules["ui.main_window"], "_window", None)

# Remove any previously registered MCommandMessage hook BEFORE reloading the
# module: the old callback survives in the OpenMaya layer and would leak
# (writing into the old module's globals that the reloaded module can't see).
for _mod_name in list(sys.modules.keys()):
    if _mod_name == "core.channel_box":
        try:
            _hook = getattr(sys.modules[_mod_name], "disable_command_hook", None)
            if _hook is not None:
                _hook()
        except Exception:
            pass

for _mod_name in list(sys.modules.keys()):
    if _mod_name.startswith(("ui.", "core.")):
        _mod = sys.modules[_mod_name]
        _file = getattr(_mod, "__file__", None) or ""
        if "attributeManager_maya" in _file:
            importlib.reload(_mod)

if _saved_window is not None and "ui.main_window" in sys.modules:
    sys.modules["ui.main_window"]._window = _saved_window

if _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

try:
    from ui.main_window import launch
    launch(dockable=True)
except Exception as e:
    import traceback
    traceback.print_exc()
    import maya.cmds as cmds
    cmds.warning("Attribute Manager launch failed: {}".format(e))
