"""scene_io integration tests against the live Maya kernel: persistence,
locking contract, undo footprint, corrupt-data tolerance and node creation.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

import maya.cmds as cmds

import support
from core.attr_data import AttrGroup, Config, resolve_entries
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


def _network_names():
    return [n.split("|")[-1] for n in cmds.ls(type="network", long=True)]


class MainNodeConvergence(support.MayaTestCase):
    def test_extra_empty_node_removed_on_save(self):
        support.write_config_node(_simple_config())
        support.write_config_node(Config(), name="attrManager1")
        save_config(_simple_config())
        self.assertEqual([n for n in _network_names() if n.startswith("attrManager")],
                         ["attrManager"])

    def test_extra_node_without_config_attr_removed_on_save(self):
        support.write_config_node(_simple_config())
        cmds.createNode("network", name="attrManager1")
        save_config(_simple_config())
        self.assertEqual([n for n in _network_names() if n.startswith("attrManager")],
                         ["attrManager"])

    def test_extra_nonempty_node_merged_and_removed(self):
        support.write_config_node(_simple_config())
        extra_group = AttrGroup(name="Extra")
        extra_group.entries = [_cube_entry("rotateZ")]
        support.write_config_node(
            support.make_config(groups=[extra_group]), name="attrManager1")

        save_config(_simple_config())

        self.assertEqual([n for n in _network_names() if n.startswith("attrManager")],
                         ["attrManager"])
        data = json.loads(cmds.getAttr("attrManager.config"))
        self.assertEqual([g["name"] for g in data["groups"]], ["Main", "Extra"])
        self.assertEqual([e["attr"] for e in data["groups"][1]["entries"]],
                         ["rotateZ"])

    def test_same_name_group_merged_with_entry_dedup(self):
        cube = cmds.polyCube(name="ioCube")[0]
        cube_uuid = cmds.ls(cube, uuid=True)[0]
        group = AttrGroup(name="Main")
        group.entries = [support.make_entry("tx", cube_uuid, "translateX")]
        support.write_config_node(support.make_config(groups=[group]))

        dup_group = AttrGroup(name="Main")
        dup_group.entries = [
            support.make_entry("tx dup", cube_uuid, "translateX"),
            support.make_entry("ty", cube_uuid, "translateY"),
        ]
        support.write_config_node(
            support.make_config(groups=[dup_group]), name="attrManager1")

        save_config(support.make_config(groups=[group]))

        data = json.loads(cmds.getAttr("attrManager.config"))
        self.assertEqual([e["attr"] for e in data["groups"][0]["entries"]],
                         ["translateX", "translateY"])

    def test_locked_extra_node_removed(self):
        support.write_config_node(_simple_config())
        support.write_config_node(Config(), name="attrManager1")
        self.assertTrue(
            cmds.lockNode("attrManager1", query=True, lock=True)[0])
        save_config(_simple_config())
        self.assertEqual([n for n in _network_names() if n.startswith("attrManager")],
                         ["attrManager"])

    def test_converged_config_survives_roundtrip(self):
        primary_group = AttrGroup(name="Main")
        primary_group.entries = [_cube_entry("translateX")]
        primary = support.make_config(groups=[primary_group])
        extra_group = AttrGroup(name="Extra")
        extra_group.entries = [_cube_entry("rotateZ")]
        support.write_config_node(primary)
        support.write_config_node(
            support.make_config(groups=[extra_group]), name="attrManager1")

        save_config(primary)

        expected = support.make_config(groups=[primary_group, extra_group])
        expected.normalise_orders()
        resolve_entries(expected)
        self.assertEqual(load_config(), expected)

    def test_convergence_adds_no_undo_entries(self):
        config = _simple_config()
        support.write_config_node(config)
        support.write_config_node(Config(), name="attrManager1")
        cmds.flushUndo()
        save_config(config)
        count = 0
        while True:
            try:
                cmds.undo()
                count += 1
            except RuntimeError:
                break
        self.assertEqual(count, 0)

    def test_load_reads_primary_and_warns(self):
        extra_group = AttrGroup(name="Other")
        support.write_config_node(_simple_config())
        support.write_config_node(
            support.make_config(groups=[extra_group]), name="attrManager1")
        with mock.patch("maya.cmds.warning") as warn:
            loaded = load_config()
        warn.assert_called_once()
        self.assertEqual([g.name for g in loaded.groups], ["Main"])

    def test_reference_nodes_untouched_by_convergence(self):
        ref_path = os.path.join(self.temp_dir(), "ref.ma")
        support.make_ref_scene(ref_path)
        cmds.file(ref_path, reference=True, namespace="refNs")
        support.write_config_node(_simple_config())
        support.write_config_node(Config(), name="attrManager1")

        save_config(_simple_config())

        names = _network_names()
        self.assertIn("attrManager", names)
        self.assertIn("refNs:attrManager", names)
        self.assertNotIn("attrManager1", names)


if __name__ == "__main__":
    unittest.main()
