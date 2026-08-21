"""Package bootstrap: make both the project root and this directory
importable regardless of how the suite is launched (unittest discover or
-m unittest tests.test_xxx).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.dirname(_HERE), _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)
