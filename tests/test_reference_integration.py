"""End-to-end reference tests: real file -reference / -edit operations
against the live kernel, exercising scene_io.load_config and core.merge.
"""

from __future__ import annotations

import os
import unittest

import maya.cmds as cmds

import support
from core.attr_data import AttrGroup
from core.merge import collect_for_save, merge_for_display
from core.scene_io import load_config, save_config


class ReferenceTestBase(support.MayaTestCase):
    def _make_reference(self, namespace="refNs"):
        ref_path = os.path.join(self.temp_dir(), "ref_%s.ma" % namespace)
        support.make_ref_scene(ref_path)
        cmds.file(ref_path, reference=True, namespace=namespace)
        ref_node = cmds.referenceQuery(
            "|%s:refCube" % namespace, referenceNode=True)
        return ref_node, ref_path


class LoadReferencedConfig(ReferenceTestBase):
    def test_ref_group_gets_namespace_and_referenced_entries(self):
        self._make_reference()
        config = load_config()
        ref_groups = [g for g in config.groups if g.reference_namespace]
        self.assertEqual(len(ref_groups), 1)
        group = ref_groups[0]
        self.assertEqual(group.name, "Ref Group")
        self.assertEqual(group.reference_namespace, "refNs")
        self.assertEqual([e.attr for e in group.entries],
                         ["translateX", "translateY"])
        self.assertTrue(all(e.is_referenced for e in group.entries))

    def test_resolve_maps_uuid_to_namespaced_node(self):
        self._make_reference()
        config = load_config()
        from core.attr_data import resolve_entries
        resolve_entries(config)
        entry = [e for g in config.groups for e in g.entries
                 if e.attr == "translateX"][0]
        self.assertEqual(entry.invalid_reason, "")
        self.assertEqual(entry.node_path, "|refNs:refCube")


class OverrideEndToEnd(ReferenceTestBase):
    def test_override_survives_scene_reopen_in_original_position(self):
        self._make_reference()
        merged = load_config()
        merge_for_display(merged)

        cube_uuid = [e for g in merged.groups for e in g.entries
                     if e.attr == "translateY"][0].node_uuid
        main_group = AttrGroup(name="Main")
        main_group.entries = [
            support.make_entry("translateY", cube_uuid, "translateY")]
        merged.groups.insert(0, main_group)

        self.assertTrue(save_config(collect_for_save(merged)))

        path = os.path.join(self.temp_dir(), "main.ma")
        cmds.file(rename=path)
        cmds.file(save=True, type="mayaAscii")
        cmds.file(new=True, force=True)
        cmds.file(path, open=True, force=True)

        reloaded = load_config()
        merge_for_display(reloaded)
        ref_group = [g for g in reloaded.groups
                     if g.reference_namespace == "refNs"][0]
        overridden = [e for e in ref_group.entries if e.attr == "translateY"][0]
        readonly = [e for e in ref_group.entries if e.attr == "translateX"][0]
        self.assertFalse(overridden.is_referenced)
        self.assertTrue(readonly.is_referenced)


class ReferenceLifecycle(ReferenceTestBase):
    def test_remove_reference_drops_ref_group(self):
        _, ref_path = self._make_reference()
        self.assertTrue([g for g in load_config().groups
                         if g.reference_namespace])
        cmds.file(ref_path, removeReference=True)
        self.assertEqual(
            [g for g in load_config().groups if g.reference_namespace], [])

    def test_unload_reference_hides_ref_data(self):
        _, ref_path = self._make_reference()
        cmds.file(ref_path, unloadReference=True)
        self.assertEqual(
            [g for g in load_config().groups if g.reference_namespace], [])

    def test_namespace_rename_is_picked_up_on_reload(self):
        _, ref_path = self._make_reference(namespace="oldNs")
        cmds.file(ref_path, edit=True, namespace="newNs")
        config = load_config()
        namespaces = sorted(g.reference_namespace for g in config.groups
                            if g.reference_namespace)
        self.assertEqual(namespaces, ["newNs"])

    def test_two_references_stay_independently_tagged(self):
        ref_dir = self.temp_dir()
        support.make_ref_scene(os.path.join(ref_dir, "ref_a.ma"))
        support.make_ref_scene(os.path.join(ref_dir, "ref_b.ma"))
        cmds.file(new=True, force=True)
        cmds.file(os.path.join(ref_dir, "ref_a.ma"),
                  reference=True, namespace="nsA")
        cmds.file(os.path.join(ref_dir, "ref_b.ma"),
                  reference=True, namespace="nsB")

        config = load_config()
        tagged = {g.reference_namespace for g in config.groups
                  if g.reference_namespace}
        self.assertEqual(tagged, {"nsA", "nsB"})
        for group in config.groups:
            if group.reference_namespace:
                self.assertTrue(all(e.is_referenced for e in group.entries))


if __name__ == "__main__":
    unittest.main()
