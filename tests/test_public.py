import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path

from evidex.core import config, settings
from evidex.core.attachments import first_path, join_paths, split_paths
from evidex.core.media import is_image_path
from evidex.core.nocode_adapter import inspect_csv, parse_with_config
from evidex.packs import _discover_user_packs, active_pack, registry
from evidex.packs import PackInterface
from evidex.packs.generic_ts.adapter import parse
from evidex.views.schema_editor import (
    _blank_schema,
    adapter_mapping_layout,
    adapter_summary_lines,
    choose_initial_pack,
    csv_guidance_key,
    save_user_pack,
)


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.original_records_csv = config.RECORDS_CSV
        self.temp_dir = tempfile.TemporaryDirectory()
        config.RECORDS_CSV = Path(self.temp_dir.name) / "runs.csv"

    def tearDown(self):
        config.RECORDS_CSV = self.original_records_csv
        self.temp_dir.cleanup()

    def test_public_build_uses_generic_pack_only(self):
        self.assertEqual(config.DEFAULT_PACK, "generic_ts")
        self.assertEqual(registry, {"generic_ts": "evidex.packs.generic_ts"})
        self.assertEqual(active_pack().name, "generic_ts")

    def test_unknown_pack_falls_back_to_generic(self):
        settings.set("active_pack", "unknown_pack")
        self.assertEqual(active_pack().name, "generic_ts")

    def test_generic_initial_csv_files(self):
        from evidex.core import csvio, fields

        importlib.reload(fields)
        importlib.reload(csvio)
        created = csvio.ensure_initial_csv_files(Path(self.temp_dir.name))
        self.assertEqual(created, ["runs.csv", "steps.csv", "series.csv"])
        with (Path(self.temp_dir.name) / "runs.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            header = next(csv.reader(handle))
        self.assertEqual(
            header,
            [
                "run_id", "date", "title", "experimenter",
                "result_summary", "raw_path", "notes",
            ],
        )

    def test_attachment_path_cells_support_multiple_files(self):
        value = "signals/a.csv; figures/result.png\nnotes.txt; signals/a.csv"
        self.assertEqual(
            split_paths(value),
            ["signals/a.csv", "figures/result.png", "notes.txt"],
        )
        self.assertEqual(first_path(value), "signals/a.csv")
        self.assertEqual(
            join_paths(["a.csv", "b.xlsx", "", "a.csv"]),
            "a.csv; b.xlsx",
        )

    def test_image_attachment_detection_is_extension_based(self):
        self.assertTrue(is_image_path("figures/result.PNG"))
        self.assertTrue(is_image_path("photos/sample.jpeg"))
        self.assertFalse(is_image_path("signals/data.csv"))
        self.assertFalse(is_image_path("notes/readme"))

    def test_generic_time_series_parser(self):
        data_path = Path(self.temp_dir.name) / "signal.csv"
        data_path.write_text(
            "time,signal_a,signal_b\n0,1,2\n1,1.5,2.5\n",
            encoding="utf-8-sig",
        )
        signal = parse(data_path)
        self.assertEqual(signal.x.name, "time")
        self.assertEqual([channel.name for channel in signal.channels],
                         ["signal_a", "signal_b"])

    def test_generic_pack_uses_general_features_and_all_channels(self):
        from evidex.components.waveform import (
            waveform_channels,
            waveform_mode,
        )

        schema = active_pack().schema()
        self.assertFalse(any(schema["features"].values()))
        mode = waveform_mode(schema["waveform"], "all")

        data_path = Path(self.temp_dir.name) / "signal.csv"
        data_path.write_text(
            "time,temperature,pressure\n0,20,100\n1,21,101\n",
            encoding="utf-8-sig",
        )
        signal = parse(data_path)
        self.assertEqual(
            waveform_channels(signal, mode),
            ["temperature", "pressure"],
        )

    def test_local_pack_is_discovered_outside_public_package(self):
        pack_dir = Path(self.temp_dir.name) / "packs" / "private_instrument"
        pack_dir.mkdir(parents=True)
        (pack_dir / "schema.json").write_text(
            json.dumps({
                "RUN_FIELDS": ["run_id"],
                "STEP_FIELDS": ["run_id", "step_no", "action"],
                "SERIES_FIELDS": ["series_id"],
                "COLS": [["run_id", 100]],
                "HEAD": {"run_id": "Run ID"},
                "LONG_FIELDS": [],
                "HIDDEN_EDIT_FIELDS": [],
                "JP_LABEL": {"run_id": "ID"},
                "LABEL_EN": {"run_id": "Run ID"},
                "CHOICES": {},
                "GCOL": {},
                "STEP_FORM": [["action", "Action"]],
                "ACTION_CHOICES": [],
                "MEDIA_SEEDS": [],
                "facets": [],
                "adv_filters": [],
            }),
            encoding="utf-8",
        )
        self.assertIn("private_instrument", _discover_user_packs())

    def test_only_generic_pack_is_in_public_package(self):
        package_dir = Path(__file__).resolve().parent.parent / "evidex" / "packs"
        bundled = sorted(
            path.name for path in package_dir.iterdir()
            if path.is_dir() and (path / "schema.json").is_file()
        )
        self.assertEqual(bundled, ["generic_ts"])

    def test_new_custom_pack_starts_without_specialized_features(self):
        schema = _blank_schema()
        self.assertFalse(any(schema["features"].values()))
        self.assertEqual(schema["waveform"]["default_mode"], "all")
        self.assertEqual(schema["waveform"]["modes"][0]["channels"], "all")

    def test_csv_columns_are_detected_without_programming(self):
        data_path = Path(self.temp_dir.name) / "spectrometer.csv"
        data_path.write_text(
            "Exported by instrument\n"
            "Wavelength;Intensity;Absorbance\n"
            "400;12;0.10\n"
            "500;18;0.15\n",
            encoding="utf-8-sig",
        )
        inspected = inspect_csv(data_path, skip_rows=1)
        self.assertEqual(inspected["delimiter"], ";")
        self.assertEqual(
            inspected["header"],
            ["Wavelength", "Intensity", "Absorbance"],
        )

    def test_nocode_pack_round_trip_preserves_columns_and_units(self):
        data_path = Path(self.temp_dir.name) / "spectrometer.csv"
        data_path.write_text(
            "Wavelength,Intensity,Absorbance\n"
            "400,12,0.10\n"
            "500,18,0.15\n",
            encoding="utf-8-sig",
        )
        adapter = {
            "file_format": "csv",
            "encoding_fallback": ["utf-8-sig", "cp932"],
            "skip_rows": 0,
            "x_column": "Wavelength",
            "x_name": "wavelength",
            "x_unit": "nm",
            "channel_columns": ["Intensity", "Absorbance"],
            "channel_units": ["counts", "AU"],
            "delimiter": ",",
        }
        pack_dir = save_user_pack(
            "spectrometer_demo",
            _blank_schema(),
            adapter,
            {"facets": [], "GCOL": {}},
        )
        signal = PackInterface(
            "spectrometer_demo", user_path=str(pack_dir)
        ).parse(data_path)
        self.assertEqual(signal.x.unit, "nm")
        self.assertEqual(
            [channel.name for channel in signal.channels],
            ["Intensity", "Absorbance"],
        )
        self.assertEqual(
            [channel.unit for channel in signal.channels],
            ["counts", "AU"],
        )
        self.assertEqual(signal.channels[0].values, [12.0, 18.0])

    def test_nocode_parser_rejects_non_numeric_selection(self):
        data_path = Path(self.temp_dir.name) / "labels.csv"
        data_path.write_text(
            "time,label\nzero,low\none,high\n",
            encoding="utf-8-sig",
        )
        with self.assertRaisesRegex(ValueError, "No numeric data"):
            parse_with_config(
                data_path,
                {
                    "x_column": "time",
                    "channel_columns": ["label"],
                    "delimiter": ",",
                },
            )

    def test_pack_manager_beginner_labels_are_clear(self):
        from evidex.core import i18n

        original = settings.get("language")
        try:
            settings.set("language", "ja")
            i18n._LOCALE = None
            self.assertEqual(i18n.t("schema_editor.str3"), "記録項目")
            self.assertEqual(
                i18n.t("schema_editor.str13"), "入力方法:"
            )
            self.assertEqual(
                i18n.t("schema_editor.channel_settings"),
                "グラフに表示する列（縦軸）",
            )
            note = i18n.t("schema_editor.csv_guidance_template")
            self.assertIn("新しいパックを作るためのひな形", note)
            self.assertIn("複製", note)
            self.assertIn(
                "分からない機能はオフ",
                i18n.t("schema_editor.display_intro"),
            )
        finally:
            settings.set("language", original)
            i18n._LOCALE = None

    def test_csv_guidance_changes_by_pack_type(self):
        self.assertEqual(
            csv_guidance_key("generic_ts", True),
            "schema_editor.csv_guidance_template",
        )
        self.assertEqual(
            csv_guidance_key("instrument_pack", True),
            "schema_editor.csv_guidance_custom_reader",
        )
        self.assertEqual(
            csv_guidance_key("configured_pack", False),
            "schema_editor.csv_guidance_column_settings",
        )

    def test_csv_mapping_layout_changes_with_width(self):
        self.assertEqual(adapter_mapping_layout(500), "stacked")
        self.assertEqual(adapter_mapping_layout(620), "columns")
        self.assertEqual(adapter_mapping_layout(900), "columns")

    def test_adapter_summary_shows_saved_csv_and_waveform_settings(self):
        lines = adapter_summary_lines({
            "skip_rows": 2,
            "x_column": "Time",
            "x_name": "elapsed",
            "x_unit": "s",
            "channel_columns": ["Voltage", "Current"],
            "channel_units": ["V", "A"],
            "delimiter": "\t",
        })
        self.assertEqual(lines[0][0], "schema_editor.current_x_axis")
        self.assertEqual(lines[0][1]["column"], "Time")
        self.assertIn("Voltage [V]", lines[1][1]["channels"])
        self.assertEqual(lines[2][1]["skip_rows"], 2)
        self.assertEqual(lines[2][1]["delimiter"], "\\t")
        self.assertEqual(
            adapter_summary_lines({}, has_python_adapter=True),
            [
                "schema_editor.current_reader_custom",
                "schema_editor.current_reader_custom_location",
                "schema_editor.current_reader_custom_mapping",
            ],
        )
        self.assertEqual(
            adapter_summary_lines({"skip_rows": 0, "delimiter": ","}),
            [
                "schema_editor.current_settings_incomplete",
                "schema_editor.current_settings_next_steps",
            ],
        )

    def test_pack_manager_opens_the_active_pack(self):
        names = ["generic_ts", "shsaw"]
        self.assertEqual(
            choose_initial_pack(names, active_name="shsaw"),
            "shsaw",
        )
        self.assertEqual(
            choose_initial_pack(
                names, selected_name="generic_ts", active_name="shsaw"
            ),
            "generic_ts",
        )


if __name__ == "__main__":
    unittest.main()
