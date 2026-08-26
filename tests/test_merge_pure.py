"""Pure-Python tests for core.merge (no Maya, no Qt).

These operate on core.attr_data objects only. Behaviours are taken from the
implementation in core/merge.py.

If a test fails, judge whether the test assumption or the project behaviour is
wrong before editing the test. In particular ``collect_for_save`` documents
"never mutates config" — a failure of the no-mutation test below is most likely
a real bug in merge.py (main groups are appended by reference and then
renumbered by normalise_orders), and should be fixed in merge.py.
"""

from __future__ import annotations

from core.merge import collect_for_save, entry_key, merge_configs, merge_for_display
from _fixtures import make_config, make_entry, make_group


def _main_config():
    group = make_group(name="Main", entries=[
        make_entry("translateX", "uuid-A", "translateX"),
        make_entry("rotateZ", "uuid-C", "rotateZ"),
    ])
    return make_config(groups=[group])


def _ref_config(namespace="refNs"):
    group = make_group(name="Ref Group", reference_namespace=namespace, entries=[
        make_entry("translateX", "uuid-A", "translateX", is_referenced=True),
        make_entry("translateY", "uuid-B", "translateY", is_referenced=True),
    ])
    return make_config(groups=[group])


def _merged(main_config, ref_config):
    return make_config(groups=main_config.groups + ref_config.groups)


def _snapshot(config):
    return [
        (g.name, g.reference_namespace, g.order,
         tuple((e.attr, e.order, e.is_referenced) for e in g.entries))
        for g in config.groups
    ]


def _sig(config):
    """Structure signature ignoring order (which merge_for_display does NOT
    renumber — only collect_for_save/normalise_orders do)."""
    return [
        (g.name, g.reference_namespace,
         tuple((e.attr, e.is_referenced) for e in g.entries))
        for g in config.groups
    ]


# --------------------------------------------------------------------------
# entry_key
# --------------------------------------------------------------------------
class TestEntryKey:
    def test_uses_uuid(self):
        assert entry_key(make_entry(attr="tx", node_uuid="U", node_path="|a")) == ("U", "tx")

    def test_falls_back_to_path_when_uuid_empty(self):
        assert entry_key(make_entry(attr="tx", node_uuid="", node_path="|a")) == ("|a", "tx")

    def test_uses_path_when_uuid_none(self):
        assert entry_key(make_entry(attr="tx", node_uuid=None, node_path="|a")) == ("|a", "tx")

    def test_includes_attr(self):
        assert entry_key(make_entry(attr="a", node_uuid="U")) != entry_key(make_entry(attr="b", node_uuid="U"))


