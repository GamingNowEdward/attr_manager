"""Shared harness for the mayapy-based Attribute Manager test suite.

Run with Maya 2024's mayapy.exe (see tests/README.md). Every test starts
from a fresh empty scene with an empty undo queue.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
import uuid as uuidlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import maya.standalone

    maya.standalone.initialize(name="python")
    import maya.cmds as cmds  # noqa: E402
except Exception:
    cmds = None

from core.attr_data import AttrEntry, AttrGroup, Config  # noqa: E402


class MayaTestCase(unittest.TestCase):
    """Base class giving each test a fresh scene and a clean undo queue."""

    def setUp(self):
        cmds.file(new=True, force=True)

    def temp_dir(self):
        path = os.path.join(
            tempfile.gettempdir(), "attrman_tests", uuidlib.uuid4().hex[:8]
        )
        os.makedirs(path, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path


def make_entry(display_name, node_uuid, attr, **kw):
    defaults = dict(
        display_name=display_name,
        node_path="|grp|" + display_name,
        node_uuid=node_uuid,
        attr=attr,
    )
    defaults.update(kw)
    return AttrEntry(**defaults)


def make_config(groups=None, version=1, float_precision=False):
    return Config(
        version=version,
        groups=list(groups or []),
        slider_float_precision=float_precision,
    )


def write_config_node(config, name="attrManager"):
    """Create the locked attrManager network node by hand.

    Deliberately independent of core.scene_io so tests never lean on the
    module under test to build their fixtures.
    """
    node = cmds.createNode("network", name=name)
    cmds.addAttr(node, longName="config", dataType="string", hidden=True)
    cmds.setAttr("{}.config".format(node), config.to_json(), type="string")
    cmds.setAttr("{}.config".format(node), lock=True)
    cmds.lockNode(node, lock=True)
    return node


def make_ref_scene(path, group_name="Ref Group"):
    """Build and save a scene holding a cube plus an attrManager config.

    Returns a dict with the cube's name and UUID for later assertions.
    """
    cmds.file(new=True, force=True)
    cube = cmds.polyCube(name="refCube")[0]
    cube_uuid = cmds.ls(cube, uuid=True)[0]
    group = AttrGroup(name=group_name)
    group.entries = [
        make_entry("translateX", cube_uuid, "translateX"),
        make_entry("translateY", cube_uuid, "translateY"),
    ]
    write_config_node(make_config(groups=[group]))
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii")
    cmds.file(new=True, force=True)
    return {"cube": cube, "uuid": cube_uuid}
