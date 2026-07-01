"""Pack management operations — UI-independent logic.

Both the tkinter and Qt UIs import from here.
"""
import copy
import json
import re
import shutil
from pathlib import Path

from evidex.core import config
from evidex.core.fsio import atomic_write
from evidex.core.i18n import t
from evidex.core.schema import load_schema, pack_resource_dir
from evidex.packs import get_pack_names, registry


_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_REQUIRED_SCHEMA_KEYS = ("RUN_FIELDS", "JP_LABEL", "COLS", "HEAD")
_COPYABLE_PACK_FILES = ("schema.json", "adapter_config.json", "adapter.py", "viz.json")


def choose_initial_pack(pack_names, selected_name="", active_name=""):
    if selected_name in pack_names:
        return selected_name
    if active_name in pack_names:
        return active_name
    return pack_names[0] if pack_names else None


def csv_guidance_key(pack_name, has_python_adapter):
    if pack_name == config.DEFAULT_PACK:
        return "schema_editor.csv_guidance_template"
    if has_python_adapter:
        return "schema_editor.csv_guidance_custom_reader"
    return "schema_editor.csv_guidance_column_settings"


def adapter_mapping_layout(width, breakpoint=620):
    return "stacked" if width < breakpoint else "columns"


def adapter_summary_lines(adapter, has_python_adapter=False):
    if has_python_adapter and not adapter:
        return [
            "schema_editor.current_reader_custom",
            "schema_editor.current_reader_custom_location",
            "schema_editor.current_reader_custom_mapping",
        ]
    if not adapter:
        return ["schema_editor.current_settings_empty"]
    if not adapter.get("x_column") or not adapter.get("channel_columns"):
        return [
            "schema_editor.current_settings_incomplete",
            "schema_editor.current_settings_next_steps",
        ]

    channel_columns = list(adapter.get("channel_columns") or [])
    channel_units = list(adapter.get("channel_units") or [])
    channels = []
    for index, name in enumerate(channel_columns):
        unit = channel_units[index] if index < len(channel_units) else ""
        channels.append(f"{name} [{unit}]" if unit else str(name))
    if not channels:
        channels.append("-")

    delimiter = adapter.get("delimiter", ",")
    delimiter_text = "\\t" if delimiter == "\t" else delimiter
    return [
        ("schema_editor.current_x_axis", {
            "column": adapter.get("x_column") or "-",
            "name": adapter.get("x_name") or "-",
            "unit": adapter.get("x_unit") or "-",
        }),
        ("schema_editor.current_channels", {
            "channels": ", ".join(channels),
        }),
        ("schema_editor.current_csv_options", {
            "skip_rows": adapter.get("skip_rows", 0),
            "delimiter": delimiter_text or "-",
        }),
    ]


def user_pack_root():
    return config.RECORDS_CSV.parent / "packs"


def user_pack_dir(pack_name):
    return user_pack_root() / pack_name


def validate_pack_name(pack_name, allow_existing=False):
    name = (pack_name or "").strip()
    if not name or not _PACK_NAME_RE.fullmatch(name):
        raise ValueError(t("schema_editor.invalid_name"))
    if name in registry:
        raise ValueError(t("schema_editor.str30"))
    if not allow_existing and name in get_pack_names():
        raise ValueError(t("schema_editor.str35"))
    return name


def validate_schema(schema):
    if not isinstance(schema, dict):
        raise ValueError(t("schema_editor.str31"))
    if not all(key in schema for key in _REQUIRED_SCHEMA_KEYS):
        raise ValueError(t("schema_editor.str31"))

    fields = schema.get("RUN_FIELDS")
    if (
        not isinstance(fields, list)
        or not fields
        or any(not isinstance(field, str) or not field.strip() for field in fields)
        or len(fields) != len(set(fields))
    ):
        raise ValueError(t("schema_editor.invalid_fields"))
    if not isinstance(schema.get("JP_LABEL"), dict):
        raise ValueError(t("schema_editor.str31"))
    if not isinstance(schema.get("COLS"), list) or not isinstance(schema.get("HEAD"), dict):
        raise ValueError(t("schema_editor.str31"))
    return True


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_write(path, encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_user_pack(pack_name, schema, adapter=None, viz=None):
    name = validate_pack_name(pack_name, allow_existing=True)
    validate_schema(schema)
    destination = user_pack_dir(name)
    destination.mkdir(parents=True, exist_ok=True)
    _write_json(destination / "schema.json", schema)

    if adapter:
        _write_json(destination / "adapter_config.json", adapter)
        adapter_py = destination / "adapter.py"
        if adapter_py.exists():
            adapter_py.unlink()
    if viz is not None:
        _write_json(destination / "viz.json", viz)
    return destination


def duplicate_pack(source_name, new_name):
    name = validate_pack_name(new_name)
    if source_name in registry:
        source = pack_resource_dir(source_name)
    else:
        source = user_pack_dir(source_name)
    if not source.is_dir():
        raise ValueError(t("schema_editor.pack_not_found", pack_name=source_name))

    destination = user_pack_dir(name)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        copied = False
        for filename in _COPYABLE_PACK_FILES:
            source_file = source / filename
            if source_file.is_file():
                shutil.copy2(source_file, destination / filename)
                copied = True
        if not copied or not (destination / "schema.json").is_file():
            raise ValueError(t("schema_editor.str31"))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def delete_user_pack(pack_name):
    name = validate_pack_name(pack_name, allow_existing=True)
    destination = user_pack_dir(name)
    if not destination.is_dir():
        raise ValueError(t("schema_editor.pack_not_found", pack_name=name))
    shutil.rmtree(destination)


def blank_schema():
    return {
        "RUN_FIELDS": ["run_id", "date"],
        "JP_LABEL": {"run_id": "run_id(実験ID)", "date": "実験日(YYYY-MM-DD)"},
        "LABEL_EN": {"run_id": "Run ID", "date": "Date (YYYY-MM-DD)"},
        "FIELD_TYPES": {"run_id": "text", "date": "date"},
        "CHOICES": {},
        "COLS": [["run_id", 100], ["date", 100]],
        "HEAD": {"run_id": "run_id", "date": "Date"},
        "facets": [],
        "adv_filters": [],
        "GCOL": {},
        "features": {
            "steps": False,
            "series": False,
            "grading": False,
            "baseline": False,
        },
        "waveform": {
            "default_mode": "all",
            "step_markers": False,
            "modes": [{
                "id": "all",
                "label": "Channels",
                "y_label": "Value",
                "channels": "all",
            }],
        },
        "STEP_FIELDS": ["step_id", "run_id"],
        "SERIES_FIELDS": ["series_id", "objective"],
        "LONG_FIELDS": [],
        "HIDDEN_EDIT_FIELDS": [],
        "STEP_FORM": [],
        "ACTION_CHOICES": [],
        "MEDIA_SEEDS": [],
    }


def blank_adapter():
    return {
        "file_format": "csv",
        "encoding_fallback": ["utf-8-sig", "cp932"],
        "skip_rows": 0,
        "x_column": "",
        "x_name": "",
        "x_unit": "",
        "channel_columns": [],
        "channel_units": [],
        "delimiter": ",",
    }
