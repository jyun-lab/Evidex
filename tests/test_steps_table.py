import csv
import re
import tempfile
import unittest
from pathlib import Path

from evidex.core import config
from evidex.core.fields import STEP_FIELDS, STEP_FORM
from evidex.core.i18n import t
from evidex.core.steps_table import (
    load_steps_table,
    save_steps_table,
    validate_step_update,
)


class StepsTableTests(unittest.TestCase):
    def setUp(self):
        self.original_records_csv = config.RECORDS_CSV
        self.temp_dir = tempfile.TemporaryDirectory()
        config.RECORDS_CSV = Path(self.temp_dir.name) / "runs.csv"

    def tearDown(self):
        config.RECORDS_CSV = self.original_records_csv
        self.temp_dir.cleanup()

    def test_load_steps_table_groups_and_sorts_by_step_no(self):
        steps_csv = Path(self.temp_dir.name) / "steps.csv"
        with steps_csv.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=STEP_FIELDS)
            writer.writeheader()
            writer.writerow({"run_id": "R001", "step_no": "2", "action": "B"})
            writer.writerow({"run_id": "R001", "step_no": "1", "action": "A"})

        steps, fields, mtime = load_steps_table(config.RECORDS_CSV)

        self.assertEqual(fields, STEP_FIELDS)
        self.assertIsNotNone(mtime)
        self.assertEqual([row["action"] for row in steps["R001"]], ["A", "B"])

    def test_save_steps_table_writes_backup_and_keeps_required_fields(self):
        steps, fields, mtime = load_steps_table(config.RECORDS_CSV)
        steps["R001"] = [
            {"run_id": "R001", "step_no": "1", "action": "A"},
        ]
        mtime = save_steps_table(config.RECORDS_CSV, steps, fields, mtime)
        steps["R001"][0]["action"] = "B"
        save_steps_table(config.RECORDS_CSV, steps, fields, mtime)

        loaded, loaded_fields, _mtime = load_steps_table(config.RECORDS_CSV)
        self.assertEqual(loaded["R001"][0]["action"], "B")
        for field in STEP_FIELDS:
            self.assertIn(field, loaded_fields)
        backups = list((Path(self.temp_dir.name) / "backup").glob("steps-*.csv"))
        self.assertTrue(backups)

    def test_validate_step_update_rejects_invalid_numeric_values(self):
        if "data_start_row" not in STEP_FIELDS or "data_end_row" not in STEP_FIELDS:
            self.skipTest("current pack has no data row fields")
        step = {"action": "A", "data_start_row": "10", "data_end_row": "3"}

        with self.assertRaisesRegex(
            ValueError,
            re.escape(t("steps.validation.start_must_le_end")),
        ):
            validate_step_update(step)

    def test_validate_step_update_rejects_missing_primary_field(self):
        if not STEP_FORM:
            self.skipTest("current pack has no step form fields")
        primary = STEP_FORM[0][0]

        with self.assertRaises(ValueError):
            validate_step_update({primary: ""})


if __name__ == "__main__":
    unittest.main()
