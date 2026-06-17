import tkinter as tk
import unittest

from evidex.views.run_editor import FileListEditor


class FakeApp:
    def __init__(self, selected=None):
        self.selected = selected or []

    def choose_file_paths(self, parent):
        return list(self.selected)


class RunEditorLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_file_list_editor_shows_filenames_and_saves_joined_paths(self):
        app = FakeApp(["signals/b.csv", "figures/result.png"])
        editor = FileListEditor(
            self.root,
            app,
            "signals/a.csv; C:/data/long/path/photo.jpg",
        )
        editor.pack()
        self.root.update_idletasks()

        self.assertEqual(editor.listbox.get(0), "a.csv")
        self.assertEqual(editor.listbox.get(1), "photo.jpg")

        editor.add_files()
        self.assertEqual(
            editor.get(),
            "signals/a.csv; C:/data/long/path/photo.jpg; "
            "signals/b.csv; figures/result.png",
        )

        editor.listbox.selection_clear(0, "end")
        editor.listbox.selection_set(1)
        editor.remove_selected()
        self.assertEqual(
            editor.get(),
            "signals/a.csv; signals/b.csv; figures/result.png",
        )


if __name__ == "__main__":
    unittest.main()
