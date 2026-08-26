"""Behaviour matrix for core.merge: merge_for_display / collect_for_save.

Inputs are hand-built data (fast); the real load_config path that produces
these structures end-to-end is covered in test_reference_integration.
"""

from __future__ import annotations

import unittest

import support
from core.attr_data import AttrGroup, Config
from core.merge import collect_for_save, entry_key, merge_configs, merge_for_display


def _main_config():
    group = AttrGroup(name="Main")
    group.entries = [
        support.make_entry("translateX", "uuid-A", "translateX"),
        support.make_entry("rotateZ", "uuid-C", "rotateZ"),
    ]
    return Config(groups=[group])


def _ref_config(namespace="refNs"):
    group = AttrGroup(name="Ref Group")
    group.reference_namespace = namespace
    group.entries = [
        support.make_entry("translateX", "uuid-A", "translateX", is_referenced=True),
        support.make_entry("translateY", "uuid-B", "translateY", is_referenced=True),
    ]
    return Config(groups=[group])


def _merged(main_config, ref_config):
    """Simulate scene_io.load_config: main groups first, then referenced groups."""
    return Config(groups=main_config.groups + ref_config.groups)


def _snapshot(config):
    config.normalise_orders()
    return [
        (g.name, g.reference_namespace,
         [(e.display_name, e.node_uuid, e.attr, e.is_referenced, e.order)
          for e in g.entries])
        for g in config.groups
    ]


