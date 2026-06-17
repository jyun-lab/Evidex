from dataclasses import dataclass
import csv
import datetime
from pathlib import Path
import shutil

from evidex.core import config
from evidex.core.attachments import split_paths
from evidex.core.backup import prune_backups
from evidex.core.csvio import ensure_initial_csv_files, load_with_header
from evidex.core.fields import COLS, HEAD, RUN_FIELDS, get_label


@dataclass(frozen=True)
class RecordColumn:
    key: str
    label: str
    width: int


@dataclass(frozen=True)
class RecordTable:
    records_csv: Path
    columns: list[RecordColumn]
    rows: list[dict]
    fields: list[str]
    mtime: float | None = None


@dataclass(frozen=True)
class RecordFile:
    label: str
    path: str
    resolved_path: Path
    exists: bool


def default_record_columns():
    return [
        RecordColumn(key=key, label=HEAD.get(key, key), width=int(width or 120))
        for key, width in COLS
    ]


def load_record_table(records_csv=None):
    path = Path(records_csv) if records_csv is not None else config.RECORDS_CSV
    ensure_initial_csv_files(path.parent)
    rows, fields = load_with_header(path) if path.exists() else ([], list(RUN_FIELDS))
    return RecordTable(
        records_csv=path,
        columns=default_record_columns(),
        rows=rows,
        fields=fields,
        mtime=path.stat().st_mtime if path.exists() else None,
    )


def save_record_rows(records_csv, rows, fields, previous_mtime=None):
    path = Path(records_csv)
    if previous_mtime is not None and path.exists():
        if abs(path.stat().st_mtime - previous_mtime) > 1e-6:
            raise RuntimeError(
                "runs.csv was changed by another process. Reload before saving."
            )

    backup_dir = path.parent / "backup"
    backup_dir.mkdir(exist_ok=True)
    if path.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, backup_dir / f"runs-{stamp}.csv")
        prune_backups(backup_dir)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return path.stat().st_mtime


def validate_record_update(row, updated, rows):
    run_id = updated.get("run_id", "").strip()
    if not run_id:
        raise ValueError("run_id is required.")
    for existing in rows:
        if existing is not row and existing.get("run_id", "") == run_id:
            raise ValueError(f"run_id already exists: {run_id}")
    return True


def default_new_record(rows, fields, today=None):
    today = today or datetime.date.today()
    data = {field: "" for field in fields}
    stamp = today.strftime("%Y%m%d")
    count = sum(
        1 for row in rows
        if row.get("run_id", "").startswith(stamp)
    )
    if "run_id" in data:
        data["run_id"] = f"{stamp}-{count + 1:02d}"
    if "date" in data:
        data["date"] = today.isoformat()
    return data


def row_values(row, columns):
    return [row.get(column.key, "") for column in columns]


def record_matches_query(row, columns, query):
    terms = [
        term.casefold()
        for term in str(query or "").split()
        if term.strip()
    ]
    if not terms:
        return True
    visible_values = row_values(row, columns)
    all_values = list(row.values())
    haystack = " ".join(
        str(value).casefold() for value in [*visible_values, *all_values]
    )
    return all(term in haystack for term in terms)


def filter_record_rows(rows, columns, query):
    return [
        row for row in rows
        if record_matches_query(row, columns, query)
    ]


def record_basic_items(row):
    items = []
    for key in RUN_FIELDS:
        value = row.get(key, "")
        if value:
            items.append((get_label(key), value))
    return items


def record_file_groups(row):
    groups = []
    for key in ("raw_path", "excel_path", "photo_path"):
        paths = split_paths(row.get(key, ""))
        if paths:
            groups.append((get_label(key), paths))
    return groups


def resolve_record_file_path(path, records_csv=None):
    source = Path(path)
    if source.is_absolute():
        return source
    base = Path(records_csv).parent if records_csv is not None else config.RECORDS_CSV.parent
    return base / source


def record_file_entries(row, records_csv=None):
    groups = []
    for label, paths in record_file_groups(row):
        entries = []
        for path in paths:
            resolved = resolve_record_file_path(path, records_csv)
            entries.append(
                RecordFile(
                    label=label,
                    path=path,
                    resolved_path=resolved,
                    exists=resolved.exists(),
                )
            )
        groups.append((label, entries))
    return groups


def record_detail_lines(row):
    lines = []
    for label, value in record_basic_items(row):
        lines.append(f"{label}: {value}")

    file_lines = []
    for label, paths in record_file_groups(row):
        file_lines.append(f"{label}: {len(paths)} file(s)")
        file_lines.extend(f"  - {path}" for path in paths)

    if file_lines:
        if lines:
            lines.append("")
        lines.extend(file_lines)

    return lines or ["No record selected."]
