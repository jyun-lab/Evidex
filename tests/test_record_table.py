import csv
import datetime
import tempfile
import unittest
from pathlib import Path

from evidex.core import config
from evidex.core.record_table import (
    default_new_record,
    filter_record_rows,
    load_record_table,
    record_basic_items,
    record_detail_lines,
    record_file_entries,
    record_file_groups,
    resolve_record_file_path,
    row_values,
    save_record_rows,
    validate_record_update,
)


class RecordTableTests(unittest.TestCase):
    def setUp(self):
        self.original_records_csv = config.RECORDS_CSV
        self.temp_dir = tempfile.TemporaryDirectory()
        config.RECORDS_CSV = Path(self.temp_dir.name) / "runs.csv"

    def tearDown(self):
        config.RECORDS_CSV = self.original_records_csv
        self.temp_dir.cleanup()

    def test_load_record_table_uses_configured_records_csv(self):
        with config.RECORDS_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "run_id", "date", "title", "experimenter",
                    "result_summary", "raw_path", "notes",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "run_id": "R001",
                "date": "2026-06-16",
                "title": "Demo",
                "experimenter": "A",
                "result_summary": "OK",
                "raw_path": "a.csv; b.csv",
                "notes": "",
            })

        table = load_record_table()
        self.assertEqual(table.records_csv, config.RECORDS_CSV)
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(
            table.fields,
            [
                "run_id", "date", "title", "experimenter",
                "result_summary", "raw_path", "notes",
            ],
        )
        self.assertEqual(table.columns[0].key, "run_id")
        self.assertEqual(row_values(table.rows[0], table.columns)[0], "R001")

    def test_record_detail_lines_summarizes_multiple_files(self):
        row = {
            "run_id": "R001",
            "raw_path": "a.csv; b.csv",
        }
        lines = record_detail_lines(row)
        self.assertTrue(any("R001" in line for line in lines))
        self.assertTrue(any("2 file(s)" in line for line in lines))
        self.assertIn("  - a.csv", lines)
        self.assertIn("  - b.csv", lines)
        self.assertEqual(record_basic_items(row)[0][1], "R001")
        self.assertEqual(record_file_groups(row)[0][1], ["a.csv", "b.csv"])

    def test_record_file_entries_resolve_paths_relative_to_records_csv(self):
        existing = Path(self.temp_dir.name) / "a.csv"
        existing.write_text("x,y\n1,2\n", encoding="utf-8")
        row = {"raw_path": "a.csv; missing.csv"}

        groups = record_file_entries(row, config.RECORDS_CSV)
        entries = groups[0][1]

        self.assertEqual(resolve_record_file_path("a.csv", config.RECORDS_CSV), existing)
        self.assertTrue(entries[0].exists)
        self.assertFalse(entries[1].exists)
        self.assertEqual(entries[0].resolved_path, existing)

    def test_filter_record_rows_searches_all_visible_columns(self):
        table = load_record_table()
        rows = [
            {"run_id": "R001", "date": "2026-06-16", "title": "Temperature run"},
            {"run_id": "R002", "date": "2026-06-17", "title": "Pressure run"},
        ]
        self.assertEqual(
            [row["run_id"] for row in filter_record_rows(rows, table.columns, "temp")],
            ["R001"],
        )
        self.assertEqual(
            [row["run_id"] for row in filter_record_rows(rows, table.columns, "R002 pressure")],
            ["R002"],
        )
        self.assertEqual(len(filter_record_rows(rows, table.columns, "")), 2)

    def test_save_record_rows_writes_backup_and_updates_values(self):
        table = load_record_table()
        rows = [{"run_id": "R001", "date": "2026-06-16"}]
        mtime = save_record_rows(config.RECORDS_CSV, rows, table.fields)
        rows[0]["date"] = "2026-06-17"
        save_record_rows(config.RECORDS_CSV, rows, table.fields, mtime)

        loaded = load_record_table()
        self.assertEqual(loaded.rows[0]["date"], "2026-06-17")
        backups = list((Path(self.temp_dir.name) / "backup").glob("runs-*.csv"))
        self.assertTrue(backups)

    def test_validate_record_update_rejects_duplicate_run_id(self):
        rows = [{"run_id": "R001"}, {"run_id": "R002"}]
        with self.assertRaisesRegex(ValueError, "already exists"):
            validate_record_update(rows[0], {"run_id": "R002"}, rows)

    def test_default_new_record_sets_run_id_and_date(self):
        rows = [{"run_id": "20260616-01"}]
        record = default_new_record(
            rows,
            ["run_id", "date", "title"],
            today=datetime.date(2026, 6, 16),
        )
        self.assertEqual(record["run_id"], "20260616-02")
        self.assertEqual(record["date"], "2026-06-16")
        self.assertEqual(record["title"], "")


if __name__ == "__main__":
    unittest.main()
