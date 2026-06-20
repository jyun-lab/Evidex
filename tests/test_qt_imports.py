import unittest


try:
    import PySide6  # noqa: F401

    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 not installed")
class TestQtImports(unittest.TestCase):
    """Qt版モジュールのimport整合性テスト。"""

    def test_import_qt_app_run(self):
        from evidex.qt_app import run

        self.assertTrue(callable(run))

    def test_import_main_window(self):
        from evidex.qt_app.main_window import EvidexQtWindow

        self.assertTrue(callable(EvidexQtWindow))

    def test_import_widgets(self):
        from evidex.qt_app.widgets import (
            ElidingButton,
            FilePathEditor,
            ScrollSafeComboBox,
        )

        self.assertTrue(callable(ScrollSafeComboBox))
        self.assertTrue(callable(ElidingButton))
        self.assertTrue(callable(FilePathEditor))

    def test_import_theme(self):
        from evidex.qt_app.theme import _DARK, _LIGHT

        self.assertIsInstance(_LIGHT, dict)
        self.assertIsInstance(_DARK, dict)

    def test_import_dialogs(self):
        from evidex.qt_app.dialogs import (
            RecordEditDialog,
            SeriesManagerDialog,
            StepsEditorDialog,
        )

        self.assertTrue(callable(RecordEditDialog))
        self.assertTrue(callable(StepsEditorDialog))
        self.assertTrue(callable(SeriesManagerDialog))

    def test_import_waveform(self):
        from evidex.qt_app.waveform import (
            RawDataPreviewWidget,
            SignalPlotWidget,
        )

        self.assertTrue(callable(SignalPlotWidget))
        self.assertTrue(callable(RawDataPreviewWidget))

    def test_import_popout(self):
        from evidex.qt_app.popout import DetailPopoutWindow

        self.assertTrue(callable(DetailPopoutWindow))

    def test_import_schema_editor_dialog(self):
        from evidex.qt_app.schema_editor_dialog import open_schema_editor_dialog

        self.assertTrue(callable(open_schema_editor_dialog))


if __name__ == "__main__":
    unittest.main()
