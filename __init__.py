"""Public launcher for the Maya-styled Attribute Manager."""

from __future__ import annotations

import importlib

from . import attributeManager as _attribute_manager


def reload_modules():
    importlib.reload(_attribute_manager)
    return _attribute_manager.reload_modules()


def launch():
    importlib.reload(_attribute_manager)
    return _attribute_manager.launch()
