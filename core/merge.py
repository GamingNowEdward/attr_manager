"""Pure data transforms between the merged display structure and the persisted config.

No Maya or Qt imports: these functions operate on :mod:`core.attr_data` objects
only, so they are unit-testable outside Maya.

- ``merge_for_display``: turn the merged (main + referenced) config into the
  structure shown in the panel — overrides living in main groups are moved into
  their referenced group's original position for display.
- ``collect_for_save``: the inverse — gather main groups plus overrides that are
  currently displayed inside referenced groups into a persistable config.
"""

from __future__ import annotations

import copy

from .attr_data import AttrEntry, AttrGroup, Config


def entry_key(entry: AttrEntry) -> tuple:
    """Stable identity of an entry for override matching."""
    return (entry.node_uuid or entry.node_path, entry.attr)


def merge_for_display(config: Config) -> Config:
    """Merge main + referenced groups into the panel display structure.

    Mutates ``config`` in place (group objects and ``config.groups``) and
    returns it. Main-group entries whose key matches a referenced entry are
    treated as overrides: they replace the referenced entry inside its group.
    """
    main_groups = [g for g in config.groups if g.reference_namespace is None]
    ref_groups = [g for g in config.groups if g.reference_namespace is not None]

    main_entries = {}
    for group in main_groups:
        for entry in group.entries:
            main_entries.setdefault(entry_key(entry), []).append(entry)

    merged_ref_groups = []
    shown_main_keys = set()
    for ref_group in ref_groups:
        merged_entries = []
        for entry in ref_group.entries:
            key = entry_key(entry)
            if key in main_entries:
                merged_entries.append(main_entries[key][0])
                shown_main_keys.add(key)
            else:
                merged_entries.append(entry)
        if merged_entries:
            ref_group.entries = merged_entries
            merged_ref_groups.append(ref_group)

    visible_groups = []
    for group in main_groups:
        remaining = [e for e in group.entries if entry_key(e) not in shown_main_keys]
        if group.entries and not remaining:
            continue
        group.entries = remaining
        visible_groups.append(group)
    visible_groups.extend(merged_ref_groups)

    config.groups = visible_groups
    return config


def collect_for_save(config: Config) -> Config:
    """Collect the display structure into a persistable config.

    Returns a new ``Config`` (main groups plus override store groups gathered
    from inside referenced-group display structures). Never mutates ``config``.
    """
    main_groups = []
    for group in config.groups:
        if group.reference_namespace is None:
            main_groups.append(copy.deepcopy(group))
        else:
            overrides = [copy.deepcopy(e) for e in group.entries if not e.is_referenced]
            if overrides:
                main_groups.append(AttrGroup(
                    name=group.name,
                    order=group.order,
                    collapsed=False,
                    entries=overrides,
                ))

    main_config = Config(
        version=config.version,
        slider_float_precision=config.slider_float_precision,
        groups=main_groups,
    )
    main_config.normalise_orders()
    return main_config


def merge_configs(base: Config, extra: Config) -> Config:
    """Merge ``extra`` into ``base`` for main-config-node convergence.

    Same-named groups keep ``base``'s collapsed state and gain ``extra``'s
    entries (deduped by :func:`entry_key`); differently-named groups are
    appended whole. Returns a new ``Config`` and never mutates either input.
    """
    merged = copy.deepcopy(base)
    by_name = {group.name: group for group in merged.groups}
    for group in extra.groups:
        target = by_name.get(group.name)
        if target is None:
            merged.groups.append(copy.deepcopy(group))
            by_name[group.name] = merged.groups[-1]
            continue
        existing = {entry_key(entry) for entry in target.entries}
        for entry in group.entries:
            key = entry_key(entry)
            if key not in existing:
                target.entries.append(copy.deepcopy(entry))
                existing.add(key)
    merged.normalise_orders()
    return merged
