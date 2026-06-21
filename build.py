#!/usr/bin/env python3
"""Build the Evidex Windows executable with PyInstaller.

Run from the repository root:

    python -m pip install pyinstaller ttkbootstrap matplotlib
    python build.py

Use --qt to build the Qt version and --version to include a version in the
executable name. Build artifacts are intentionally excluded from Git.
"""
import argparse
import os
import subprocess
import sys

from evidex.core.windows import read_ico_sizes

HERE = os.path.dirname(os.path.abspath(__file__))
SEP = ";" if os.name == "nt" else ":"

parser = argparse.ArgumentParser(description="Build Evidex Windows executable")
parser.add_argument(
    "--qt",
    action="store_true",
    help="Build Qt version instead of tkinter",
)
parser.add_argument(
    "--version",
    default=None,
    help="Version string for exe name (e.g. 1.0.0)",
)
args = parser.parse_args()

if args.qt:
    entry_point = os.path.join(HERE, "evidex_qt_app.py")
    exe_name = "Evidex-Qt"
    hidden_imports = []
else:
    entry_point = os.path.join(HERE, "evidex_app.py")
    exe_name = "Evidex"
    hidden_imports = ["PIL._tkinter_finder"]

if args.version:
    exe_name = f"{exe_name}-{args.version}"


def fail(message):
    print(f"[ERROR] {message}")
    raise SystemExit(1)


# A GUI build without Tcl/Tk produces an EXE that exits immediately. Detect that
# before PyInstaller overwrites a previously working build.
if not args.qt:
    try:
        import tkinter as tk

        tcl = tk.Tcl()
        tcl.eval("info patchlevel")
    except Exception as exc:
        fail(
            "This Python installation does not include a usable Tcl/Tk. "
            "Install Python from python.org with the optional Tcl/Tk component, "
            f"then run build.py again. Details: {exc}"
        )

ADD_DATA = ["README.md"]
LEGACY_FILES = {
    "ledger_app.html",
    "ledger.py",
    "ledger_setup.py",
    "run_setup.bat",
    "build_exe.bat",
}
legacy_included = LEGACY_FILES.intersection(ADD_DATA)
if legacy_included:
    fail(f"Legacy files must not be bundled: {sorted(legacy_included)}")

ICON = os.path.join(HERE, "evidex", "assets", "evidex.ico")
if not os.path.exists(ICON):
    fail(f"Icon file was not found: {ICON}")

try:
    icon_sizes = read_ico_sizes(ICON)
except (OSError, ValueError) as exc:
    fail(f"Icon file is invalid: {exc}")

required_icon_sizes = {16, 32, 48, 256}
missing_icon_sizes = required_icon_sizes - icon_sizes
if missing_icon_sizes:
    fail(f"Icon file is missing required sizes: {sorted(missing_icon_sizes)}")

cmd = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--onefile",
    "--noconsole",
    "--name",
    exe_name,
    "--icon",
    ICON,
]

for hidden_import in hidden_imports:
    cmd += ["--hidden-import", hidden_import]

for name in ADD_DATA:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        fail(f"Bundled data file was not found: {name}")
    cmd += ["--add-data", f"{path}{SEP}."]

cmd += ["--add-data", f"{ICON}{SEP}evidex{os.sep}assets"]
cmd += [
    "--add-data",
    f"{os.path.join(HERE, 'evidex', 'packs')}{SEP}evidex{os.sep}packs",
]
cmd += [
    "--add-data",
    f"{os.path.join(HERE, 'evidex', 'locales')}{SEP}evidex{os.sep}locales",
]
cmd.append(entry_point)

print("Running:", " ".join(cmd))
raise SystemExit(subprocess.call(cmd))
