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
from ..core.attachments import first_path, split_paths
from ..core.csvio import ensure_initial_csv_files, parse_device_csv
from ..core.filtering import norm, fnum, row_matches
from ..core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame
from ..core.i18n import t

class HelperMixin:
    def _liquid_disp(self, r):
        """使用液体の表示値(工程が正本、旧データはラン列にフォールバック)"""
        seen = {}
        for s in self.steps.get(r.get("run_id", ""), []):
            v = (s.get("liquid", "") or "").strip()
            if v:
                seen.setdefault(norm(v), v)
        return " → ".join(seen.values()) if seen else r.get("liquid", "")

    def _liquid_disp_icons(self, r):
        """一覧の使用液体列向け(_liquid_dispの各要素に絵文字を付加)。
        _run_paramsの系列差分はアイコン無しのまま見せるため、
        _liquid_disp自体は変更しない(B-2注4)。"""
        disp = self._liquid_disp(r)
        if not disp:
            return disp
        return " → ".join(f"{icon_for_liquid(p)} {p}".strip()
                          for p in disp.split(" → "))

    def _resolve_path(self, rel):
        rel = first_path(rel)
        if not rel:
            return None
        q = Path(rel)
        return q if q.is_absolute() else (self.path.parent / q)

    def _resolve_single_path(self, rel):
        if not rel:
            return None
        q = Path(rel)
        return q if q.is_absolute() else (self.path.parent / q)

    def open_path(self, row, col):
        paths = split_paths(row.get(col, ""))
        if not paths:
            return
        target = self._resolve_single_path(paths[0])
        if target is None or not target.exists():
            messagebox.showinfo(
                t("msg.info"),
                t("pane.msg.file_not_found", path=target or paths[0]),
            )
            return
        if hasattr(os, "startfile"):
            os.startfile(str(target))
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def _link(self, parent, text, cb):
        color = "#4FB3D9" if getattr(self, "dark", False) else "#0E6E8C"
        lb = ttk.Label(parent, text=text, foreground=color,
                       cursor="hand2", font=("", 10, "underline"))
        lb.bind("<Button-1>", lambda e: cb())
        return lb

    def _run_params(self, r):
        """Return comparable, schema-defined conditions for a run."""
        excluded = {
            "run_id", "series_id", "date", "experimenter", "grade",
            "result_summary", "notes", "base_row",
        }
        excluded.update(k for k in self.fields if k.endswith("_path"))
        params = {}
        rst = self.steps.get(r.get("run_id", ""), [])
        for field in self.fields:
            if field in excluded or field in self.LONG_FIELDS:
                continue
            value = r.get(field, "")
            if rst and field in self.STEP_FIELDS:
                values = []
                for step in rst:
                    item = (step.get(field, "") or "").strip()
                    if item and item not in values:
                        values.append(item)
                if values:
                    value = " / ".join(values)
            params[self.get_label(field)] = value
        if self.has_feature("steps"):
            params[t("pane.field.n_steps")] = str(len(rst)) if rst else ""
        return params

    def _series_grade_seq(self, runs):
        """時系列順runsの格付け列(各runの "A"/"B"/"C" または未設定なら "?")。
        _tab_seriesのGrade推移とシリーズ管理一覧の両方が、この順序リストを
        元に表示する(計画書: 二重実装禁止)。"""
        if not self.has_feature("grading"):
            return []
        return [(x.get("grade", "") or "").strip().upper() or "?"
                for x in runs]

    def _compress_grade_seq(self, seq):
        """連続重複を圧縮して"A→B"形式の文字列にする(シリーズ管理一覧用)。
        _tab_seriesの方は圧縮しない全件タイムラインのまま(計画書T6-12)。"""
        if not seq:
            return "—"
        out = [seq[0]]
        for g in seq[1:]:
            if g != out[-1]:
                out.append(g)
        return "→".join(out)

    def _series_manager_rows(self):
        """シリーズ管理ウィンドウの一覧データ。
        series.csv登録済み ∪ runsが参照するseries_id の和集合(計画書B-1)。"""
        sids = set()
        for s in self.series_rows:
            sid = (s.get("series_id", "") or "").strip()
            if sid:
                sids.add(sid)
        for r in self.rows:
            sid = (r.get("series_id", "") or "").strip()
            if sid:
                sids.add(sid)
        out = []
        for sid in sorted(sids):
            runs = [x for x in self.rows
                    if (x.get("series_id", "") or "").strip() == sid]
            runs.sort(key=lambda x: (x.get("date", ""), x.get("run_id", "")))
            dates = [x.get("date", "") for x in runs if x.get("date", "")]
            period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
            srow = next((s for s in self.series_rows
                         if (s.get("series_id", "") or "").strip() == sid),
                        None)
            obj = (srow.get("objective", "") if srow else "").strip()
            obj = obj.splitlines()[0] if obj else ""
            if len(obj) > 20:
                obj = obj[:20] + "…"
            out.append({"sid": sid, "n": len(runs), "period": period,
                        "grades": self._compress_grade_seq(
                            self._series_grade_seq(runs)),
                        "objective": obj, "runs": runs, "srow": srow})
        return out
