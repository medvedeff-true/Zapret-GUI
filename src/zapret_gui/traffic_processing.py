"""Compatibility facade for traffic-processing preference helpers.

The implementation lives in :mod:`zapret_gui.traffic_modes`, which is also
used by the existing runtime mode builder.  Keep this small module for code
and plugins that imported the first-slice helper name while the feature was
being split into separate runtime modules.
"""

from __future__ import annotations

from .traffic_modes import (
    TRAFFIC_MODE_ALL,
    TRAFFIC_MODE_APPLICATIONS,
    TRAFFIC_MODE_LISTS,
    TRAFFIC_MODES,
    list_has_values,
    mode_from_index,
    mode_index,
    normalize_traffic_mode,
    settings_bool,
    settings_mode,
)

# The first SettingsDialog implementation used this descriptive name.
list_file_has_entries = list_has_values

__all__ = [
    "TRAFFIC_MODE_ALL",
    "TRAFFIC_MODE_APPLICATIONS",
    "TRAFFIC_MODE_LISTS",
    "TRAFFIC_MODES",
    "list_file_has_entries",
    "list_has_values",
    "mode_from_index",
    "mode_index",
    "normalize_traffic_mode",
    "settings_bool",
    "settings_mode",
]
