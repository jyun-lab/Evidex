from pathlib import Path

BACKUP_KEEP = 100
_BACKUP_PAT = ("runs-*.csv", "steps-*.csv", "series-*.csv")


def _is_backup_candidate(path: Path, bdir: Path, prefix: str):
    return (
        path.parent == bdir
        and path.suffix == ".csv"
        and path.name.startswith(prefix)
    )


def prune_backups(bdir: Path):
    try:
        for pat in _BACKUP_PAT:
            try:
                prefix = pat.split("*", 1)[0]
                cands = [
                    path for path in bdir.glob(pat)
                    if _is_backup_candidate(path, bdir, prefix)
                ]
                cands.sort(key=lambda p: p.stat().st_mtime)
                for path in cands[:-BACKUP_KEEP]:
                    try:
                        if _is_backup_candidate(path, bdir, prefix):
                            path.unlink()
                    except OSError:
                        pass
            except Exception:
                pass
    except Exception:
        pass
