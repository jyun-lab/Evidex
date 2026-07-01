import sys
import os
from pathlib import Path


LAST_DIR_FILE = Path.home() / ".evidex" / "last_dir.txt"


def _base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / "pyproject.toml").exists() or (candidate / "evidex_app.py").exists():
        return candidate
    return Path.home() / "Evidex"


def _read_last_dir():
    try:
        if not LAST_DIR_FILE.exists():
            return None
        value = LAST_DIR_FILE.read_text(encoding="utf-8").splitlines()[0].strip()
        if not value:
            return None
        path = Path(value).expanduser()
        if path.exists():
            return path
    except Exception:
        return None
    return None


def save_last_dir(path):
    try:
        from evidex.core.fsio import atomic_write

        LAST_DIR_FILE.parent.mkdir(parents=True, exist_ok=True)
        with atomic_write(LAST_DIR_FILE, encoding="utf-8") as handle:
            handle.write(str(Path(path).expanduser()))
            handle.write("\n")
        return True
    except Exception:
        return False


def resolve_base_dir(argv_data=None):
    if argv_data:
        return Path(argv_data).expanduser()
    env_home = os.environ.get("EVIDEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    last_dir = _read_last_dir()
    if last_dir is not None:
        return last_dir
    return _base_dir()


def set_base_dir(path):
    global RECORDS_CSV
    base_dir = Path(path).expanduser()
    RECORDS_CSV = base_dir / "runs.csv"
    return base_dir


RECORDS_CSV = resolve_base_dir() / "runs.csv"
DEFAULT_PACK = "generic_ts"
BUNDLED_ASSETS = ["README.md"]
_UI_FONT_CANDIDATES = [
    "Yu Gothic UI", "Meiryo UI", "Noto Sans CJK JP",
    "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN",
    "BIZ UDPGothic", "Meiryo", "Arial"
]
