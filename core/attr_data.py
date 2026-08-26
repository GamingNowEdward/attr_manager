"""Data objects used by Attribute Manager.

This module deliberately has no Maya dependency until ``resolve_entries`` is
called, which makes the serialisation layer safe to import in tooling/tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AttrEntry:
    display_name: str
    node_path: str
    node_uuid: str
    attr: str
    order: int = 0
    invalid_reason: str = ""
    control_mode: str = "spin"
    custom_min: Optional[float] = None
    custom_max: Optional[float] = None
    display_type: str = "auto"
    is_referenced: bool = False

    def to_dict(self) -> dict:
        data = {
            "display_name": self.display_name,
            "node_path": self.node_path,
            "node_uuid": self.node_uuid,
            "attr": self.attr,
            "order": self.order,
            "control_mode": self.control_mode,
            "display_type": self.display_type,
        }
        if self.custom_min is not None:
            data["custom_min"] = self.custom_min
        if self.custom_max is not None:
            data["custom_max"] = self.custom_max
        return data

    @classmethod
    def from_dict(cls, value: dict) -> "AttrEntry":
        return cls(
            display_name=str(value.get("display_name", "")),
            node_path=str(value.get("node_path", value.get("node", ""))),
            node_uuid=str(value.get("node_uuid", "")),
            attr=str(value.get("attr", "")),
            order=int(value.get("order", 0)),
            control_mode=str(value.get("control_mode", "spin")),
            custom_min=value.get("custom_min"),
            custom_max=value.get("custom_max"),
            display_type=str(value.get("display_type", "auto")),
            is_referenced=False,
        )


@dataclass
class AttrGroup:
    name: str
    order: int = 0
    collapsed: bool = False
    entries: List[AttrEntry] = field(default_factory=list)
    reference_namespace: Optional[str] = None

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "order": self.order,
            "collapsed": self.collapsed,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        if self.reference_namespace is not None:
            data["reference_namespace"] = self.reference_namespace
        return data

    @classmethod
    def from_dict(cls, value: dict) -> "AttrGroup":
        return cls(
            name=str(value.get("name", "Group")),
            order=int(value.get("order", 0)),
            collapsed=bool(value.get("collapsed", False)),
            entries=[AttrEntry.from_dict(item) for item in value.get("entries", [])],
            reference_namespace=value.get("reference_namespace"),
        )


@dataclass
class Config:
    version: int = 1
    groups: List[AttrGroup] = field(default_factory=list)
    slider_float_precision: bool = False

    def to_dict(self) -> dict:
        self.normalise_orders()
        data = {"version": self.version, "groups": [group.to_dict() for group in self.groups]}
        if self.slider_float_precision:
            data["slider_float_precision"] = True
        return data

    @classmethod
    def from_dict(cls, value: dict) -> "Config":
        config = cls(
            version=int(value.get("version", 1)),
            groups=[AttrGroup.from_dict(item) for item in value.get("groups", [])],
            slider_float_precision=bool(value.get("slider_float_precision", False)),
        )
        config.normalise_orders()
        return config

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> Optional["Config"]:
        if not raw:
            return None
        try:
            value = json.loads(raw)
            return cls.from_dict(value) if isinstance(value, dict) else None
        except Exception:
            return None

    def normalise_orders(self) -> None:
        self.groups.sort(key=lambda group: group.order)
        for group_index, group in enumerate(self.groups):
            group.order = group_index
            group.entries.sort(key=lambda entry: entry.order)
            for entry_index, entry in enumerate(group.entries):
                entry.order = entry_index


def _find_by_uuid(cmds, node_uuid: str) -> Optional[str]:
    if not node_uuid:
        return None
    try:
        matches = cmds.ls(node_uuid, long=True) or []
        return matches[0] if matches else None
    except Exception:
        return None


def resolve_entries(config: Config) -> None:
    """Refresh node paths and record why entries cannot currently be edited."""
    import maya.cmds as cmds

    for group in config.groups:
        for entry in group.entries:
            entry.invalid_reason = ""
            node = _find_by_uuid(cmds, entry.node_uuid)
            if not node and entry.node_path and cmds.objExists(entry.node_path):
                node = entry.node_path
            if not node:
                entry.invalid_reason = "Node not found"
                continue
            try:
                entry.node_path = (cmds.ls(node, long=True) or [node])[0]
                entry.node_uuid = (cmds.ls(node, uuid=True) or [""])[0]
            except Exception:
                pass
            if not cmds.attributeQuery(entry.attr, node=node, exists=True):
                entry.invalid_reason = "Attribute not found"
                continue
            plug = "{}.{}".format(node, entry.attr)
            try:
                if cmds.getAttr(plug, lock=True):
                    entry.invalid_reason = "Attribute is locked"
                    continue
                if cmds.listConnections(plug, source=True, destination=False):
                    entry.invalid_reason = "Attribute has an input connection"
            except Exception as exc:
                entry.invalid_reason = "Cannot read attribute: {}".format(exc)

