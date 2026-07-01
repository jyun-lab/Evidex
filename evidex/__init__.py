"""
Evidex: A structured laboratory data management GUI.
"""

__version__ = "0.3.0"

__all__ = ["App", "Tooltip", "RUN_FIELDS", "STEP_FIELDS",
           "BUNDLED_ASSETS", "THEMED", "MPL", "_UI_FONT_CANDIDATES",
           "ensure_initial_csv_files", "extract_bundled_assets",
           "load_with_header", "load_steps_with_header", "icon_for_action", "icon_for_liquid"]

def __getattr__(name):
    if name == "App":
        from .main import App
        return App
    if name == "Tooltip":
        from .components import Tooltip
        return Tooltip
    if name in ["RUN_FIELDS", "STEP_FIELDS"]:
        from .core import fields
        return getattr(fields, name)
    if name in ["BUNDLED_ASSETS", "_UI_FONT_CANDIDATES"]:
        from .core import config
        return getattr(config, name)
    if name in ["THEMED", "MPL"]:
        from .gui_runtime import THEMED, MPL
        return THEMED if name == "THEMED" else MPL
    if name in ["ensure_initial_csv_files", "extract_bundled_assets", "load_with_header", "load_steps_with_header"]:
        from .core import csvio
        return getattr(csvio, name)
    if name in ["icon_for_action", "icon_for_liquid"]:
        from .core import icons
        return getattr(icons, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
