"""scene_io integration tests against the live Maya kernel: persistence,
locking contract, undo footprint, corrupt-data tolerance and node creation.
"""

from __future__ import annotations

import json
import os
import unittest

import maya.cmds as cmds

import support
from core.attr_data import AttrGroup, resolve_entries
from core.scene_io import (
    get_or_create_node,
    load_config,
    save_config,
)


def _cube_entry(attr="translateX"):
    cube = cmds.polyCube(name="ioCube")[0]
    return support.make_entry(attr, cmds.ls(cube, uuid=True)[0], attr)


def _simple_config():
    group = AttrGroup(name="Main")
    group.entries = [_cube_entry()]
    return support.make_config(groups=[group], version=2, float_precision=True)


class LoadEmptyScene(support.MayaTestCase):
    def test_load_without_config_node_returns_empty(self):
        loaded = load_config()
        self.assertEqual(loaded.groups, [])
        self.assertEqual(loaded.version, 1)


class SaveLoadRoundTrip(support.MayaTestCase):
    def test_roundtrip_preserves_config(self):
        config = _simple_config()
        self.assertTrue(save_config(config))
        resolve_entries(config)
        self.assertEqual(load_config(), config)

    def test_persists_across_file_save_and_reopen(self):
        path = os.path.join(self.temp_dir(), "main.ma")
        config = _simple_config()
        save_config(config)
        cmds.file(rename=path)
        cmds.file(save=True, type="mayaAscii")

        cmds.file(new=True, force=True)
        self.assertEqual(load_config().groups, [])

        cmds.file(path, open=True, force=True)
        resolve_entries(config)
        self.assertEqual(load_config(), config)


class LockingContract(support.MayaTestCase):
    def test_config_node_locked_after_save(self):
        save_config(_simple_config())
        self.assertTrue(cmds.lockNode("attrManager", query=True, lock=True)[0])

    def test_plug_lock_state_survives_save_unchanged(self):
        save_config(_simple_config())
        self.assertFalse(cmds.getAttr("attrManager.config", lock=True))

        cmds.lockNode("attrManager", lock=False)
        cmds.setAttr("attrManager.config", lock=True)
        save_config(_simple_config())
        self.assertTrue(cmds.getAttr("attrManager.config", lock=True))


class UndoFootprint(support.MayaTestCase):
    def test_save_adds_no_undo_entries(self):
        baseline = cmds.undoInfo(query=True, length=True)
        save_config(_simple_config())
        self.assertEqual(cmds.undoInfo(query=True, length=True), baseline)


class GetOrCreateNode(support.MayaTestCase):
    def test_creates_network_node_when_absent(self):
        node = get_or_create_node()
        self.assertEqual(node, "attrManager")
        self.assertEqual(cmds.nodeType(node), "network")
        self.assertTrue(
            cmds.attributeQuery("config", node=node, exists=True))

    def test_reuses_existing_config_node(self):
        first = get_or_create_node()
        self.assertEqual(get_or_create_node(), first)

    def test_non_network_namesake_falls_back_to_attr_manager1(self):
        cmds.polyCube(name="attrManager")
        node = get_or_create_node()
        self.assertEqual(node, "attrManager1")
        self.assertEqual(cmds.nodeType(node), "network")


class CorruptDataTolerance(support.MayaTestCase):
    def test_corrupt_json_loads_as_empty_config(self):
        node = cmds.createNode("network", name="attrManager")
        cmds.addAttr(node, longName="config", dataType="string", hidden=True)
        cmds.setAttr(node + ".config", "{not valid json", type="string")
        loaded = load_config()
        self.assertEqual(loaded.groups, [])


class SaveFiltering(support.MayaTestCase):
    def test_reference_groups_and_flagged_entries_not_persisted(self):
        group = AttrGroup(name="Main")
        kept = _cube_entry("translateX")
        dropped = support.make_entry(
            "ty", kept.node_uuid, "translateY", is_referenced=True)
        group.entries = [kept, dropped]
        ref_group = AttrGroup(
            name="Ref", reference_namespace="refNs",
            entries=[support.make_entry("rz", kept.node_uuid, "rotateZ")])

        self.assertTrue(save_config(support.make_config(groups=[group, ref_group])))

        data = json.loads(cmds.getAttr("attrManager.config"))
        self.assertEqual([g["name"] for g in data["groups"]], ["Main"])
        self.assertEqual([e["attr"] for e in data["groups"][0]["entries"]],
                         ["translateX"])
        for group_data in data["groups"]:
            self.assertNotIn("reference_namespace", group_data)


if __name__ == "__main__":
    unittest.main()
