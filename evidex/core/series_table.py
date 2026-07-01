import csv
import datetime
from pathlib import Path
import shutil

from evidex.core import config
from evidex.core.backup import prune_backups
from evidex.core.csvio import ensure_initial_csv_files, load_with_header
from evidex.core.fields import SERIES_FIELDS
from evidex.core.fsio import atomic_write


def series_csv_for_records(records_csv=None):
    records_path = Path(records_csv) if records_csv is not None else config.RECORDS_CSV
    return records_path.parent / "series.csv"


def load_series_table(records_csv=None):
    path = series_csv_for_records(records_csv)
    ensure_initial_csv_files(path.parent)
    if not path.exists():
        return [], list(SERIES_FIELDS), None
    rows, fields = load_with_header(path)
    return rows, fields, path.stat().st_mtime


def save_series_rows(records_csv, rows, fields, previous_mtime=None):
    path = series_csv_for_records(records_csv)
    if previous_mtime is not None and path.exists():
        if abs(path.stat().st_mtime - previous_mtime) > 1e-6:
            raise RuntimeError(
                "series.csv was changed by another process. Reload before saving."
            )

    backup_dir = path.parent / "backup"
    backup_dir.mkdir(exist_ok=True)
    if path.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, backup_dir / f"series-{stamp}.csv")
        prune_backups(backup_dir)

    output_fields = list(fields or SERIES_FIELDS)
    for field in SERIES_FIELDS:
        if field not in output_fields:
            output_fields.append(field)
    for row in rows:
        for field in row:
            if field not in output_fields:
                output_fields.append(field)

    with atomic_write(path, newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in output_fields})
    return path.stat().st_mtime


def series_grade_sequence(runs, grading_enabled=False):
    if not grading_enabled:
        return []
    return [
        (row.get("grade", "") or "").strip().upper() or "?"
        for row in runs
    ]


def compress_sequence(sequence):
    if not sequence:
        return "-"
    output = [sequence[0]]
    for item in sequence[1:]:
        if item != output[-1]:
            output.append(item)
    return " -> ".join(output)


def series_manager_rows(record_rows, series_rows, grading_enabled=False):
    series_ids = set()
    for row in series_rows:
        series_id = (row.get("series_id", "") or "").strip()
        if series_id:
            series_ids.add(series_id)
    for row in record_rows:
        series_id = (row.get("series_id", "") or "").strip()
        if series_id:
            series_ids.add(series_id)

    output = []
    for series_id in sorted(series_ids):
        runs = [
            row for row in record_rows
            if (row.get("series_id", "") or "").strip() == series_id
        ]
        runs.sort(key=lambda row: (row.get("date", ""), row.get("run_id", "")))
        dates = [row.get("date", "") for row in runs if row.get("date", "")]
        period = f"{min(dates)} - {max(dates)}" if dates else "-"
        series_row = next(
            (
                row for row in series_rows
                if (row.get("series_id", "") or "").strip() == series_id
            ),
            None,
        )
        objective = (series_row.get("objective", "") if series_row else "").strip()
        objective = objective.splitlines()[0] if objective else ""
        if len(objective) > 30:
            objective = objective[:30] + "..."
        output.append(
            {
                "sid": series_id,
                "n": len(runs),
                "period": period,
                "grades": compress_sequence(
                    series_grade_sequence(runs, grading_enabled)
                ),
                "objective": objective,
                "runs": runs,
                "srow": series_row,
            }
        )
    return output
