"""Round-trip tests for merge_for_display / collect_for_save (pure Python, no Maya).

These cover the full override lifecycle the panel relies on:
load (merge main + referenced configs) -> display -> edit (create override)
-> save (collect) -> reload -> display again. The display structure must
survive the round trip: overrides stay in their referenced group's original
position, keep their non-referenced identity, and never drift or vanish.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.attr_data import AttrEntry, AttrGroup, Config
from core.merge import collect_for_save, entry_key, merge_for_display


def _entry(display_name, uuid, attr, **kw):
    defaults = dict(
        display_name=display_name,
        node_path="|refNs:grp|" + display_name,
        node_uuid=uuid,
        attr=attr,
    )
    defaults.update(kw)
    return AttrEntry(**defaults)


def _main_config():
    group = AttrGroup(name="Main")
    group.entries = [
        _entry("translateX", "uuid-A", "translateX"),
        _entry("rotateZ", "uuid-C", "rotateZ"),
    ]
    return Config(groups=[group])


def _ref_config(namespace="refNs"):
    group = AttrGroup(name="Ref Group")
    group.reference_namespace = namespace
    group.entries = [
        _entry("translateX", "uuid-A", "translateX", is_referenced=True),
        _entry("translateY", "uuid-B", "translateY", is_referenced=True),
    ]
    return Config(groups=[group])


def _merged(main_config, ref_config):
    """Simulate scene_io.load_config: main groups first, then referenced groups."""
    return Config(groups=main_config.groups + ref_config.groups)


def _snapshot(config):
    """Display state as comparable tuples (order normalised like the panel rebuild)."""
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
        main.groups[0].entries = [_entry("rotateZ", "uuid-C", "rotateZ")]
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
        main.groups[0].entries = [_entry("translateX", "uuid-A", "translateX")]
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
            _entry("translateX", "uuid-A", "translateX"),
            _entry("translateX dup", "uuid-A", "translateX"),
        ]
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        # Current behaviour: the second same-key main entry is filtered out of
        # the main group while only the first replaces the ref entry.
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
        main.groups[0].entries = [_entry("rotateZ", "uuid-C", "rotateZ")]
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
        # Reload: the saved config becomes the new main config; the reference
        # scene re-supplies fresh read-only entries (new objects, untouched).
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)

        self.assertEqual(_snapshot(reloaded), display_before)
        # The override is displayed in the ref group, not as a standalone store group.
        ref_group = reloaded.groups[-1]
        self.assertEqual(ref_group.reference_namespace, "refNs")
        self.assertEqual(ref_group.entries[0].is_referenced, False)
        self.assertEqual(ref_group.entries[0].attr, "translateX")

    def test_remove_override_restores_readonly_ref_entry(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)

        # Simulate AttrManagerWindow.remove_override_entry.
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
        main.groups[1].entries = [_entry("translateY", "uuid-B", "translateY")]
        merged = _merged(main, ref)
        merge_for_display(merged)
        display_before = _snapshot(merged)

        saved = collect_for_save(merged)
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)
        self.assertEqual(_snapshot(reloaded), display_before)


if __name__ == "__main__":
    unittest.main()
