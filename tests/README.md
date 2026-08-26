# Tests

The suite is split into two independent halves: the Maya-free half is run by
CI automatically, while the Maya-dependent half is executed locally (not part
of CI).

## Layout

```
tests/
  pytest.ini            # testpaths=tests, ignores tests/mayapy
  conftest.py           # puts project root + tests/ on sys.path
  _fixtures.py          # pure-Python data factories (no Maya)
  test_attr_data_pure.py  # core.attr_data: data model + serialisation
  test_merge_pure.py     # core.merge: merge_for_display / collect_for_save / merge_configs
  support.py             # shared mayapy harness (import-safe; see note)
  mayapy/                # MAYA-DEPENDENT tests — not collected by pytest
    __init__.py
    test_attr_data.py          # ResolveEntries (real nodes) — mayapy only
    test_scene_io.py           # save/load round-trip, locking, convergence
    test_channel_box.py        # command-hook firing
    test_reference_integration.py
```

`tests/support.py` is import-safe under system Python: it only initialises
`maya.standalone` / imports `maya.cmds` inside a `try/except`, so importing it
without Maya present simply leaves `cmds = None`. The pure tests do NOT import
it — they use `tests/_fixtures.py` instead.

## Pure-Python suite (no Maya)

Runs under any system Python with pytest. This is what CI runs automatically.

```
python -m pytest -v
```

- Exit code 0 = all green.
- Single file: `python -m pytest tests/test_merge_pure.py -v`
- Single case: `python -m pytest tests/test_attr_data_pure.py::TestConfigJsonRoundTrip::test_round_trip_equals_for_normalised_clean_config -v`

`pytest.ini` sets `testpaths = tests` and `addopts = --ignore=tests/mayapy`, so
`pytest` collects only the Maya-free tests regardless of CWD.

Coverage:

| File | Scope |
|---|---|
| `test_attr_data_pure.py` | `AttrEntry`/`AttrGroup`/`Config` serialisation; the `is_referenced`/`invalid_reason` serialisation boundary; `Config.to_dict`/`from_dict` `normalise_orders` side effect; `from_json` error matrix; equality semantics |
| `test_merge_pure.py` | `entry_key`; `merge_for_display` override placement + order preservation; `collect_for_save` (gathers main + override store groups, never mutates input); override save/reload round-trip; `merge_configs` convergence |

## mayapy suite (Maya required)

Drives the live kernel (scene I/O, references, undo queue, `MCommandMessage`).
Run locally with Maya's `mayapy.exe`. This suite is **not** part of CI — it is
executed on your machine.

```
mayapy -m unittest discover -s tests/mayapy -t tests -v
```

`-t tests` puts the `tests/` directory (home of `support.py`) on `sys.path` so
the moved tests can still `import support`.

Coverage:

| File | Scope |
|---|---|
| `test_attr_data.py` (`ResolveEntries`) | real-node `resolve_entries` (valid uuid / missing node / missing attr / locked / input connection) |
| `test_scene_io.py` | save→load round-trip incl. file reopen, locking contract, undo footprint, corrupt-JSON tolerance, `get_or_create_node` branches, main-config convergence |
| `test_channel_box.py` | `_parse_set_attr_line` matrix; real hook firing; `_hook_enabled` gating; `unlock_attr` |
| `test_reference_integration.py` | `file -reference` tagging, override survives reopen, unload/remove drops ref data, namespace rename, dual references |

## CI

`.github/workflows/ci.yml` defines a single job:

- `pure-tests` — `ubuntu-latest`, Python **3.13** (aligned with Maya 2027's
  bundled Python 3.13.3); runs `pytest`. Triggered on push / PR.

The mayapy suite (above) is **not** part of CI; it is run locally.

## Headless notes & gotchas learned here

- `tests/__init__.py` bootstraps sys.path (project root + tests dir), and
  `tests/conftest.py` re-asserts it, so both `unittest discover` and
  `pytest` work and test modules can `import core` / `from _fixtures import …`.
- `core/attr_data.py` has no Maya import until `resolve_entries()` is called, so
  the pure suite imports it safely. `core/merge.py` has no Maya/Qt imports.
- `Config.to_dict()` and `Config.from_dict()` both call `normalise_orders()` as
  a side effect (they renumber group/entry `.order` fields). `merge_for_display`
  mutates in place but does NOT renumber; `collect_for_save` returns a new
  `Config` and does normalise the returned copy (it deep-copies main groups so
  the input is never mutated).
- `from_json` returns `None` for empty/non-JSON/non-dict input and for
  malformed `groups` (e.g. a string or a dict-of-keys) because `from_dict`
  raises and `from_json` swallows the exception. This is implementation-coupled.
- Temp scenes go to `%TEMP%\attrman_tests\<hex>` and are removed per-test via
  `addCleanup` (mayapy suite only).
