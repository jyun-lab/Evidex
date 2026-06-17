import sys
import os
from pathlib import Path

def _base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

RECORDS_CSV = _base_dir() / "runs.csv"
DEFAULT_PACK = "generic_ts"
BUNDLED_ASSETS = ["README.md"]
_UI_FONT_CANDIDATES = [
    "Yu Gothic UI", "Meiryo UI", "Noto Sans CJK JP",
    "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN",
    "BIZ UDPGothic", "Meiryo", "Arial"
]
