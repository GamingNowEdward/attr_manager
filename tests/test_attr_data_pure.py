"""Pure-Python tests for core.attr_data (no Maya).

Covers the data model and serialisation layer. ``resolve_entries`` is the only
Maya-touching function and is deliberately out of scope here (see
tests/mayapy/test_attr_data.py).

If a test here fails, first judge whether the *test assumption* is wrong or the
*project behaviour* is wrong before changing the test — several of these encode
documented invariants (e.g. the serialisation boundary for ``is_referenced``).
"""

from __future__ import annotations

import json

import pytest

from core.attr_data import AttrEntry, AttrGroup, Config
from _fixtures import make_config, make_entry, make_group


# --------------------------------------------------------------------------
# AttrEntry.to_dict
# --------------------------------------------------------------------------
class TestAttrEntryToDict:
    def test_emits_core_fields(self):
        entry = make_entry(display_name="Tx", node_uuid="U1", attr="translateX")
        data = entry.to_dict()
        assert data == {
            "display_name": "Tx",
            "node_path": "|group|Tx",
            "node_uuid": "U1",
            "attr": "translateX",
            "order": 0,
            "control_mode": "spin",
            "display_type": "auto",
        }

    def test_omits_custom_min_max_when_none(self):
        data = make_entry().to_dict()
        assert "custom_min" not in data
        assert "custom_max" not in data

    def test_emits_custom_min_max_when_set_including_zero(self):
        data = make_entry(custom_min=0.0, custom_max=-5.0).to_dict()
        assert data["custom_min"] == 0.0
        assert data["custom_max"] == -5.0

    def test_never_emits_is_referenced(self):
        data = make_entry(is_referenced=True).to_dict()
        assert "is_referenced" not in data

    def test_never_emits_invalid_reason(self):
        entry = make_entry()
        entry.invalid_reason = "Node not found"
        assert "invalid_reason" not in entry.to_dict()


# --------------------------------------------------------------------------
# AttrEntry.from_dict
# --------------------------------------------------------------------------
class TestAttrEntryFromDict:
    def test_defaults(self):
        entry = AttrEntry.from_dict({})
        assert entry.display_name == ""
        assert entry.node_path == ""
        assert entry.node_uuid == ""
        assert entry.attr == ""
        assert entry.order == 0
        assert entry.control_mode == "spin"
        assert entry.display_type == "auto"
        assert entry.custom_min is None
        assert entry.custom_max is None
        assert entry.is_referenced is False
        assert entry.invalid_reason == ""

    def test_control_mode_and_display_type_defaults(self):
        entry = AttrEntry.from_dict({"display_name": "X", "node_uuid": "U", "attr": "a"})
        assert entry.control_mode == "spin"
        assert entry.display_type == "auto"

    def test_order_coerced_to_int(self):
        assert AttrEntry.from_dict({"order": "3"}).order == 3
        assert AttrEntry.from_dict({"order": 3.9}).order == 3

    def test_legacy_node_key_maps_to_node_path(self):
        entry = AttrEntry.from_dict(
            {"display_name": "Tx", "node": "|pCube1", "attr": "translateX"}
        )
        assert entry.node_path == "|pCube1"

    def test_explicit_node_path_takes_precedence_over_legacy_node(self):
        entry = AttrEntry.from_dict(
            {"node_path": "|a", "node": "|b", "attr": "x"}
        )
        assert entry.node_path == "|a"

    def test_custom_min_max_zero_preserved(self):
        entry = AttrEntry.from_dict(
            {"custom_min": 0.0, "custom_max": 0.0, "attr": "x"}
        )
        assert entry.custom_min == 0.0
        assert entry.custom_max == 0.0

    def test_custom_min_max_none_when_absent(self):
        entry = AttrEntry.from_dict({"attr": "x"})
        assert entry.custom_min is None
        assert entry.custom_max is None

    def test_is_referenced_always_reset_to_false(self):
        entry = AttrEntry.from_dict({"attr": "x", "is_referenced": True})
        assert entry.is_referenced is False

    def test_invalid_reason_never_read(self):
        entry = AttrEntry.from_dict({"attr": "x", "invalid_reason": "broken"})
        assert entry.invalid_reason == ""


