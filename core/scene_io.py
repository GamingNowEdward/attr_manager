"""Read and write Attribute Manager configuration in the Maya scene."""

from __future__ import annotations

import maya.cmds as cmds

from .attr_data import Config, resolve_entries

NODE_NAME = "attrManager"
ATTR_NAME = "config"


def _config_nodes():
    exact = cmds.ls(NODE_NAME, type="network", long=True) or []
    if exact:
        return exact
    return cmds.ls("{}*".format(NODE_NAME), type="network", long=True) or []


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
    existing = _config_nodes()
    if existing and _referenced(existing[0]):
        cmds.warning("Attribute Manager: configuration node is referenced and cannot be saved.")
        return False
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
        cmds.setAttr(plug, config.to_json(), type="string")
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
    nodes = _config_nodes()
    if not nodes or not cmds.attributeQuery(ATTR_NAME, node=nodes[0], exists=True):
        return Config()
    try:
        config = Config.from_json(cmds.getAttr("{}.{}".format(nodes[0], ATTR_NAME))) or Config()
    except Exception:
        return Config()
    resolve_entries(config)
    return config
