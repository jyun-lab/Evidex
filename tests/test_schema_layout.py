import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from evidex.core import config
from evidex.views.schema_editor import _blank_schema, open_schema_editor, save_user_pack


class SchemaEditorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.original_records_csv = config.RECORDS_CSV
        self.temp_dir = tempfile.TemporaryDirectory()
        config.RECORDS_CSV = Path(self.temp_dir.name) / "runs.csv"
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temp_dir.cleanup()
            self.skipTest(str(error))
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()
        config.RECORDS_CSV = self.original_records_csv
        self.temp_dir.cleanup()

    def test_controls_remain_visible_at_minimum_size(self):
        editor = open_schema_editor(self.root)
        editor.geometry("680x500")
        editor.update_idletasks()
        editor.update()

        window_right = editor.winfo_rootx() + editor.winfo_width()
        window_bottom = editor.winfo_rooty() + editor.winfo_height()

        for button in editor._schema_editor_pack_buttons:
            self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
            self.assertLessEqual(
                button.winfo_rootx() + button.winfo_width(), window_right
            )

        save_button = editor._schema_editor_save_button
        self.assertLessEqual(
            save_button.winfo_rooty() + save_button.winfo_height(), window_bottom
        )
        self.assertTrue(editor._schema_editor_field_hscroll.winfo_ismapped())
        self.assertGreater(editor._schema_editor_field_tree.winfo_width(), 0)
        self.assertEqual(
            editor._schema_editor_current_pack.get(), "generic_ts"
        )
        self.assertIn(
            "generic_ts",
            editor._schema_editor_pack_selector.cget("values"),
        )
        self.assertEqual(
            editor._schema_editor_selected_pack_label.cget("font"), ""
        )
        self.assertEqual(len(editor._schema_editor_page_canvases), 3)
        self.assertEqual(len(editor._schema_editor_page_scrollbars), 3)
        self.assertTrue(
            editor._schema_editor_page_scrollbars[0].winfo_ismapped()
        )
        fields_canvas = editor._schema_editor_page_canvases[0]
        self.assertGreaterEqual(
            fields_canvas.bbox("all")[3],
            fields_canvas.winfo_height(),
        )
        if fields_canvas.yview() != (0.0, 1.0):
            fields_canvas.yview_moveto(1.0)
            editor.update_idletasks()
            editor.update()
            apply_button = editor._schema_editor_apply_field_button
            canvas_bottom = (
                fields_canvas.winfo_rooty() + fields_canvas.winfo_height()
            )
            self.assertLessEqual(
                apply_button.winfo_rooty() + apply_button.winfo_height(),
                canvas_bottom,
            )

        editor._schema_editor_notebook.select(
            editor._schema_editor_adapter_tab
        )
        editor.update_idletasks()
        editor.update()
        self.assertTrue(
            editor._schema_editor_page_scrollbars[1].winfo_ismapped()
        )
        self.assertTrue(
            editor._schema_editor_choose_csv_button.winfo_ismapped()
        )
        self.assertGreater(
            editor._schema_editor_x_column_box.winfo_width(), 0
        )
        self.assertEqual(
            editor._schema_editor_adapter_mapping_layout.get(),
            "stacked",
        )
        self.assertTrue(editor._schema_editor_x_axis_frame.winfo_ismapped())
        self.assertLess(
            editor._schema_editor_x_axis_frame.winfo_rooty(),
            editor._schema_editor_channel_frame.winfo_rooty(),
        )
        self.assertGreater(
            editor._schema_editor_channel_tree.winfo_width(), 0
        )
        self.assertGreater(
            editor._schema_editor_python_adapter_note.cget("wraplength"), 0
        )
        self.assertTrue(editor._schema_editor_current_settings.winfo_ismapped())
        self.assertIn(
            "X axis",
            editor._schema_editor_current_settings_var.get(),
        )

        editor._schema_editor_notebook.select(0)
        editor.update_idletasks()
        editor.update()
        self.assertTrue(editor._schema_editor_field_intro.winfo_ismapped())
        self.assertIn(
            editor._schema_editor_field_type_box.get(),
            editor._schema_editor_field_type_box.cget("values"),
        )
        self.assertTrue(
            editor._schema_editor_field_type_help.cget("text")
        )

        editor._schema_editor_notebook.select(2)
        editor.update_idletasks()
        editor.update()
        self.assertTrue(
            editor._schema_editor_page_scrollbars[2].winfo_ismapped()
        )
        self.assertTrue(editor._schema_editor_display_tabs.winfo_ismapped())

        editor.destroy()

    def test_custom_python_adapter_disables_csv_mapping_controls(self):
        pack_dir = save_user_pack(
            "custom_reader",
            _blank_schema(),
            None,
            {"facets": [], "GCOL": {}},
        )
        (pack_dir / "adapter.py").write_text(
            "def parse(path):\n"
            "    raise RuntimeError('not used in this layout test')\n",
            encoding="utf-8",
        )

        editor = open_schema_editor(self.root)
        editor._schema_editor_current_pack.set("custom_reader")
        editor._schema_editor_pack_selector.event_generate("<<ComboboxSelected>>")
        editor.update_idletasks()
        editor.update()

        self.assertIn(
            "adapter.py",
            editor._schema_editor_current_settings_var.get(),
        )
        self.assertEqual(
            editor._schema_editor_choose_csv_button.cget("state"),
            "disabled",
        )
        self.assertEqual(
            editor._schema_editor_reload_columns_button.cget("state"),
            "disabled",
        )
        self.assertEqual(
            editor._schema_editor_apply_adapter_button.cget("state"),
            "disabled",
        )
        self.assertEqual(
            editor._schema_editor_test_adapter_button.cget("state"),
            "disabled",
        )
        self.assertEqual(
            editor._schema_editor_x_column_box.cget("state"),
            "disabled",
        )

        editor.destroy()


if __name__ == "__main__":
    unittest.main()
