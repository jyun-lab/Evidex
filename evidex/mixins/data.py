import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import csv
import shutil
import json
import subprocess
import datetime
from pathlib import Path
import threading
from ..core import config
from ..core.fields import RUN_FIELDS, STEP_FIELDS, SERIES_FIELDS, COLS, HEAD, LONG_FIELDS, JP_LABEL, CHOICES, GCOL, STEP_FORM, ACTION_CHOICES, MEDIA_SEEDS, HIDDEN_EDIT_FIELDS
from ..core.backup import prune_backups
from ..core.attachments import join_paths, split_paths
from ..core.csvio import ensure_initial_csv_files, parse_device_csv, load_with_header, load_steps_with_header, STEP_FIELDS, SERIES_FIELDS
from ..core.filtering import norm, fnum, row_matches
from ..core.fsio import atomic_write
from ..core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame
from ..core.i18n import t

class DataMixin:
    def _load(self, path):
        self.path = Path(path)
        if not self.path.exists():
            messagebox.showerror(t("msg.error"), t("data.msg.not_found", path=self.path))
            return
        try:
            self.rows, self.fields = load_with_header(self.path)
            if self.has_feature("baseline") and "base_row" not in self.fields:
                self.fields.append("base_row")
            self.steps, self.step_fields = load_steps_with_header(self.path)
            spath = self.path.parent / "series.csv"
            if spath.exists():
                self.series_rows, self.series_fields = load_with_header(spath)
            else:
                self.series_rows = []
                self.series_fields = list(SERIES_FIELDS)
            self.mtime = self.path.stat().st_mtime
        except Exception as e:
            messagebox.showerror(t("data.msg.read_error"), str(e))
            return
        self.title(t("data.title.main", name=self.path.name))
        st = sorted({r.get("status", "") for r in self.rows if r.get("status")})
        if getattr(self, "status", None) is not None:
            self.status.config(values=[""] + st)
        self.update_liquid_choices()
        self.update_series_choices()
        self.update_action_choices()
        self.build_nav()
        self.search()

    def open_file(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if p:
            self._load(p)

    def save_evidence(self):
        """バックアップ→書き戻し。Excel等で並行変更されていたら警告。"""
        if self.path.exists() and abs(self.path.stat().st_mtime - self.mtime) > 1e-6:
            if not messagebox.askyesno(
                    t("data.msg.conflict_title"),
                    t("data.msg.conflict")):
                return False
        bdir = self.path.parent / "backup"
        bdir.mkdir(exist_ok=True)
        if self.path.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(self.path, bdir / f"runs-{stamp}.csv")
            prune_backups(bdir)
        with atomic_write(self.path, newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=self.fields)
            w.writeheader()
            for r in self.rows:
                w.writerow({k: r.get(k, "") for k in self.fields})
        self.mtime = self.path.stat().st_mtime
        st = sorted({r.get("status", "") for r in self.rows if r.get("status")})
        if getattr(self, "status", None) is not None:
            self.status.config(values=[""] + st)
        return True

    def apply_edit(self, row, out, is_new, parent=None):
        rid = out.get("run_id", "").strip()
        if not rid:
            messagebox.showerror(t("msg.input_error"), t("data.msg.no_run_id"), parent=parent)
            return False
        if any((r is not row) and r.get("run_id", "") == rid for r in self.rows):
            messagebox.showerror(t("msg.input_error"),
                                 t("data.msg.duplicate_run_id", rid=rid), parent=parent)
            return False
        v = out.get("viscosity_mPas", "") if "viscosity_mPas" in self.fields else ""
        if v and fnum(v) is None:
            messagebox.showerror(t("msg.input_error"),
                                 t("steps.msg.viscosity_num"),
                                 parent=parent)
            return False
        b = out.get("base_row", "") if self.has_feature("baseline") else ""
        if b and (fnum(b) is None or fnum(b) < 2):
            messagebox.showerror(t("msg.input_error"),
                                 t("data.msg.base_row_invalid"),
                                 parent=parent)
            return False
        if is_new:
            self.rows.append(out)
        else:
            row.update(out)
        if not self.save_evidence():
            if is_new:
                self.rows.remove(out)
            return False
        self.search()
        return True

    def choose_file_paths(self, parent):
        selected = filedialog.askopenfilenames(parent=parent)
        if not selected:
            return []
        paths = []
        for path in selected:
            p = path
            try:
                rel = os.path.relpath(p, self.path.parent)
                if not rel.startswith(".."):
                    p = rel.replace(os.sep, "/")
            except ValueError:
                pass  # 別ドライブ等は絶対パスのまま
            paths.append(p)
        return paths

    def pick_file_into(self, entry, parent):
        paths = self.choose_file_paths(parent)
        if not paths:
            return
        existing = split_paths(entry.get())
        entry.delete(0, "end")
        entry.insert(0, join_paths(existing + paths))

    # ---------- 工程編集 ----------
    STEP_FIELDS = STEP_FIELDS   # モジュール定数(ensure_initial_csv_filesと共用)
    STEP_FORM = [("action", t("steps.field.action")), ("liquid", t("steps.field.liquid")),
                 ("viscosity_mPas", t("steps.field.viscosity")),
                 ("drop_volume_uL", t("steps.field.drop_volume")), ("duration_min", t("steps.field.duration")),
                 ("data_start_row", t("steps.field.data_start_row")),
                 ("data_end_row", t("steps.field.data_end_row")),
                 ("notes", t("steps.field.notes"))]
    from evidex.core.fields import ACTION_CHOICES, MEDIA_SEEDS


    def save_series(self):
        spath = self.path.parent / "series.csv"
        try:
            if spath.exists():
                bdir = self.path.parent / "backup"
                bdir.mkdir(exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                shutil.copy2(spath, bdir / f"series-{ts}.csv")
                prune_backups(bdir)
            with atomic_write(spath, newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=self.series_fields)
                w.writeheader()
                for r in self.series_rows:
                    w.writerow({k: r.get(k, "") for k in self.series_fields})
            return True
        except Exception as e:
            messagebox.showerror(t("data.msg.save_error"), str(e))
            return False

    # ---------- 詳細表示(共通部品: 別ウィンドウとパネルで共有) ----------
    GCOL = {"A": "#1E7A3C", "B": "#9A5B00", "C": "#5B6B7A"}

    def known_liquids(self):
        """ラン表+工程表で使われた液体名を重複なしで返す(候補リスト用)"""
        seen = {}
        for r in self.rows:
            v = (r.get("liquid", "") or "").strip()
            if v:
                seen.setdefault(norm(v), v)
        for ss in self.steps.values():
            for s in ss:
                v = (s.get("liquid", "") or "").strip()
                if v:
                    seen.setdefault(norm(v), v)
        for v in self.MEDIA_SEEDS:
            seen.setdefault(norm(v), v)
        return sorted(seen.values())

    def update_liquid_choices(self):
        if getattr(self, "liquid", None) is not None:
            self.liquid.config(values=[""] + self.known_liquids())

    def known_series(self):
        """ラン表のseries_idを重複なしで返す(詳細フィルタ候補用)"""
        return sorted({(r.get("series_id", "") or "").strip()
                       for r in self.rows
                       if (r.get("series_id", "") or "").strip()})

    def update_series_choices(self):
        if getattr(self, "series_filter", None) is not None:
            self.series_filter.config(values=[""] + self.known_series())

    def known_actions(self):
        """既定の操作種別+実データの工程actionを重複なしで返す"""
        seen = {}
        for a in self.ACTION_CHOICES:
            seen.setdefault(norm(a), a)
        for ss in self.steps.values():
            for s in ss:
                v = (s.get("action", "") or "").strip()
                if v:
                    seen.setdefault(norm(v), v)
        return sorted(seen.values())

    def update_action_choices(self):
        if getattr(self, "action_filter", None) is not None:
            self.action_filter.config(values=[""] + self.known_actions())
