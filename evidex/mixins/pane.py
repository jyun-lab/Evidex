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
from ..core.attachments import split_paths
from ..core.csvio import ensure_initial_csv_files, parse_device_csv
from ..core.filtering import norm, fnum, row_matches
from ..core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from ..core.media import is_image_path
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame
from ..core.i18n import t

class PaneMixin:
    def toggle_pane(self):
        if self.pane_visible:
            self._mid.forget(self.pane)
            self.pane_visible = False
        else:
            self._mid.add(self.pane, weight=2)
            self.pane_visible = True
            self._sash_after = self.after(100, self._init_sash)
            self.on_select()
        self.v_pane.set(self.pane_visible)
        self.pane_btn.config(text=t("pane.btn.visible") if self.pane_visible
                             else t("pane.btn.hidden"))

    def _menu_pane(self):
        if self.v_pane.get() != self.pane_visible:
            self.toggle_pane()

    def _init_sash(self, _retry=0):
        """パネルに最低幅を保証(表の要求幅に食われるのを防ぐ)。
        左ナビ150px、右パネル440pxを確保。
        幅が未確定の場合はリトライする(起動時の表示崩れ対策)。"""
        try:
            self.update_idletasks()
            w = self._mid.winfo_width()
            if w <= 1 and _retry < 10:
                self._sash_after = self.after(50, lambda: self._init_sash(_retry + 1))
                return
            idx = 0
            if getattr(self, "nav_visible", True):
                self._mid.sashpos(idx, 150)
                idx += 1
            if getattr(self, "pane_visible", True) and w > 850:
                self._mid.sashpos(idx, max(150 + 200, w - 440))
            self._sash_inited = True
        except tk.TclError:
            pass

    # ---------- 検索条件プリセット(evidex_prefs.json) ----------
    def render_pane(self, idx):
        for w in self.pane.winfo_children():
            w.destroy()
        if not (0 <= idx < len(self.hits)):
            ttk.Label(self.pane, foreground="#888",
                      text=t("pane.msg.select_run")).pack(anchor="w", pady=10)
            return
        r = self.hits[idx]
        head = ttk.Frame(self.pane)
        head.pack(fill="x", pady=(4, 0))
        ttk.Label(head, text=r.get("run_id", ""),
                  font=("", 12, "bold")).pack(side="left")
        if self.has_feature("grading"):
            g = (r.get("grade", "") or "").strip().upper()
            ttk.Label(head, text=g or "—", font=("", 11, "bold"),
                      foreground=self.GCOL.get(g, "#888")
                      ).pack(side="left", padx=(6, 0))
        acts = ttk.Frame(self.pane)
        acts.pack(fill="x", pady=(4, 0))
        self._link(acts, t("btn.open_in_window"),
                   lambda: self.open_detail(idx)).pack(side="right")
        ttk.Button(acts, text=t("btn.edit_run"),
                   command=lambda: self.edit_run(r)
                   ).pack(side="left")
        if self.has_feature("steps"):
            ttk.Button(acts, text=t("btn.edit_steps"),
                       command=lambda: self.open_steps_editor(
                           r.get("run_id", ""))
                       ).pack(side="left", padx=(6, 0))
        sf = ScrollFrame(self.pane)
        sf.pack(fill="both", expand=True, pady=(6, 0))
        wave = ttk.Frame(sf.inner)
        wave.pack(fill="x")

        def set_mode(mo):
            self._pane_state["mode"] = mo
            self.render_pane(idx)

        def set_base(b):
            self._pane_state["base"] = b
            self.render_pane(idx)

        def set_axis(a):
            self._pane_state["axis"] = a
            self.render_pane(idx)

        def set_axis_open(v):
            self._pane_state["axis_open"] = v
            self.render_pane(idx)

        self._draw_wave(wave, r, self._pane_state["mode"], set_mode,
                        figsize=(4.4, 2.1),
                        base=self._pane_state["base"],
                        set_base=(set_base if self.has_feature("baseline")
                                  else None),
                        axis=self._pane_state["axis"], set_axis=set_axis,
                        axis_open=self._pane_state.get("axis_open", False),
                        set_axis_open=set_axis_open)
        self._detail_sections(sf.inner, r, wrap=380)

    def open_detail(self, idx):
        """別ウィンドウ版の詳細(前後送り付き)"""
        win = tk.Toplevel(self)
        win.geometry("700x680")
        state = {"idx": idx,
                 "mode": self.WAVEFORM.get("default_mode", "all"),
                 "base": False, "axis": {},
                "axis_open": False}

        header = ttk.Frame(win, padding=(10, 8))
        header.pack(fill="x")
        prev_b = ttk.Button(header, text=t("btn.prev"), width=6,
                            command=lambda: nav(-1))
        prev_b.pack(side="left")
        title = ttk.Label(header, font=("", 13, "bold"))
        title.pack(side="left", padx=(10, 4))
        gbadge = ttk.Label(header, font=("", 11, "bold"))
        if self.has_feature("grading"):
            gbadge.pack(side="left")
        pos = ttk.Label(header, foreground="#888")
        pos.pack(side="left", padx=(8, 0))
        next_b = ttk.Button(header, text=t("btn.next"), width=6,
                            command=lambda: nav(1))
        next_b.pack(side="right")

        win.minsize(560, 480)
        bar = ttk.Frame(win, padding=(10, 8))
        bar.pack(side="bottom", fill="x")
        body = ttk.Frame(win)
        body.pack(fill="both", expand=True)
        ttk.Button(bar, text=t("btn.edit_run"),
                   command=lambda: (win.destroy(),
                                    self.edit_run(self.hits[state["idx"]]))
                   ).pack(side="left")
        if self.has_feature("steps"):
            ttk.Button(bar, text=t("btn.edit_steps"),
                       command=lambda: (win.destroy(), self.open_steps_editor(
                           self.hits[state["idx"]].get("run_id", "")))
                       ).pack(side="left", padx=(6, 0))

        def set_mode(mo):
            state["mode"] = mo
            render()

        def set_base(b):
            state["base"] = b
            render()

        def set_axis(a):
            state["axis"] = a
            render()

        def set_axis_open(v):
            state["axis_open"] = v
            render()

        def render():
            r = self.hits[state["idx"]]
            title.config(text=r.get("run_id", t("pane.label.no_id")))
            if self.has_feature("grading"):
                g = (r.get("grade", "") or "").strip().upper()
                gbadge.config(text=g or "—",
                              foreground=self.GCOL.get(g, "#888"))
            pos.config(text=f"{state['idx'] + 1} / {len(self.hits)}")
            prev_b.config(state="normal" if state["idx"] > 0 else "disabled")
            next_b.config(state="normal"
                          if state["idx"] < len(self.hits) - 1 else "disabled")
            try:
                self.tree.selection_set(str(state["idx"]))
            except tk.TclError:
                pass
            for w in body.winfo_children():
                w.destroy()
            sf = ScrollFrame(body)
            sf.pack(fill="both", expand=True)
            c = ttk.Frame(sf.inner, padding=(12, 4))
            c.pack(fill="both", expand=True)
            wave = ttk.Frame(c)
            wave.pack(fill="x")
            self._draw_wave(wave, r, state["mode"], set_mode,
                            base=state["base"],
                            set_base=(set_base if self.has_feature("baseline")
                                      else None),
                            axis=state["axis"], set_axis=set_axis,
                            axis_open=state["axis_open"],
                            set_axis_open=set_axis_open)
            self._detail_sections(c, r)
            win.lift()
            win.focus_set()

        def nav(d):
            new = state["idx"] + d
            if 0 <= new < len(self.hits):
                state["idx"] = new
                render()

        win.bind("<Left>", lambda e: nav(-1))
        win.bind("<Right>", lambda e: nav(1))
        render()
        win._render = render
        win._nav = nav
        win._state = state
        win._set_mode = set_mode
        win._set_base = set_base
        win._set_axis = set_axis
        win._set_axis_open = set_axis_open
        win._body = body
        return win

    # ---------- 編集 ----------
    from ..core.fields import LONG_FIELDS, HIDDEN_EDIT_FIELDS, JP_LABEL, CHOICES

    def _detail_sections(self, parent, r, wrap=620):
        """詳細の中身: 基本情報/工程/ファイル/系列 の4タブ"""
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, pady=(8, 0))
        tab_basic = ttk.Frame(nb, padding=10)
        tab_files = ttk.Frame(nb, padding=10)
        nb.add(tab_basic, text=t("pane.tab.basic"))
        tab_steps = None
        if self.has_feature("steps"):
            tab_steps = ttk.Frame(nb, padding=10)
            nb.add(tab_steps, text=t("pane.tab.steps"))
        nb.add(tab_files, text=t("pane.tab.files"))
        tab_series = None
        if self.has_feature("series"):
            tab_series = ttk.Frame(nb, padding=10)
            nb.add(tab_series, text=t("pane.tab.series"))

        def _series_tab_region(e):
            if tab_series is None:
                return False
            if nb.identify(e.x, e.y) != "label":
                return False
            return nb.tabs()[nb.index(f"@{e.x},{e.y}")] == str(tab_series)

        if tab_series is not None:
            Tooltip(nb, HELP_TEXT["series_tab"], region=_series_tab_region)

        def section(parent_, label):
            ttk.Label(parent_, text=label, foreground="#888",
                      font=("", 9)).pack(anchor="w", pady=(10, 1))

        # --- 基本情報タブ ---
        rst = self.steps.get(r.get("run_id", ""), [])
        grid = ttk.Frame(tab_basic)
        grid.pack(fill="x")
        excluded = {"run_id", "grade", "base_row", "notebook_ref"}
        excluded.update(self.LONG_FIELDS)
        excluded.update(k for k in self.fields if k.endswith("_path"))
        items = []
        for field in self.fields:
            if field in excluded:
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
            items.append((self.get_label(field), value))
        for i, (k, v) in enumerate(items):
            ttk.Label(grid, text=k, foreground="#888", width=10
                      ).grid(row=i // 2, column=(i % 2) * 2,
                             sticky="w", pady=1)
            ttk.Label(grid, text=v or "—").grid(
                row=i // 2, column=(i % 2) * 2 + 1,
                sticky="w", padx=(0, 24), pady=1)
        for field in self.LONG_FIELDS:
            if r.get(field):
                section(tab_basic, self.get_label(field))
                ttk.Label(tab_basic, text=r[field], wraplength=wrap,
                          justify="left").pack(anchor="w")

        # --- 工程タブ(枠付きカード) ---
        if tab_steps is not None and rst:
            for s in rst:
                card = ttk.Frame(tab_steps, relief="solid", borderwidth=1,
                                 padding=(8, 4))
                card.pack(fill="x", pady=2)
                row1 = ttk.Frame(card)
                row1.pack(fill="x")
                primary = self.STEP_FORM[0][0] if self.STEP_FORM else "action"
                primary_value = s.get(primary, "")
                ttk.Label(row1, text=f"{icon_for_action(primary_value)} "
                                     f"{s.get('step_no','')}. "
                                     f"{primary_value}",
                          font=("", 10, "bold")).pack(side="left")
                sub = []
                for field, label in self.STEP_FORM[1:]:
                    value = (s.get(field, "") or "").strip()
                    if value and field != "notes":
                        sub.append(f"{label}: {value}")
                if sub:
                    ttk.Label(card, text=" · ".join(sub), font=("", 9),
                              foreground="#888").pack(anchor="w")
                if s.get("notes"):
                    ttk.Label(card, text=t("pane.label.notes_prefix", notes=s['notes']), font=("", 9),
                              foreground="#888", wraplength=wrap,
                              justify="left").pack(anchor="w")
        elif tab_steps is not None:
            ttk.Label(tab_steps, foreground="#888",
                      text=t("pane.msg.no_steps")
                      ).pack(anchor="w")

        # --- ファイルタブ(コピー/フォルダを開く付き) ---
        def copy_path(rel, btn):
            ap = self._resolve_single_path(rel)
            self.clipboard_clear()
            self.clipboard_append(str(ap if ap else rel))
            btn.config(text="✓")
            btn.after(900, lambda: btn.config(text="📋"))

        def open_folder(rel):
            ap = self._resolve_single_path(rel)
            folder = None
            if ap is not None:
                folder = ap.parent if ap.suffix else ap
            if folder is None or not folder.exists():
                messagebox.showinfo(t("msg.info"),
                                    t("pane.msg.folder_not_found", folder=folder))
                return
            if hasattr(os, "startfile"):          # Windows: エクスプローラー
                os.startfile(str(folder))
            else:                                  # 開発環境(Linux)用
                subprocess.Popen(["xdg-open", str(folder)])

        def make_thumbnail(path, master, max_width=150, max_height=110):
            try:
                from PIL import Image, ImageTk

                with Image.open(path) as image:
                    image.thumbnail((max_width, max_height))
                    return ImageTk.PhotoImage(image.copy(), master=master)
            except Exception:
                pass
            try:
                image = tk.PhotoImage(master=master, file=str(path))
                scale = max(
                    1,
                    int(max(
                        image.width() / max_width,
                        image.height() / max_height,
                    ) + 0.999),
                )
                return image.subsample(scale, scale) if scale > 1 else image
            except tk.TclError:
                return None

        image_items = []
        for col, lab in (("raw_path", t("pane.field.raw_path")),
                         ("excel_path", t("pane.field.excel_path")),
                         ("photo_path", t("pane.field.photo_path"))):
            for rel in split_paths(r.get(col, "")):
                resolved = self._resolve_single_path(rel)
                if is_image_path(rel) and resolved is not None and resolved.exists():
                    image_items.append((col, lab, rel, resolved))
        tab_files._image_refs = []
        if image_items:
            ttk.Label(tab_files, text=t("pane.section.images"),
                      foreground="#888", font=("", 9)
                      ).pack(anchor="w", pady=(0, 4))
            gallery = ttk.Frame(tab_files)
            gallery.pack(fill="x", pady=(0, 8))
            for index, (col, _lab, rel, resolved) in enumerate(image_items):
                card = ttk.Frame(gallery, padding=(0, 0, 10, 8))
                card.grid(row=index // 3, column=index % 3, sticky="nw")
                thumb = make_thumbnail(resolved, card)
                if thumb is None:
                    continue
                tab_files._image_refs.append(thumb)
                image_label = ttk.Label(card, image=thumb, cursor="hand2")
                image_label.pack(anchor="w")
                image_label.bind(
                    "<Button-1>",
                    lambda _event, path=rel, key=col: self.open_path({key: path}, key),
                )
                name = Path(rel.replace("\\", "/")).name or rel
                caption = ttk.Label(
                    card,
                    text=name,
                    foreground="#555",
                    wraplength=150,
                    justify="left",
                    cursor="hand2",
                )
                caption.pack(anchor="w", pady=(2, 0))
                caption.bind(
                    "<Button-1>",
                    lambda _event, path=rel, key=col: self.open_path({key: path}, key),
                )

        any_file = False
        for col, lab in (("raw_path", t("pane.field.raw_path")),
                         ("excel_path", t("pane.field.excel_path")),
                         ("photo_path", t("pane.field.photo_path"))):
            for index, rel in enumerate(split_paths(r.get(col, "")), start=1):
                any_file = True
                rowf = ttk.Frame(tab_files)
                rowf.pack(fill="x", pady=2)
                label = lab if index == 1 else ""
                ttk.Label(rowf, text=label, foreground="#888", width=10
                          ).pack(side="left")
                cbtn = ttk.Button(rowf, text="📋", width=3)
                cbtn.config(command=lambda path=rel, b=cbtn: copy_path(path, b))
                obtn = ttk.Button(rowf, text="📁", width=3,
                                  command=lambda path=rel: open_folder(path))
                obtn.pack(side="right")
                cbtn.pack(side="right", padx=(0, 4))
                self._link(
                    rowf,
                    rel,
                    lambda path=rel: self.open_path({col: path}, col),
                ).pack(side="left", fill="x")
        if r.get("notebook_ref"):
            rowf = ttk.Frame(tab_files)
            rowf.pack(fill="x", pady=2)
            ttk.Label(rowf, text=t("pane.field.notebook_ref"), foreground="#888", width=10
                      ).pack(side="left")
            ttk.Label(rowf, text=r["notebook_ref"]).pack(side="left")
            any_file = True
        if not any_file:
            ttk.Label(tab_files, foreground="#888",
                      text=t("pane.msg.no_files")
                      ).pack(anchor="w")
        ttk.Label(tab_files, foreground="#888", font=("", 8),
                  text=t("pane.msg.file_hint")
                  ).pack(anchor="w", pady=(8, 0))

        # --- 系列タブ(系列比較ビュー) ---
        if tab_series is not None:
            self._tab_series(tab_series, r, wrap)
        return nb

    def _tab_series(self, parent, r, wrap=620):
        sid = (r.get("series_id", "") or "").strip()
        if not sid:
            ttk.Label(parent, foreground="#888",
                      text=t("pane.msg.no_series")).pack(anchor="w")
            return
        runs = [x for x in self.rows
                if (x.get("series_id", "") or "").strip() == sid]
        runs.sort(key=lambda x: (x.get("date", ""), x.get("run_id", "")))

        # --- 概要 ---
        head = ttk.Frame(parent)
        head.pack(fill="x")
        ttk.Label(head, text=t("pane.label.series_title", sid=sid),
                  font=("", 11, "bold")).pack(side="left")
        ttk.Button(head, text=t("btn.edit_series_info"),
                   command=lambda: self.edit_series(sid)
                   ).pack(side="right")
        dates = [x.get("date", "") for x in runs if x.get("date", "")]
        period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
        ttk.Label(parent, foreground="#888",
                  text=t("series.label.summary", n=len(runs), period=period)
                  ).pack(anchor="w", pady=(2, 0))
        if self.has_feature("grading"):
            gline = ttk.Frame(parent)
            gline.pack(anchor="w", pady=(2, 0))
            ttk.Label(gline, text=t("series.label.grade_seq"),
                      foreground="#888").pack(side="left")
            for j, g in enumerate(self._series_grade_seq(runs)):
                if j:
                    ttk.Label(gline, text="→",
                              foreground="#888").pack(side="left", padx=2)
                ttk.Label(gline, text=g, font=("", 10, "bold"),
                          foreground=self.GCOL.get(g, "#888")).pack(side="left")

        # --- series.csv の既知マップ ---
        srow = next((s for s in self.series_rows
                     if (s.get("series_id", "") or "").strip() == sid), None)
        if srow:
            for key, lab in (("objective", t("series.field.objective")), ("claim", t("series.field.claim")),
                             ("established_knowns", t("series.field.established_knowns")),
                             ("unresolved", t("series.field.unresolved")),
                             ("my_assessment", t("series.field.my_assessment"))):
                if srow.get(key, "").strip():
                    ttk.Label(parent, text=lab, foreground="#888",
                              font=("", 9)).pack(anchor="w", pady=(8, 0))
                    ttk.Label(parent, text=srow[key], wraplength=wrap,
                              justify="left").pack(anchor="w")
        else:
            ttk.Label(parent, foreground="#888",
                      text=t("series.msg.not_registered")
                      ).pack(anchor="w", pady=(6, 0))

        # --- 差分タイムライン ---
        ttk.Label(parent, text=t("pane.label.timeline"),
                  foreground="#888", font=("", 9)).pack(anchor="w",
                                                        pady=(12, 2))
        prev = None
        for x in runs:
            box = ttk.Frame(parent, padding=(8, 4))
            box.pack(fill="x", pady=(0, 2))
            cur = x.get("run_id", "") == r.get("run_id", "")
            hl = ttk.Frame(box)
            hl.pack(anchor="w")
            ttk.Label(hl, text=("▶ " if cur else "   ") +
                      f"{x.get('date','')}  {x.get('run_id','')}",
                      font=("", 10, "bold" if cur else "normal")
                      ).pack(side="left")
            if self.has_feature("grading"):
                g = (x.get("grade", "") or "").strip().upper()
                ttk.Label(hl, text=f" {g}" if g else "",
                          font=("", 10, "bold"),
                          foreground=self.GCOL.get(g, "#888")).pack(side="left")
            ttk.Label(hl, text=f"  {x.get('experimenter','')}",
                      foreground="#888").pack(side="left")
            params = self._run_params(x)
            if prev is None:
                init = "、".join(f"{k}={v}" for k, v in params.items() if v)
                if init:
                    ttk.Label(box, text=t("pane.label.initial_condition") + init,
                              wraplength=wrap, justify="left",
                              foreground="#555").pack(anchor="w", padx=(16, 0))
            else:
                diffs = []
                for k in params:
                    a, b = prev.get(k, ""), params.get(k, "")
                    if a == b:
                        continue
                    fa, fb = fnum(a), fnum(b)
                    if fa is not None and fb is not None:
                        d = fb - fa
                        diffs.append(f"{k}: {a} → {b} ({d:+g})")
                    else:
                        diffs.append(f"{k}: {a or '—'} → {b or '—'}")
                if diffs:
                    for dtext in diffs:
                        ttk.Label(box, text="Δ " + dtext,
                                  foreground="#0E6E8C" if not
                                  getattr(self, "dark", False) else "#4FB3D9"
                                  ).pack(anchor="w", padx=(16, 0))
                else:
                    ttk.Label(box, text=t("pane.msg.no_change"), font=("", 8),
                              foreground="#999").pack(anchor="w",
                                                      padx=(16, 0))
            if x.get("result_summary", "").strip():
                ttk.Label(box, text=x["result_summary"], wraplength=wrap,
                          justify="left").pack(anchor="w", padx=(16, 0))
            prev = params
