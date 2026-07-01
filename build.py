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

from evidex import __version__
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
    nargs="?",
    const=__version__,
    default=None,
    help="Version string for exe name (defaults to package version when omitted)",
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

ADD_DATA = ["README.md", "LICENSE"]

# Qt builds: bundle PySide6 LGPL license notice
if args.qt:
    ADD_DATA.append("CHANGELOG.md")
    try:
        import PySide6

        pyside6_dir = os.path.dirname(PySide6.__file__)
        for license_name in ("LICENSES", "licenses"):
            license_dir = os.path.join(pyside6_dir, license_name)
            if os.path.isdir(license_dir):
                break
        else:
            # Fall back: include the single license file if present
            for candidate in (
                os.path.join(pyside6_dir, "LGPL_EXCEPTION.txt"),
                os.path.join(pyside6_dir, "LICENSE.LGPLv3"),
            ):
                if os.path.exists(candidate):
                    ADD_DATA.append(candidate)
                    break
            license_dir = None

    except ImportError:
        license_dir = None
        print("[WARN] PySide6 not found; LGPL license files not bundled.")

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

# Bundle PySide6 license directory if found
if args.qt and license_dir is not None:
    cmd += ["--add-data", f"{license_dir}{SEP}PySide6_licenses"]

cmd += ["--add-data", f"{ICON}{SEP}evidex{os.sep}assets"]
cmd += [
    "--add-data",
    f"{os.path.join(HERE, 'evidex', 'packs')}{SEP}evidex{os.sep}packs",
]
cmd += [
    "--add-data",
    f"{os.path.join(HERE, 'evidex', 'locales')}{SEP}evidex{os.sep}locales",
]

# Bundle demo data so first-time users can explore immediately
DEMO_DIR = os.path.join(HERE, "examples", "demo")
if os.path.isdir(DEMO_DIR):
    cmd += ["--add-data", f"{DEMO_DIR}{SEP}demo"]
else:
    print("[WARN] examples/demo not found; demo data will not be bundled.")

cmd.append(entry_point)

print("Running:", " ".join(cmd))
raise SystemExit(subprocess.call(cmd))
