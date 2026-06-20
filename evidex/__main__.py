"""Entry point for ``python -m evidex``.

Usage:
    python -m evidex          # auto-detect (Qt if available, else tkinter)
    python -m evidex --qt     # force Qt
    python -m evidex --tk     # force tkinter
"""
import sys


def main():
    backend = "auto"
    if "--qt" in sys.argv:
        sys.argv.remove("--qt")
        backend = "qt"
    elif "--tk" in sys.argv:
        sys.argv.remove("--tk")
        backend = "tk"

    if backend == "qt" or (backend == "auto" and _qt_available()):
        from evidex.qt_app import run
        run(sys.argv)
    else:
        from evidex.main import App
        App().mainloop()


def _qt_available():
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
