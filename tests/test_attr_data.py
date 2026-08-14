"""Serialisation round-trip tests for core.attr_data (pure Python, no Maya)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.attr_data import AttrEntry, AttrGroup, Config


def _entry(**kw):
    defaults = dict(
        display_name="translateX",
        node_path="|group1|pCube1",
        node_uuid="uuid-1",
        attr="translateX",
        order=0,
        control_mode="spin",
        custom_min=None,
        custom_max=None,
        display_type="auto",
        is_referenced=False,
    )
    defaults.update(kw)
    return AttrEntry(**defaults)


def _full_config() -> Config:
    main = AttrGroup(name="Main")
    main.entries = [
        _entry(display_name="Translate X", node_uuid="uuid-1", attr="translateX",
               custom_min=-10.0, custom_max=10.0),
        _entry(display_name="Visible", node_uuid="uuid-2", attr="visibility",
               control_mode="check"),
    ]
    ref = AttrGroup(name="Ref Group", order=1, reference_namespace="refNs")
    ref.entries = [
        _entry(display_name="Rotate Y", node_uuid="uuid-3", attr="rotateY", order=0),
    ]
    cfg = Config(groups=[main, ref], slider_float_precision=True)
    return cfg


class SerialisationRoundTrip(unittest.TestCase):
    def test_json_roundtrip_preserves_full_config(self):
        cfg = _full_config()
        restored = Config.from_json(cfg.to_json())
        self.assertIsNotNone(restored)
        self.assertEqual(restored, cfg)

    def test_to_dict_omits_optional_defaults(self):
        cfg = Config()
        group = AttrGroup(name="Main")
        group.entries = [_entry()]
        cfg.groups = [group]
        data = cfg.to_dict()
        self.assertNotIn("slider_float_precision", data)
        group_data = data["groups"][0]
        self.assertNotIn("reference_namespace", group_data)
        self.assertEqual(len(group_data["entries"]), 1)
        entry_data = group_data["entries"][0]
        self.assertNotIn("custom_min", entry_data)
        self.assertNotIn("custom_max", entry_data)

    def test_to_dict_serialises_optional_fields_when_set(self):
        cfg = _full_config()
        data = cfg.to_dict()
        self.assertTrue(data["slider_float_precision"])
        main_data = data["groups"][0]
        self.assertEqual(main_data["entries"][0]["custom_min"], -10.0)
        self.assertEqual(main_data["entries"][0]["custom_max"], 10.0)
        self.assertIn("reference_namespace", data["groups"][1])

    def test_normalise_orders_sorts_and_renumbers(self):
        g1 = AttrGroup(name="First", order=5)
        g2 = AttrGroup(name="Second", order=1)
        g1.entries = [
            _entry(display_name="B", order=9),
            _entry(display_name="A", order=0),
        ]
        cfg = Config(groups=[g1, g2])
        cfg.normalise_orders()
        self.assertEqual([g.name for g in cfg.groups], ["Second", "First"])
        self.assertEqual([g.order for g in cfg.groups], [0, 1])
        self.assertEqual([e.display_name for e in cfg.groups[1].entries], ["A", "B"])
        self.assertEqual([e.order for e in cfg.groups[1].entries], [0, 1])

    def test_from_json_empty_and_invalid_returns_none(self):
        self.assertIsNone(Config.from_json(""))
        self.assertIsNone(Config.from_json("not json at all"))
        self.assertIsNone(Config.from_json("[1, 2, 3]"))
        self.assertIsNone(Config.from_json('"a string"'))
        self.assertIsNone(Config.from_json('{"groups": "wrong type"}'))
        self.assertIsNone(Config.from_json('{"groups": {"not": "a list"}}'))

    def test_from_dict_accepts_legacy_node_key(self):
        raw = {
            "groups": [{
                "name": "Legacy",
                "entries": [{
                    "display_name": "Tx", "node": "|pCube1", "attr": "translateX",
                }],
            }],
        }
        cfg = Config.from_dict(raw)
        entry = cfg.groups[0].entries[0]
        self.assertEqual(entry.node_path, "|pCube1")
        self.assertEqual(entry.display_type, "auto")
        self.assertEqual(entry.order, 0)

    def test_from_dict_defaults_for_empty_document(self):
        cfg = Config.from_dict({})
        self.assertEqual(cfg.version, 1)
        self.assertEqual(cfg.groups, [])
        self.assertFalse(cfg.slider_float_precision)

    def test_roundtrip_through_dict_matches(self):
        cfg = _full_config()
        self.assertEqual(Config.from_dict(cfg.to_dict()), cfg)

    def test_is_referenced_is_runtime_flag_not_persisted(self):
        cfg = Config()
        group = AttrGroup(name="Ref", reference_namespace="refNs")
        group.entries = [_entry(is_referenced=True)]
        cfg.groups = [group]
        restored = Config.from_json(cfg.to_json())
        # Reference identity persists on the group; entry.is_referenced is
        # derived at load time by scene_io.load_config, never serialised.
        self.assertEqual(restored.groups[0].reference_namespace, "refNs")
        self.assertFalse(restored.groups[0].entries[0].is_referenced)


if __name__ == "__main__":
    unittest.main()