class MergeDisplay(unittest.TestCase):
    def test_override_replaces_ref_entry_in_place(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        self.assertEqual(
            _snapshot(merged),
            [
                ("Main", None, [("rotateZ", "uuid-C", "rotateZ", False, 0)]),
                ("Ref Group", "refNs",
                 [("translateX", "uuid-A", "translateX", False, 0),
                  ("translateY", "uuid-B", "translateY", True, 1)]),
            ],
        )

    def test_ref_entry_without_override_stays_readonly(self):
        main = Config(groups=[AttrGroup(name="Main")])
        main.groups[0].entries = [support.make_entry("rotateZ", "uuid-C", "rotateZ")]
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        self.assertEqual(
            _snapshot(merged),
            [
                ("Main", None, [("rotateZ", "uuid-C", "rotateZ", False, 0)]),
                ("Ref Group", "refNs",
                 [("translateX", "uuid-A", "translateX", True, 0),
                  ("translateY", "uuid-B", "translateY", True, 1)]),
            ],
        )

    def test_empty_ref_group_is_not_displayed(self):
        ref = Config(groups=[AttrGroup(name="Empty Ref", reference_namespace="refNs")])
        merged = _merged(_main_config(), ref)
        merge_for_display(merged)
        self.assertEqual([g.name for g in merged.groups], ["Main"])

    def test_main_group_fully_overridden_is_hidden(self):
        main = Config(groups=[AttrGroup(name="Main")])
        main.groups[0].entries = [support.make_entry("translateX", "uuid-A", "translateX")]
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        self.assertEqual([g.name for g in merged.groups], ["Ref Group"])

    def test_empty_main_group_stays_visible(self):
        main = Config(groups=[AttrGroup(name="Main")])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        self.assertEqual([g.name for g in merged.groups], ["Main", "Ref Group"])

    def test_duplicate_override_keys_first_wins_second_dropped(self):
        main = Config(groups=[AttrGroup(name="Main")])
        main.groups[0].entries = [
            support.make_entry("translateX", "uuid-A", "translateX"),
            support.make_entry("translateX dup", "uuid-A", "translateX"),
        ]
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        self.assertEqual(
            _snapshot(merged),
            [
                ("Ref Group", "refNs",
                 [("translateX", "uuid-A", "translateX", False, 0),
                  ("translateY", "uuid-B", "translateY", True, 1)]),
            ],
        )


class CollectForSave(unittest.TestCase):
    def test_collect_gathers_main_groups_and_override_store_groups(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        self.assertEqual([g.name for g in saved.groups], ["Main", "Ref Group"])
        main_group, store_group = saved.groups
        self.assertIsNone(main_group.reference_namespace)
        self.assertEqual([e.attr for e in main_group.entries], ["rotateZ"])
        self.assertIsNone(store_group.reference_namespace)
        self.assertEqual(store_group.collapsed, False)
        self.assertEqual([(e.node_uuid, e.attr, e.is_referenced) for e in store_group.entries],
                         [("uuid-A", "translateX", False)])

    def test_collect_without_overrides_emits_no_store_group(self):
        main = Config(groups=[AttrGroup(name="Main")])
        main.groups[0].entries = [support.make_entry("rotateZ", "uuid-C", "rotateZ")]
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        self.assertEqual([g.name for g in saved.groups], ["Main"])
        self.assertEqual([e.attr for e in saved.groups[0].entries], ["rotateZ"])

    def test_collect_normalises_orders_contiguously(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        self.assertEqual([g.order for g in saved.groups], [0, 1])
        for group in saved.groups:
            self.assertEqual([e.order for e in group.entries], list(range(len(group.entries))))

    def test_collect_preserves_version_and_float_precision(self):
        merged = _merged(_main_config(), _ref_config())
        merged.version = 3
        merged.slider_float_precision = True
        merge_for_display(merged)
        saved = collect_for_save(merged)
        self.assertEqual(saved.version, 3)
        self.assertTrue(saved.slider_float_precision)

    def test_collect_does_not_mutate_display_config(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        before = _snapshot(merged)
        collect_for_save(merged)
        self.assertEqual(_snapshot(merged), before)


class OverrideRoundTrip(unittest.TestCase):
    def test_override_survives_save_reload_cycle(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        display_before = _snapshot(merged)

        saved = collect_for_save(merged)
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)

        self.assertEqual(_snapshot(reloaded), display_before)
        ref_group = reloaded.groups[-1]
        self.assertEqual(ref_group.reference_namespace, "refNs")
        self.assertEqual(ref_group.entries[0].is_referenced, False)
        self.assertEqual(ref_group.entries[0].attr, "translateX")

    def test_remove_override_restores_readonly_ref_entry(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)

        key = ("uuid-A", "translateX")
        for group in merged.groups:
            group.entries = [
                e for e in group.entries
                if (group.reference_namespace is not None and e.is_referenced)
                or entry_key(e) != key
            ]

        saved = collect_for_save(merged)
        self.assertEqual([g.name for g in saved.groups], ["Main"])
        self.assertEqual([e.attr for e in saved.groups[0].entries], ["rotateZ"])

        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)
        self.assertEqual(
            _snapshot(reloaded),
            [
                ("Main", None, [("rotateZ", "uuid-C", "rotateZ", False, 0)]),
                ("Ref Group", "refNs",
                 [("translateX", "uuid-A", "translateX", True, 0),
                  ("translateY", "uuid-B", "translateY", True, 1)]),
            ],
        )

    def test_multiple_overrides_and_groups_round_trip(self):
        main = _main_config()
        ref = _ref_config()
        main.groups.append(AttrGroup(name="Second"))
        main.groups[1].entries = [support.make_entry("translateY", "uuid-B", "translateY")]
        merged = _merged(main, ref)
        merge_for_display(merged)
        display_before = _snapshot(merged)

        saved = collect_for_save(merged)
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)
        self.assertEqual(_snapshot(reloaded), display_before)


class MergeConfigs(unittest.TestCase):
    def _config(self, group_name="Main", entries=()):
        group = AttrGroup(name=group_name, collapsed=True)
        group.entries = list(entries)
        return Config(groups=[group])

    def test_differently_named_groups_are_appended_whole(self):
        base = self._config()
        extra = self._config("Extra", [
            support.make_entry("tx", "uuid-X", "translateX"),
        ])
        merged = merge_configs(base, extra)
        self.assertEqual([g.name for g in merged.groups], ["Main", "Extra"])
        self.assertEqual([e.attr for e in merged.groups[1].entries], ["translateX"])

    def test_same_name_group_merges_entries_with_dedup(self):
        base = self._config(entries=[
            support.make_entry("tx", "uuid-A", "translateX"),
        ])
        extra = self._config(entries=[
            support.make_entry("tx dup", "uuid-A", "translateX"),
            support.make_entry("ty", "uuid-B", "translateY"),
        ])
        merged = merge_configs(base, extra)
        self.assertEqual([g.name for g in merged.groups], ["Main"])
        self.assertEqual(
            [e.attr for e in merged.groups[0].entries], ["translateX", "translateY"])

    def test_base_collapsed_state_wins(self):
        base = self._config(entries=[
            support.make_entry("tx", "uuid-A", "translateX"),
        ])
        extra = Config(groups=[AttrGroup(name="Main", collapsed=False, entries=[
            support.make_entry("ty", "uuid-B", "translateY"),
        ])])
        merged = merge_configs(base, extra)
        self.assertTrue(merged.groups[0].collapsed)

    def test_inputs_are_not_mutated(self):
        base = self._config(entries=[
            support.make_entry("tx", "uuid-A", "translateX"),
        ])
        extra = self._config("Extra", [
            support.make_entry("rz", "uuid-Z", "rotateZ"),
        ])
        base_before = _snapshot(base)
        extra_before = _snapshot(extra)
        merge_configs(base, extra)
        self.assertEqual(_snapshot(base), base_before)
        self.assertEqual(_snapshot(extra), extra_before)

    def test_orders_are_normalised_after_merge(self):
        base = Config(groups=[AttrGroup(name="B", order=5)])
        extra = Config(groups=[AttrGroup(name="A", order=1)])
        merged = merge_configs(base, extra)
        self.assertEqual([g.name for g in merged.groups], ["A", "B"])
        self.assertEqual([g.order for g in merged.groups], [0, 1])


if __name__ == "__main__":
    unittest.main()
