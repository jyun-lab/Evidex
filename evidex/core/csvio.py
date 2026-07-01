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
        base_dir = config.RECORDS_CSV.parent
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
        base_dir = config.RECORDS_CSV.parent
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

    # Extract demo data on first run
    demo_src = src_dir / "demo"
    if demo_src.is_dir():
        # Demo CSV files (runs.csv, steps.csv, series.csv)
        for csv_name in ("runs.csv", "steps.csv", "series.csv"):
            src = demo_src / csv_name
            dst = base_dir / csv_name
            if dst.exists() or not src.exists():
                continue
            try:
                shutil.copy2(src, dst)
                copied.append(csv_name)
            except OSError:
                pass

        # Demo directories (signals/, images/)
        for dir_name in ("signals", "images"):
            src = demo_src / dir_name
            dst = base_dir / dir_name
            if dst.exists() or not src.is_dir():
                continue
            try:
                shutil.copytree(src, dst)
                copied.append(f"{dir_name}/")
            except OSError:
                pass

        # Demo packs (merge into packs/ without overwriting existing)
        demo_packs = demo_src / "packs"
        if demo_packs.is_dir():
            dst_packs = base_dir / "packs"
            dst_packs.mkdir(exist_ok=True)
            for pack_dir in demo_packs.iterdir():
                if pack_dir.is_dir():
                    dst_pack = dst_packs / pack_dir.name
                    if not dst_pack.exists():
                        try:
                            shutil.copytree(pack_dir, dst_pack)
                            copied.append(f"packs/{pack_dir.name}/")
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
