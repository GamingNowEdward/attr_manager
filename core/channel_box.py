"""Small wrappers around Maya's Channel Box queries."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel


def get_channelbox_selection() -> Tuple[List[str], List[str]]:
    """Return selected objects and Channel Box attributes, or empty lists."""
    try:
        main_attrs = mel.eval("channelBox -query -selectedMainAttributes mainChannelBox") or []
    except Exception:
        main_attrs = []
    try:
        shape_attrs = mel.eval("channelBox -query -selectedShapeAttributes mainChannelBox") or []
    except Exception:
        shape_attrs = []
    attributes = list(main_attrs) + [a for a in shape_attrs if a not in main_attrs]
    nodes = cmds.ls(selection=True, long=True) or []
    return list(nodes), attributes


def get_selected_objects() -> List[str]:
    return cmds.ls(selection=True, long=True) or []


_last_set_attr = None
_command_callback = None
_hook_enabled = False


def record_set_attr(node: str, attr: str):
    global _last_set_attr
    if not _hook_enabled:
        return
    _last_set_attr = (node, attr)


def unlock_attr(node: str, attr: str) -> bool:
    """Unlock an attribute plug; returns True on success (or if not locked)."""
    try:
        if not cmds.getAttr("{}.{}".format(node, attr), lock=True):
            return True
        cmds.setAttr("{}.{}".format(node, attr), lock=False)
        return True
    except Exception:
        return False


def _on_command(command_string, client_data=None):
    """Record setAttr commands issued through the MEL/command system.

    ``MCommandMessage.addCommandCallback`` fires for commands executed via
    the MEL channel (MEL scripts, Attribute Editor right-click actions such
    as Lock, which echoes ``setAttr "-l" 1 {"node.attr"};``) but NOT for
    Python ``cmds`` calls, so panel edits still rely on ``record_set_attr``.
    A right-click Lock is recorded for "+ Last Attr" but left locked — it is
    only unlocked when the attribute is actually added via the Add dialog.
    """
    if not _hook_enabled:
        return
    try:
        if not command_string.startswith("setAttr"):
            return
        result = _parse_set_attr_line(command_string)
        if not result:
            return
        record_set_attr(result[0], result[1])
    except Exception:
        pass


def enable_command_hook():
    global _command_callback, _hook_enabled
    _hook_enabled = True
    if _command_callback is None:
        _command_callback = om2.MCommandMessage.addCommandCallback(_on_command)


def disable_command_hook():
    global _command_callback, _hook_enabled
    _hook_enabled = False
    if _command_callback is not None:
        try:
            om2.MMessage.removeCallback(_command_callback)
        except Exception:
            pass
        _command_callback = None


def _parse_set_attr_line(line: str) -> Optional[Tuple[str, str]]:
    """Extract (node, attr) from a MEL setAttr echo line, or None.

    Maya echoes ``setAttr`` with ``-type`` either before the plug
    (``setAttr -type double3 "pCube1.color" 1 2 3;``) or after it, and the
    Attribute Editor right-click "Lock" echoes the plug wrapped in braces
    (``setAttr "-l" 1 {"polyCube10.d"};``), so the plug is located by token
    scan rather than a fixed-position regex.
    """
    tokens = re.findall(r'"[^"]*"|\S+', line.strip())
    if not tokens or tokens[0] != "setAttr":
        return None
    for token in tokens[1:]:
        stripped = token.strip('";{}')
        if not stripped or stripped.startswith("-"):
            continue
        if "." in stripped and not stripped.startswith(".") and not stripped.endswith("."):
            node, attr = stripped.rsplit(".", 1)
            return node, attr
    return None


def get_last_set_attr() -> Optional[Tuple[str, str]]:
    global _last_set_attr
    if _last_set_attr:
        return _last_set_attr
    try:
        history = mel.eval("scrollField -q -text $gCommandReporter;")
        if not history:
            return None
    except Exception:
        return None
    for line in reversed(history.strip().split("\n")):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        result = _parse_set_attr_line(line)
        if result:
            return result
    return None
