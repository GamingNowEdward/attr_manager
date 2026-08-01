"""Small wrappers around Maya's Channel Box queries."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

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


def record_set_attr(node: str, attr: str):
    global _last_set_attr
    _last_set_attr = (node, attr)


def _parse_set_attr_line(line: str) -> Optional[Tuple[str, str]]:
    """Extract (node, attr) from a MEL setAttr echo line, or None."""
    match = re.search(
        r'setAttr\s+"?([a-zA-Z0-9_:|]+\.[a-zA-Z0-9_]+)"?\s*(?:-type\s+\w+\s+)?[-0-9\.]*', line
    )
    if not match:
        return None
    plug = match.group(1)
    node, attr = plug.rsplit(".", 1)
    return node, attr


def get_last_set_attr() -> Optional[Tuple[str, str]]:
    global _last_set_attr
    if _last_set_attr:
        result = _last_set_attr
        _last_set_attr = None
        return result
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
