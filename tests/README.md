# Tests — mayapy Test Suite

All tests run inside Maya's own interpreter (`mayapy.exe`) and drive the
live kernel: scene I/O, references, undo queue, MCommandMessage. System
Python is NOT supported — `support.py` calls
`maya.standalone.initialize(name="python")` on import.

## Run

From the project root:

```
"C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe" -m unittest discover -s tests -v
```

- Exit code 0 = all green.
- Single file: `"…mayapy.exe" -m unittest tests.test_scene_io -v`
- Single case: `"…mayapy.exe" -m unittest tests.test_scene_io.LockingContract.test_config_node_locked_after_save -v`

Startup noise from the machine's userSetup (Zoo Tools banner, MCP
commandPort warnings) is harmless.

## Coverage

| File | Scope |
|---|---|
| `test_attr_data.py` | Serialisation round-trips; `resolve_entries` against real nodes (valid uuid / missing node / missing attr / locked / input connection) |
| `test_merge.py` | `merge_for_display` / `collect_for_save` behaviour matrix (hand-built data) |
| `test_scene_io.py` | save→load round-trip incl. file reopen, locking contract, undo footprint, corrupt-JSON tolerance, `get_or_create_node` branches, save filtering of ref groups/entries |
| `test_channel_box.py` | `_parse_set_attr_line` matrix; real hook firing (MEL yes, Python cmds no); `_hook_enabled` gating; `unlock_attr` |
| `test_reference_integration.py` | End-to-end: `file -reference` tagging, override survives scene reopen in original position, unload/remove drops ref data, namespace rename picked up on reload, dual references independently tagged |

Not covered (GUI-only, manual testing required): dock/workspace behaviour,
undo from Qt callbacks inside the running panel, drag-and-drop, focus
handling — see AGENTS.md.

## Headless notes & gotchas learned here

- `tests/__init__.py` bootstraps sys.path (project root + tests dir), so
  both `unittest discover -s tests` and `-m unittest tests.test_xxx`
  work; test modules can plain `import support`.
- mayapy needs `maya.standalone.initialize(name="python")` before
  `maya.cmds` is complete (otherwise e.g. `cmds.file` does not exist).
  Double init raises RuntimeError, which `support.py` swallows.
- `cmds.file(refNodeName, removeReference=True)` FAILS with "File not
  found": the first positional argument must be the reference FILE PATH.
  Same for `unloadReference=True` and `edit=True, namespace=...`.
- `load_config()` runs `resolve_entries()` at the end, refreshing
  `node_path`/`node_uuid`. A saved config only compares equal to its
  fixture after calling `resolve_entries(fixture)`.
- A locked node rejects `cmds.setAttr(plug, lock=True)` ("Attribute is
  from a locked node") — unlock the NODE first, then the plug.
- Verified in batch mayapy: MCommandMessage callbacks DO fire for MEL
  `setAttr`; direct `save_config()` adds zero undo entries. The GUI
  Qt-callback undo path remains manual-test territory.
- Fixtures: `support.make_ref_scene()` is self-contained — it starts AND
  ends with `file -new`, so it never leaks geometry into the caller's
  scene. Build ALL fixture files first, then reference them; referencing
  a file that is still the current scene triggers "File is already in
  memory".
- Temp scenes go to `%TEMP%\attrman_tests\<hex>` and are removed per-test
  via `addCleanup`.
