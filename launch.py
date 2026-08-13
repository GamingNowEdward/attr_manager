"""Portable launcher for Attribute Manager.

Usage in Maya Script Editor:
    __file__ = r"C:\opencode\attributeManager_maya\launch.py"; exec(compile(open(__file__).read(), __file__, "exec"))
"""
from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

for _mod_name in list(sys.modules.keys()):
    if _mod_name in ("ui", "core") or _mod_name.startswith(("ui.", "core.")):
        _mod = sys.modules[_mod_name]
        _file = getattr(_mod, "__file__", None) or ""
        if "attributeManager_maya" not in _file:
            del sys.modules[_mod_name]

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
