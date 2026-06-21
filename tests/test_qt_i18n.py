import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
QT_APP = ROOT / "evidex" / "qt_app"
JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")

IMPORT_TARGETS = {
    "main_window.py",
    "detail.py",
    "filtering.py",
    "table_view.py",
    "record_ops.py",
    "record_dialog.py",
    "widgets.py",
    "waveform.py",
    "steps_dialog.py",
    "series_dialog.py",
    "popout.py",
    "theming.py",
    "schema_editor_dialog.py",
    "schema_fields.py",
    "schema_display.py",
}


def _docstring_ids(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                result.add(id(node.body[0].value))
    return result


class QtI18nTests(unittest.TestCase):
    def test_qt_ui_has_no_hardcoded_japanese_string_literals(self):
        violations = []
        for path in QT_APP.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = _docstring_ids(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docstrings
                    and JP_RE.search(node.value)
                ):
                    violations.append((path.name, node.lineno, node.value))
        self.assertEqual([], violations)

    def test_target_qt_modules_import_t(self):
        missing = []
        for name in IMPORT_TARGETS:
            tree = ast.parse((QT_APP / name).read_text(encoding="utf-8"))
            imported = any(
                isinstance(node, ast.ImportFrom)
                and node.module == "evidex.core.i18n"
                and any(alias.name == "t" for alias in node.names)
                for node in tree.body
            )
            if not imported:
                missing.append(name)
        self.assertEqual([], sorted(missing))

    def test_qt_translation_keys_exist_in_both_locales(self):
        locale_dir = ROOT / "evidex" / "locales"
        en = json.loads((locale_dir / "en.json").read_text(encoding="utf-8"))
        ja = json.loads((locale_dir / "ja.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(ja))

        missing = []
        for path in QT_APP.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "t"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    continue
                key = node.args[0].value
                if key not in en or key not in ja:
                    missing.append((path.name, node.lineno, key))
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
