import os
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401

    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 not installed")
class TestQtWidgets(unittest.TestCase):
    """画面を表示せずに行うQtウィジェットの基本テスト。"""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_scroll_safe_combo_box_can_be_created(self):
        from evidex.qt_app.widgets import ScrollSafeComboBox

        widget = ScrollSafeComboBox()
        try:
            self.assertIsInstance(widget, ScrollSafeComboBox)
        finally:
            widget.deleteLater()
            self.app.processEvents()

    def test_eliding_button_can_set_text(self):
        from evidex.qt_app.widgets import ElidingButton

        button = ElidingButton()
        try:
            text = "A long experiment record title"
            button.setText(text)

            self.assertEqual(button._full_text, text)
            self.assertEqual(button.toolTip(), text)
        finally:
            button.deleteLater()
            self.app.processEvents()

    def test_theme_dictionaries_have_required_keys(self):
        from evidex.qt_app.theme import _DARK, _LIGHT

        required_keys = {
            "bg",
            "bg_alt",
            "bg_surface",
            "text",
            "text_muted",
            "border",
            "border_light",
            "header_bg",
            "nav_bg",
            "nav_border",
            "selection",
            "selection_text",
            "selection_border",
            "selection_inactive",
            "hover",
            "link",
            "grade_row",
        }
        for theme in (_LIGHT, _DARK):
            with self.subTest(theme=theme):
                self.assertTrue(required_keys <= theme.keys())
                self.assertEqual(set(theme["grade_row"]), {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
