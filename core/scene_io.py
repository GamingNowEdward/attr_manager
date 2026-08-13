"""Read and write Attribute Manager configuration in the Maya scene."""

from __future__ import annotations

from typing import Optional

import maya.cmds as cmds

from .attr_data import AttrGroup, Config, resolve_entries

NODE_NAME = "attrManager"
ATTR_NAME = "config"


def _short_name(node: str) -> str:
    return node.split("|")[-1].split(":")[-1]


def _config_nodes():
    all_network = cmds.ls(type="network", long=True) or []
    return [n for n in all_network
            if NODE_NAME in _short_name(n) and not _referenced(n)]


def _config_nodes_all():
    all_network = cmds.ls(type="network", long=True) or []
    return [n for n in all_network if NODE_NAME in _short_name(n)]


def _get_namespace(node: str) -> Optional[str]:
    name = node.split("|")[-1]
    if ":" in name:
        return name.rsplit(":", 1)[0]
    return None


def _load_from_node(node: str) -> Config:
    if not cmds.attributeQuery(ATTR_NAME, node=node, exists=True):
        return Config()
    try:
        raw = cmds.getAttr("{}.{}".format(node, ATTR_NAME))
        return Config.from_json(raw) or Config()
    except Exception:
        return Config()


def _any_node():
    return cmds.ls(NODE_NAME) or []


def get_or_create_node() -> str:
    nodes = _config_nodes()
    if nodes:
        node = nodes[0]
    elif _any_node():
        existing = _any_node()[0]
        cmds.warning(
            "Attribute Manager: '{}' exists but is not a network node ({}); "
            "creating a new config node.".format(NODE_NAME, cmds.nodeType(existing))
        )
        node = cmds.createNode("network", name=NODE_NAME)
    else:
        node = cmds.createNode("network", name=NODE_NAME)
    locked = _node_locked(node)
    if locked:
        cmds.lockNode(node, lock=False)
    try:
        if not cmds.attributeQuery(ATTR_NAME, node=node, exists=True):
            cmds.addAttr(node, longName=ATTR_NAME, dataType="string", hidden=True)
        # Keep it out of normal scene views without locking its attrs.
        cmds.setAttr("{}.isHistoricallyInteresting".format(node), 0)
    finally:
        # The config node is always left locked; only this module unlocks it.
        cmds.lockNode(node, lock=True)
    return node


def _node_locked(node: str) -> bool:
    try:
        value = cmds.lockNode(node, query=True, lock=True)
        return bool(value[0] if isinstance(value, (list, tuple)) else value)
    except Exception:
        return False


def _referenced(node: str) -> bool:
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def save_config(config: Config) -> bool:
    """Persist config without adding bookkeeping changes to the undo queue."""
    filtered_groups = []
    for group in config.groups:
        if group.reference_namespace is not None:
            continue
        filtered_entries = [e for e in group.entries if not e.is_referenced]
        filtered_groups.append(AttrGroup(
            name=group.name,
            order=group.order,
            collapsed=group.collapsed,
            entries=filtered_entries,
            reference_namespace=None,
        ))

    filtered_config = Config(
        version=config.version,
        slider_float_precision=config.slider_float_precision,
        groups=filtered_groups,
    )

    undo_enabled = cmds.undoInfo(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    node = None
    plug = None
    was_locked = False
    node_was_locked = False
    try:
        node = get_or_create_node()
        plug = "{}.{}".format(node, ATTR_NAME)
        was_locked = cmds.getAttr(plug, lock=True)
        node_was_locked = _node_locked(node)
        if node_was_locked:
            cmds.lockNode(node, lock=False)
        if was_locked:
            cmds.setAttr(plug, lock=False)
        cmds.setAttr(plug, filtered_config.to_json(), type="string")
        return True
    except Exception as exc:
        cmds.warning("Attribute Manager: could not save configuration: {}".format(exc))
        return False
    finally:
        try:
            if node is not None:
                if was_locked:
                    cmds.setAttr(plug, lock=True)
                cmds.lockNode(node, lock=True)
        except Exception:
            pass
        cmds.undoInfo(stateWithoutFlush=undo_enabled)


def load_config() -> Config:
    all_nodes = _config_nodes_all()
    if not all_nodes:
        return Config()

    main_config = Config()
    ref_configs = []

    for node in all_nodes:
        node_config = _load_from_node(node)
        is_ref = _referenced(node)

        if is_ref:
            namespace = _get_namespace(node)
            for group in node_config.groups:
                group.reference_namespace = namespace
                for entry in group.entries:
                    entry.is_referenced = True
            ref_configs.append(node_config)
        else:
            main_config = node_config

    for ref_config in ref_configs:
        main_config.groups.extend(ref_config.groups)

    resolve_entries(main_config)
    return main_config
