"""Public launcher for the Maya-styled Attribute Manager."""

from __future__ import annotations

import importlib

from . import launch as _launch_module


def reload_modules():
    importlib.reload(_launch_module)
    return _launch_module.reload_modules()


def launch(dockable=True):
    importlib.reload(_launch_module)
    return _launch_module.launch(dockable=dockable)
