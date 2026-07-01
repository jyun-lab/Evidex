"""Entry point for ``python -m evidex``.

Usage:
    python -m evidex          # auto-detect (Qt if available, else tkinter)
    python -m evidex --qt     # force Qt
    python -m evidex --tk     # force tkinter
"""
import sys


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
    data_dir = _consume_data_arg(sys.argv)
    from evidex.core import config

    config.set_base_dir(config.resolve_base_dir(data_dir))

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