# --------------------------------------------------------------------------
# AttrGroup.to_dict / from_dict
# --------------------------------------------------------------------------
class TestAttrGroupSerialisation:
    def test_to_dict_omits_reference_namespace_when_none(self):
        data = make_group(name="G").to_dict()
        assert "reference_namespace" not in data
        assert data["name"] == "G"
        assert data["order"] == 0
        assert data["collapsed"] is False
        assert data["entries"] == []

    def test_to_dict_emits_reference_namespace_when_set(self):
        data = make_group(name="RG", reference_namespace="refNs").to_dict()
        assert data["reference_namespace"] == "refNs"

    def test_to_dict_always_emits_collapsed(self):
        assert make_group(collapsed=True).to_dict()["collapsed"] is True
        assert make_group(collapsed=False).to_dict()["collapsed"] is False

    def test_from_dict_defaults(self):
        group = AttrGroup.from_dict({})
        assert group.name == "Group"
        assert group.order == 0
        assert group.collapsed is False
        assert group.entries == []
        assert group.reference_namespace is None

    def test_from_dict_passthrough_reference_namespace(self):
        assert AttrGroup.from_dict({"name": "G", "reference_namespace": "ns"}).reference_namespace == "ns"
        assert AttrGroup.from_dict({"name": "G"}).reference_namespace is None

    def test_from_dict_collapsed_bool(self):
        assert AttrGroup.from_dict({"collapsed": True}).collapsed is True
        assert AttrGroup.from_dict({"collapsed": 0}).collapsed is False
        assert AttrGroup.from_dict({"collapsed": 1}).collapsed is True

    def test_from_dict_builds_entries(self):
        group = AttrGroup.from_dict({
            "name": "G",
            "entries": [{"display_name": "Tx", "node_uuid": "U", "attr": "translateX"}],
        })
        assert len(group.entries) == 1
        assert group.entries[0].attr == "translateX"


# --------------------------------------------------------------------------
# Serialisation boundary invariants (documented in AGENTS.md)
# --------------------------------------------------------------------------
class TestSerialisationBoundary:
    def test_is_referenced_never_survives_round_trip(self):
        entry = make_entry(is_referenced=True)
        restored = AttrEntry.from_dict(entry.to_dict())
        assert restored.is_referenced is False

    def test_invalid_reason_never_survives_round_trip(self):
        entry = make_entry()
        entry.invalid_reason = "Node not found"
        restored = AttrEntry.from_dict(entry.to_dict())
        assert restored.invalid_reason == ""

    def test_group_reference_namespace_survives_round_trip(self):
        group = make_group(name="RG", reference_namespace="refNs",
                           entries=[make_entry()])
        restored = AttrGroup.from_dict(group.to_dict())
        assert restored.reference_namespace == "refNs"


# --------------------------------------------------------------------------
# Config.to_dict (with documented normalise_orders side effect)
# --------------------------------------------------------------------------
class TestConfigToDict:
    def test_omits_slider_float_precision_when_false(self):
        data = make_config().to_dict()
        assert "slider_float_precision" not in data

    def test_emits_slider_float_precision_when_true(self):
        data = make_config(slider_float_precision=True).to_dict()
        assert data["slider_float_precision"] is True

    def test_calls_normalise_orders_as_side_effect(self):
        cfg = make_config(groups=[
            make_group(name="B", order=5, entries=[
                make_entry(display_name="x", order=2),
                make_entry(display_name="y", order=0),
            ]),
            make_group(name="A", order=1, entries=[make_entry(display_name="z", order=0)]),
        ])
        cfg.to_dict()
        # groups re-sorted by order
        assert [g.name for g in cfg.groups] == ["A", "B"]
        assert [g.order for g in cfg.groups] == [0, 1]
        # B's entries re-sorted by order, renumbered
        assert [e.display_name for e in cfg.groups[1].entries] == ["y", "x"]
        assert [e.order for e in cfg.groups[1].entries] == [0, 1]
        assert [e.order for e in cfg.groups[0].entries] == [0]


# --------------------------------------------------------------------------
# Config.from_dict
# --------------------------------------------------------------------------
class TestConfigFromDict:
    def test_defaults(self):
        cfg = Config.from_dict({})
        assert cfg.version == 1
        assert cfg.groups == []
        assert cfg.slider_float_precision is False

    def test_reads_version_and_precision(self):
        cfg = Config.from_dict({
            "version": 4,
            "slider_float_precision": True,
            "groups": [],
        })
        assert cfg.version == 4
        assert cfg.slider_float_precision is True

    def test_normalises_orders(self):
        cfg = Config.from_dict({
            "groups": [
                {"name": "B", "order": 9, "entries": [{"attr": "a", "order": 3}]},
                {"name": "A", "order": 2, "entries": []},
            ]
        })
        assert [g.name for g in cfg.groups] == ["A", "B"]
        assert [g.order for g in cfg.groups] == [0, 1]
        assert cfg.groups[1].entries[0].order == 0


