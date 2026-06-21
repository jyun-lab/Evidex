import csv
import datetime
from pathlib import Path
import shutil

from evidex.core import config
from evidex.core.backup import prune_backups
from evidex.core.csvio import ensure_initial_csv_files, load_with_header
from evidex.core.fields import STEP_FIELDS, STEP_FORM, get_label
from evidex.core.filtering import fnum
from evidex.core.i18n import t


def steps_csv_for_records(records_csv=None):
    records_path = Path(records_csv) if records_csv is not None else config.RECORDS_CSV
    return records_path.parent / "steps.csv"


def load_steps_table(records_csv=None):
    path = steps_csv_for_records(records_csv)
    ensure_initial_csv_files(path.parent)
    if not path.exists():
        return {}, list(STEP_FIELDS), None

    rows, fields = load_with_header(path)
    steps = {}
    for row in rows:
        steps.setdefault(row.get("run_id", ""), []).append(row)
    for run_steps in steps.values():
        run_steps.sort(key=_step_sort_key)
    return steps, fields, path.stat().st_mtime


def save_steps_table(records_csv, steps_by_run, fields, previous_mtime=None):
    path = steps_csv_for_records(records_csv)
    if previous_mtime is not None and path.exists():
        if abs(path.stat().st_mtime - previous_mtime) > 1e-6:
            raise RuntimeError(
                "steps.csv was changed by another process. Reload before saving."
            )

    backup_dir = path.parent / "backup"
    backup_dir.mkdir(exist_ok=True)
    if path.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, backup_dir / f"steps-{stamp}.csv")
        prune_backups(backup_dir)

    output_fields = list(fields or STEP_FIELDS)
    for field in STEP_FIELDS:
        if field not in output_fields:
            output_fields.append(field)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        for run_id in sorted(steps_by_run):
            for step in steps_by_run[run_id]:
                writer.writerow({field: step.get(field, "") for field in output_fields})
    return path.stat().st_mtime


def validate_step_update(updated):
    primary = STEP_FORM[0][0] if STEP_FORM else None
    if primary and not updated.get(primary, "").strip():
        raise ValueError(t("steps.validation.primary_required"))

    numeric_fields = [
        ("viscosity_mPas", get_label("viscosity_mPas")),
        ("drop_volume_uL", get_label("drop_volume_uL")),
        ("duration_min", get_label("duration_min")),
        ("data_start_row", get_label("data_start_row")),
        ("data_end_row", get_label("data_end_row")),
    ]
    for field, label in numeric_fields:
        if field not in STEP_FIELDS:
            continue
        value = updated.get(field, "").strip()
        if value and fnum(value) is None:
            raise ValueError(t("steps.validation.must_be_number", label=label))

    start = updated.get("data_start_row", "").strip()
    end = updated.get("data_end_row", "").strip()
    if "data_start_row" in STEP_FIELDS and "data_end_row" in STEP_FIELDS:
        start_num = fnum(start) if start else None
        end_num = fnum(end) if end else None
        if start_num is not None and end_num is not None and start_num > end_num:
            raise ValueError(t("steps.validation.start_must_le_end"))
        if (start_num is not None and start_num < 2) or (
            end_num is not None and end_num < 2
        ):
            raise ValueError(t("steps.validation.data_rows_min_2"))

    return True


def _step_sort_key(row):
    value = fnum(row.get("step_no", ""))
    return value if value is not None else 0
