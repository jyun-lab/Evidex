import tempfile
import unittest
from pathlib import Path

from evidex.core.csv_preview import load_csv_preview


class CsvPreviewTests(unittest.TestCase):
    def test_load_csv_preview_reads_header_and_limited_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.csv"
            path.write_text(
                "time,temperature,pressure\n"
                "0,20,100\n"
                "1,21,101\n"
                "2,22,102\n",
                encoding="utf-8-sig",
            )

            preview = load_csv_preview(path, max_rows=2)

        self.assertEqual(preview.header, ["time", "temperature", "pressure"])
        self.assertEqual(preview.rows, [["0", "20", "100"], ["1", "21", "101"]])
        self.assertEqual(preview.total_rows, 3)
        self.assertEqual(preview.delimiter, ",")

    def test_load_csv_preview_rejects_empty_header_cell(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.csv"
            path.write_text("time,\n0,1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "empty column"):
                load_csv_preview(path)


if __name__ == "__main__":
    unittest.main()