# --------------------------------------------------------------------------
# Config JSON round trip
# --------------------------------------------------------------------------
class TestConfigJsonRoundTrip:
    def test_round_trip_equals_for_normalised_clean_config(self):
        cfg = make_config(
            groups=[
                make_group(name="Main", entries=[
                    make_entry(display_name="Tx", node_uuid="U1", attr="translateX",
                               custom_min=-10.0, custom_max=10.0),
                    make_entry(display_name="Vis", node_uuid="U2", attr="visibility",
                               control_mode="check"),
                ]),
                make_group(name="Ref", order=1, reference_namespace="refNs", entries=[
                    make_entry(display_name="Ry", node_uuid="U3", attr="rotateY", order=0),
                ]),
            ],
            slider_float_precision=True,
        )
        restored = Config.from_json(cfg.to_json())
        assert restored == cfg

    def test_is_referenced_lost_on_round_trip_changes_equality(self):
        cfg = make_config(groups=[
            make_group(name="Ref", reference_namespace="ns", entries=[
                make_entry(is_referenced=True),
            ]),
        ])
        restored = Config.from_json(cfg.to_json())
        assert restored != cfg
        assert restored.groups[0].entries[0].is_referenced is False

    def test_invalid_reason_lost_on_round_trip_changes_equality(self):
        cfg = make_config(groups=[make_group(entries=[make_entry()])])
        cfg.groups[0].entries[0].invalid_reason = "Attribute is locked"
        restored = Config.from_json(cfg.to_json())
        assert restored != cfg

    def test_to_json_is_compact(self):
        cfg = make_config(version=2, groups=[make_group(name="G")])
        assert '{"version":2' in cfg.to_json()
        assert ": " not in cfg.to_json()


# --------------------------------------------------------------------------
# Config.from_json error handling
# --------------------------------------------------------------------------
class TestConfigFromJsonErrors:
    @pytest.mark.parametrize("raw", [
        "",
        "not json at all",
        "[1, 2, 3]",
        '"a string"',
        '{"groups": "wrong type"}',
        '{"groups": {"not": "a list"}}',
    ])
    def test_returns_none_for_unparseable_or_malformed(self, raw):
        # NOTE: the malformed-groups cases rely on from_dict raising inside
        # from_json's try/except (AttrGroup.from_dict has no .get on a str).
        assert Config.from_json(raw) is None

    def test_returns_config_for_valid_dict(self):
        cfg = Config.from_json('{"version": 2, "groups": []}')
        assert isinstance(cfg, Config)
        assert cfg.version == 2

    def test_returns_config_for_legacy_node_key(self):
        raw = json.dumps({
            "groups": [{
                "name": "Legacy",
                "entries": [{"display_name": "Tx", "node": "|pCube1", "attr": "translateX"}],
            }]
        })
        cfg = Config.from_json(raw)
        assert cfg.groups[0].entries[0].node_path == "|pCube1"


# --------------------------------------------------------------------------
# normalise_orders
# --------------------------------------------------------------------------
class TestNormaliseOrders:
    def test_reorders_and_renumbers_groups(self):
        cfg = make_config(groups=[
            make_group(name="B", order=5),
            make_group(name="A", order=1),
        ])
        cfg.normalise_orders()
        assert [g.name for g in cfg.groups] == ["A", "B"]
        assert [g.order for g in cfg.groups] == [0, 1]

    def test_renumbers_entries_contiguously(self):
        cfg = make_config(groups=[
            make_group(name="G", entries=[
                make_entry(display_name="b", order=9),
                make_entry(display_name="a", order=0),
            ]),
        ])
        cfg.normalise_orders()
        assert [e.display_name for e in cfg.groups[0].entries] == ["a", "b"]
        assert [e.order for e in cfg.groups[0].entries] == [0, 1]

    def test_stable_sort_for_equal_orders(self):
        cfg = make_config(groups=[
            make_group(name="x", order=0, entries=[
                make_entry(display_name="first", order=0),
                make_entry(display_name="second", order=0),
            ]),
        ])
        cfg.normalise_orders()
        assert [e.display_name for e in cfg.groups[0].entries] == ["first", "second"]


# --------------------------------------------------------------------------
# Equality semantics (dataclass compares all fields)
# --------------------------------------------------------------------------
class TestEqualitySemantics:
    def test_entries_differ_only_by_invalid_reason_are_not_equal(self):
        a = make_entry()
        b = make_entry()
        b.invalid_reason = "Node not found"
        assert a != b

    def test_entries_differ_only_by_is_referenced_are_not_equal(self):
        a = make_entry()
        b = make_entry(is_referenced=True)
        assert a != b

    def test_configs_differ_by_float_precision(self):
        a = make_config()
        b = make_config(slider_float_precision=True)
        assert a != b

    def test_configs_equal_when_structurally_same(self):
        g = make_group(entries=[make_entry()])
        assert make_config(groups=[g]) == make_config(groups=[g])
