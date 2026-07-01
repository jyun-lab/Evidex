from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile


@contextmanager
def atomic_write(path, *, newline=None, encoding="utf-8"):
    """Write to a same-directory temp file and replace the target on success."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", newline=newline, encoding=encoding) as handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
