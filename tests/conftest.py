"""pytest bootstrap: ensure project root and tests dir are importable."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
for _path in (_PROJECT_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)
