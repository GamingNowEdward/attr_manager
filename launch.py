"""Portable launcher for Attribute Manager.

Usage in Maya Script Editor:
    exec(open(r"C:\opencode\attributeManager_maya\launch.py").read())
"""
from __future__ import annotations

import importlib
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_SCRIPT_DIR)

if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

_PACKAGE_NAME = "attributeManager_maya"

try:
    package = importlib.import_module(_PACKAGE_NAME)
    importlib.reload(package)
    package.launch()
except Exception as e:
    import traceback
    traceback.print_exc()
    import maya.cmds as cmds
    cmds.warning("Attribute Manager launch failed: {}".format(e))