# --------------------------------------------------------------------------
# merge_for_display
# --------------------------------------------------------------------------
class TestMergeForDisplay:
    def test_override_replaces_ref_entry_in_place(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        assert _sig(merged) == [
            ("Main", None, (("rotateZ", False),)),
            ("Ref Group", "refNs", (("translateX", False), ("translateY", True))),
        ]

    def test_merge_for_display_preserves_orders(self):
        # merge_for_display swaps overrides in place but never renumbers
        # group/entry orders; the override entry keeps its own order.
        cfg = make_config(groups=[
            make_group(name="Main", order=3, entries=[
                make_entry("a", "U1", "a", order=7),
                make_entry("b", "U2", "b", order=2),
            ]),
            make_group(name="Ref", order=9, reference_namespace="ns", entries=[
                make_entry("a", "U1", "a", is_referenced=True, order=4),
            ]),
        ])
        merge_for_display(cfg)
        assert _snapshot(cfg) == [
            ("Main", None, 3, (("b", 2, False),)),
            ("Ref", "ns", 9, (("a", 7, False),)),
        ]

    def test_ref_entry_without_override_stays_readonly(self):
        main = make_config(groups=[make_group(name="Main", entries=[
            make_entry("rotateZ", "uuid-C", "rotateZ")])])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        assert _sig(merged) == [
            ("Main", None, (("rotateZ", False),)),
            ("Ref Group", "refNs", (("translateX", True), ("translateY", True))),
        ]

    def test_empty_ref_group_is_dropped(self):
        ref = make_config(groups=[make_group(name="Empty Ref", reference_namespace="refNs")])
        merged = _merged(_main_config(), ref)
        merge_for_display(merged)
        assert [g.name for g in merged.groups] == ["Main"]

    def test_main_group_fully_overridden_is_hidden(self):
        main = make_config(groups=[make_group(name="Main", entries=[
            make_entry("translateX", "uuid-A", "translateX")])])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        assert [g.name for g in merged.groups] == ["Ref Group"]

    def test_empty_main_group_stays_visible(self):
        main = make_config(groups=[make_group(name="Main")])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        assert [g.name for g in merged.groups] == ["Main", "Ref Group"]

    def test_duplicate_override_keys_first_wins_second_dropped(self):
        main = make_config(groups=[make_group(name="Main", entries=[
            make_entry("translateX", "uuid-A", "translateX"),
            make_entry("translateX dup", "uuid-A", "translateX"),
        ])])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        assert _sig(merged) == [
            ("Ref Group", "refNs", (("translateX", False), ("translateY", True))),
        ]

    def test_same_key_in_two_ref_groups_both_get_override(self):
        ref = make_config(groups=[
            make_group(name="R1", reference_namespace="ns1", entries=[
                make_entry("translateX", "uuid-A", "translateX", is_referenced=True)]),
            make_group(name="R2", reference_namespace="ns2", entries=[
                make_entry("translateX", "uuid-A", "translateX", is_referenced=True)]),
        ])
        main = make_config(groups=[make_group(name="Main", entries=[
            make_entry("translateX", "uuid-A", "translateX")])])
        merged = _merged(main, ref)
        merge_for_display(merged)
        names = [g.name for g in merged.groups]
        assert names == ["R1", "R2"]
        for g in merged.groups:
            assert g.entries[0].is_referenced is False

    def test_mutates_input_in_place_and_returns_it(self):
        merged = _merged(_main_config(), _ref_config())
        result = merge_for_display(merged)
        assert result is merged
        # the ref group object has been rewritten
        assert merged.groups[-1].entries[0].is_referenced is False


# --------------------------------------------------------------------------
# collect_for_save
# --------------------------------------------------------------------------
class TestCollectForSave:
    def test_collect_gathers_main_groups_and_override_store_groups(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert [g.name for g in saved.groups] == ["Main", "Ref Group"]
        main_group, store_group = saved.groups
        assert main_group.reference_namespace is None
        assert [e.attr for e in main_group.entries] == ["rotateZ"]
        assert store_group.reference_namespace is None
        assert store_group.collapsed is False
        assert [(e.node_uuid, e.attr, e.is_referenced) for e in store_group.entries] == [
            ("uuid-A", "translateX", False)]

    def test_collect_without_overrides_emits_no_store_group(self):
        main = make_config(groups=[make_group(name="Main", entries=[
            make_entry("rotateZ", "uuid-C", "rotateZ")])])
        merged = _merged(main, _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert [g.name for g in saved.groups] == ["Main"]
        assert [e.attr for e in saved.groups[0].entries] == ["rotateZ"]

    def test_collect_normalises_orders_contiguously(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert [g.order for g in saved.groups] == [0, 1]
        for group in saved.groups:
            assert [e.order for e in group.entries] == list(range(len(group.entries)))

    def test_collect_preserves_version_and_float_precision(self):
        merged = _merged(_main_config(), _ref_config())
        merged.version = 3
        merged.slider_float_precision = True
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert saved.version == 3
        assert saved.slider_float_precision is True

    def test_ref_group_all_readonly_contributes_nothing(self):
        ref = make_config(groups=[make_group(name="Ref", reference_namespace="ns", entries=[
            make_entry("translateX", "uuid-A", "translateX", is_referenced=True)])])
        main = make_config(groups=[make_group(name="Main")])
        merged = _merged(main, ref)
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert [g.name for g in saved.groups] == ["Main"]

    def test_ref_group_mixed_entries_collects_only_overrides(self):
        ref = make_config(groups=[make_group(name="Ref", reference_namespace="ns", entries=[
            make_entry("translateX", "uuid-A", "translateX", is_referenced=True),
            make_entry("override", "uuid-B", "translateY", is_referenced=False),
        ])])
        main = make_config(groups=[make_group(name="Main")])
        merged = _merged(main, ref)
        merge_for_display(merged)
        saved = collect_for_save(merged)
        store = saved.groups[-1]
        assert store.name == "Ref"
        assert [e.attr for e in store.entries] == ["translateY"]

    def test_returns_a_new_config_object(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        assert saved is not merged

    def test_does_not_mutate_input(self):
        cfg = make_config(groups=[
            make_group(name="Main", order=0, entries=[
                make_entry("a", "U1", "a", order=2),
                make_entry("b", "U2", "b", order=0),
                make_entry("c", "U3", "c", order=1),
            ]),
            make_group(name="Ref", order=1, reference_namespace="ns", entries=[
                make_entry("ro", "U9", "ro", is_referenced=True, order=0),
                make_entry("ov", "U8", "ov", is_referenced=False, order=4),
            ]),
        ])
        before = _snapshot(cfg)
        collect_for_save(cfg)
        after = _snapshot(cfg)
        assert after == before

    def test_result_is_deep_independent_from_input(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        saved = collect_for_save(merged)
        saved.groups[0].entries[0].attr = "MUTATED"
        saved.groups[1].entries[0].attr = "MUTATED2"
        assert merged.groups[0].entries[0].attr != "MUTATED"
        assert merged.groups[1].entries[0].attr != "MUTATED2"


# --------------------------------------------------------------------------
# Override round trip (display -> save -> re-display)
# --------------------------------------------------------------------------
class TestOverrideRoundTrip:
    def test_override_survives_save_reload_cycle(self):
        merged = _merged(_main_config(), _ref_config())
        merge_for_display(merged)
        display_before = _snapshot(merged)

        saved = collect_for_save(merged)
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)

        assert _snapshot(reloaded) == display_before
        ref_group = reloaded.groups[-1]
        assert ref_group.reference_namespace == "refNs"
        assert ref_group.entries[0].is_referenced is False
        assert ref_group.entries[0].attr == "translateX"

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
        assert [g.name for g in saved.groups] == ["Main"]
        assert [e.attr for e in saved.groups[0].entries] == ["rotateZ"]

        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)
        assert _sig(reloaded) == [
            ("Main", None, (("rotateZ", False),)),
            ("Ref Group", "refNs", (("translateX", True), ("translateY", True))),
        ]

    def test_multiple_overrides_and_groups_round_trip(self):
        main = _main_config()
        ref = _ref_config()
        main.groups.append(make_group(name="Second", entries=[
            make_entry("translateY", "uuid-B", "translateY")]))
        merged = _merged(main, ref)
        merge_for_display(merged)
        display_before = _sig(merged)

        saved = collect_for_save(merged)
        reloaded = _merged(saved, _ref_config())
        merge_for_display(reloaded)
        assert _sig(reloaded) == display_before


# --------------------------------------------------------------------------
# merge_configs
# --------------------------------------------------------------------------
class TestMergeConfigs:
    def _config(self, group_name="Main", entries=(), collapsed=True):
        group = make_group(name=group_name, entries=list(entries), collapsed=collapsed)
        return make_config(groups=[group])

    def test_differently_named_groups_are_appended_whole(self):
        base = self._config()
        extra = self._config("Extra", [make_entry("tx", "uuid-X", "translateX")])
        merged = merge_configs(base, extra)
        assert [g.name for g in merged.groups] == ["Main", "Extra"]
        assert [e.attr for e in merged.groups[1].entries] == ["translateX"]

    def test_same_name_group_merges_entries_with_dedup(self):
        base = self._config(entries=[make_entry("tx", "uuid-A", "translateX")])
        extra = self._config(entries=[
            make_entry("tx dup", "uuid-A", "translateX"),
            make_entry("ty", "uuid-B", "translateY"),
        ])
        merged = merge_configs(base, extra)
        assert [g.name for g in merged.groups] == ["Main"]
        assert [e.attr for e in merged.groups[0].entries] == ["translateX", "translateY"]

    def test_base_collapsed_state_wins(self):
        base = self._config(entries=[make_entry("tx", "uuid-A", "translateX")])
        extra = make_config(groups=[make_group(name="Main", collapsed=False, entries=[
            make_entry("ty", "uuid-B", "translateY")])])
        merged = merge_configs(base, extra)
        assert merged.groups[0].collapsed is True

    def test_inputs_are_not_mutated(self):
        base = self._config(entries=[make_entry("tx", "uuid-A", "translateX")])
        extra = self._config("Extra", [make_entry("rz", "uuid-Z", "rotateZ")])
        base_before = _snapshot(base)
        extra_before = _snapshot(extra)
        merge_configs(base, extra)
        assert _snapshot(base) == base_before
        assert _snapshot(extra) == extra_before

    def test_orders_are_normalised_after_merge(self):
        base = make_config(groups=[make_group(name="B", order=5)])
        extra = make_config(groups=[make_group(name="A", order=1)])
        merged = merge_configs(base, extra)
        assert [g.name for g in merged.groups] == ["A", "B"]
        assert [g.order for g in merged.groups] == [0, 1]

    def test_returns_new_object(self):
        base = self._config()
        extra = self._config("Extra")
        merged = merge_configs(base, extra)
        assert merged is not base
        assert merged is not extra

    def test_result_is_deep_independent_from_inputs(self):
        base = self._config(entries=[make_entry("tx", "uuid-A", "translateX")])
        extra = self._config("Extra", [make_entry("rz", "uuid-Z", "rotateZ")])
        merged = merge_configs(base, extra)
        merged.groups[0].entries[0].attr = "MUTATED"
        assert base.groups[0].entries[0].attr == "translateX"
