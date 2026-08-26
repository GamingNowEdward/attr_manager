"""Make the parent tests directory importable for `import support`.

When the mayapy suite lives under tests/mayapy/, discovery still needs the
top-level ``support`` module (in tests/) on sys.path.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS = os.path.dirname(_HERE)
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)
