import os
from pathlib import Path
from typing import Set

BACKUP_KEEP = 100
_BACKUP_PAT = ("runs-*.csv", "steps-*.csv", "series-*.csv")

def prune_backups(bdir: Path):
    try:
        cands = []
        for pat in _BACKUP_PAT:
            cands.extend(bdir.glob(pat))
        cands.sort(key=lambda p: p.stat().st_mtime)
        while len(cands) > BACKUP_KEEP:
            try:
                cands.pop(0).unlink()
            except OSError:
                pass
    except Exception:
        pass
