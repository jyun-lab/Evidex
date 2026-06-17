import csv
import sys
import os
import shutil
from pathlib import Path

from evidex.core import config
from evidex.core.fields import RUN_FIELDS, STEP_FIELDS, SERIES_FIELDS

def _read_csv_rows(path):
    """台帳CSVを読む。utf-8-sig→cp932 の順で試す(Excel保存のCP932対策)。
    どちらでも読めなければ最後の例外を投げる。"""
    last = None
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rd = csv.DictReader(f)
                return list(rd), list(rd.fieldnames or [])
        except UnicodeDecodeError as e:
            last = e
    raise last

def load(path):
    rows, _ = _read_csv_rows(path)
    return rows

def load_with_header(path):
    return _read_csv_rows(path)

def load_steps_with_header(runs_path):
    sp = Path(runs_path).parent / "steps.csv"
    if not sp.exists():
        return {}, []
    rows, fields = _read_csv_rows(sp)
    d = {}
    for r in rows:
        d.setdefault(r.get("run_id", ""), []).append(r)
    for v in d.values():
        v.sort(key=lambda r: float(r.get("step_no", "") or 0) if r.get("step_no", "") else 0)
    return d, fields

def ensure_initial_csv_files(base_dir=None):
    if base_dir is None:
        base_dir = config._base_dir()
    else:
        base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    specs = [("runs.csv", RUN_FIELDS),
             ("steps.csv", STEP_FIELDS),
             ("series.csv", SERIES_FIELDS)]
    created = []
    for name, fields in specs:
        p = base_dir / name
        if not p.exists():
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                csv.DictWriter(f, fieldnames=fields).writeheader()
            created.append(name)
    return created

def extract_bundled_assets(base_dir=None):
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return []
    if base_dir is None:
        base_dir = config._base_dir()
    else:
        base_dir = Path(base_dir)
    src_dir = Path(meipass)
    copied = []
    for name in config.BUNDLED_ASSETS:
        dst = base_dir / name
        src = src_dir / name
        if dst.exists() or not src.exists():
            continue
        try:
            shutil.copy2(src, dst)
            copied.append(name)
        except OSError:
            pass
    return copied

def parse_device_csv(path):
    from evidex.packs import active_pack
    sig = active_pack().parse(path)
    res = {"t_min": sig.x.values}
    for c in sig.channels:
        res[c.name] = c.values
    return res
