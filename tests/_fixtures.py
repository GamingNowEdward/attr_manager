"""Pure-Python test fixtures for the Attribute Manager data layer.

No Maya dependency: these build :mod:`core.attr_data` objects directly so the
pure test suite can run under any system Python with pytest.
"""

from __future__ import annotations

from core.attr_data import AttrEntry, AttrGroup, Config


def make_entry(display_name="translateX", node_uuid="uuid-1", attr="translateX", **kw):
    defaults = dict(
        node_path="|group|" + display_name,
        order=0,
        invalid_reason="",
        control_mode="spin",
        custom_min=None,
        custom_max=None,
        display_type="auto",
        is_referenced=False,
    )
    defaults.update(
        display_name=display_name,
        node_uuid=node_uuid,
        attr=attr,
    )
    defaults.update(kw)
    return AttrEntry(**defaults)


def make_group(name="Main", entries=(), **kw):
    group = AttrGroup(name=name, **kw)
    group.entries = list(entries)
    return group


def make_config(groups=(), version=1, slider_float_precision=False):
    return Config(
        version=version,
        groups=list(groups),
        slider_float_precision=slider_float_precision,
    )
