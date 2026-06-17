import tempfile
import unittest
from pathlib import Path

from evidex.core import config
from evidex.core.series_table import (
    compress_sequence,
    load_series_table,
    save_series_rows,
    series_manager_rows,
)


class SeriesTableTests(unittest.TestCase):
    def setUp(self):
        self.original_records_csv = config.RECORDS_CSV
        self.temp_dir = tempfile.TemporaryDirectory()
        config.RECORDS_CSV = Path(self.temp_dir.name) / "runs.csv"

    def tearDown(self):
        config.RECORDS_CSV = self.original_records_csv
        self.temp_dir.cleanup()

    def test_series_manager_rows_unions_registered_and_referenced_ids(self):
        record_rows = [
            {
                "run_id": "R002",
                "date": "2026-02-01",
                "series_id": "S1",
                "grade": "B",
            },
            {
                "run_id": "R001",
                "date": "2026-01-01",
                "series_id": "S1",
                "grade": "A",
            },
            {
                "run_id": "R003",
                "date": "2026-03-01",
                "series_id": "S2",
                "grade": "",
            },
        ]
        series_rows = [
            {"series_id": "S1", "objective": "Long objective\nsecond line"},
            {"series_id": "S9", "objective": "Unused"},
        ]

        rows = series_manager_rows(record_rows, series_rows, grading_enabled=True)
        by_id = {row["sid"]: row for row in rows}

        self.assertEqual(set(by_id), {"S1", "S2", "S9"})
        self.assertEqual(by_id["S1"]["n"], 2)
        self.assertEqual([row["run_id"] for row in by_id["S1"]["runs"]], ["R001", "R002"])
        self.assertEqual(by_id["S1"]["period"], "2026-01-01 - 2026-02-01")
        self.assertEqual(by_id["S1"]["grades"], "A -> B")
        self.assertEqual(by_id["S1"]["objective"], "Long objective")
        self.assertEqual(by_id["S9"]["n"], 0)

    def test_compress_sequence_removes_adjacent_duplicates(self):
        self.assertEqual(compress_sequence(["A", "A", "B", "B", "A"]), "A -> B -> A")
        self.assertEqual(compress_sequence([]), "-")

    def test_save_series_rows_writes_backup(self):
        rows, fields, mtime = load_series_table(config.RECORDS_CSV)
        rows.append({"series_id": "S1", "objective": "A"})
        mtime = save_series_rows(config.RECORDS_CSV, rows, fields, mtime)
        rows[0]["objective"] = "B"
        save_series_rows(config.RECORDS_CSV, rows, fields, mtime)

        loaded, _fields, _mtime = load_series_table(config.RECORDS_CSV)
        self.assertEqual(loaded[0]["objective"], "B")
        backups = list((Path(self.temp_dir.name) / "backup").glob("series-*.csv"))
        self.assertTrue(backups)


if __name__ == "__main__":
    unittest.main()
