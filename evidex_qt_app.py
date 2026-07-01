#!/usr/bin/env python3
"""Experimental Qt entry point for Evidex."""

import traceback


def _consume_data_arg(argv):
    for index, arg in enumerate(list(argv)):
        if arg == "--data":
            if index + 1 >= len(argv):
                raise SystemExit("--data requires a directory")
            value = argv[index + 1]
            del argv[index:index + 2]
            return value
        if arg.startswith("--data="):
            value = arg.split("=", 1)[1]
            del argv[index]
            return value
    return None


def main():
    try:
        import sys
        from evidex.core import config

        config.set_base_dir(config.resolve_base_dir(_consume_data_arg(sys.argv)))

        from evidex.qt_app import run
        return run()
    except ModuleNotFoundError as error:
        if error.name == "PySide6":
            print(
                "PySide6 is not installed.\n"
                "Install it with:\n"
                "  python -m pip install PySide6\n"
                "\n"
                "The current Tkinter app still starts with:\n"
                "  python evidex_app.py"
            )
            return 1
        raise
    except Exception:
        traceback.print_exc()
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication([])
            QMessageBox.critical(
                None,
                "Evidex Qt Startup Error",
                "Qt版の起動中にエラーが発生しました。\n\n"
                "PowerShellに表示されたTracebackをCodexへ送ってください。",
            )
            app.quit()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
