#!/usr/bin/env python3
"""Evidex 実験記録アプリ GUI (Python 3.8+)

起動: python evidex_app.py
同じフォルダの runs.csv / steps.csv / series.csv を読み込む(無ければ
ヘッダのみのファイルを自動生成する)。実験記録・工程・シリーズの検索/
閲覧に加え、本GUI上で編集・新規作成・削除ができる。台帳を壊さないため、
書き込みの前に必ず backup/ へ退避してから保存する(世代管理あり)。
波形プレビューには matplotlib、テーマには ttkbootstrap を使うが、どちらも
未導入なら素のtkinterにフォールバックして全機能が動作する。
詳細な設計判断・制約・地雷は HANDOVER.md を参照。
"""
import calendar
import json
import re
import csv
import unicodedata
import datetime
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

from evidex.core import config
from evidex.core.i18n import t
from evidex.core.fields import (RUN_FIELDS, STEP_FIELDS, SERIES_FIELDS, COLS, HEAD,
                                LONG_FIELDS, HIDDEN_EDIT_FIELDS, JP_LABEL, CHOICES, GCOL,
                                STEP_FORM, ACTION_CHOICES, MEDIA_SEEDS,
                                FACETS, ADV_FILTERS, LABEL_EN, FEATURES,
                                WAVEFORM, get_label)
from evidex.core.csvio import (ensure_initial_csv_files, extract_bundled_assets, load,
                               load_with_header, load_steps_with_header, parse_device_csv,
                               _read_csv_rows)
from evidex.core.backup import prune_backups
from evidex.core.filtering import norm, fnum, row_matches
from evidex.core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from evidex.core.table_style import configure_treeview_rows
from evidex.core.windows import apply_window_icon, release_window_icons
from evidex.gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from evidex.views import (
    edit_series, _after_series_saved, open_series_manager,
    _refresh_series_manager, _render_series_detail, _new_series,
    _delete_series, _open_run_in_main,
    edit_run, edit_selected, delete_selected,
    validate_step, save_steps, step_form, open_steps_editor
)
if MPL:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.ticker import MultipleLocator

from evidex.components import Tooltip, DatePicker, ScrollFrame, _on_wave_click, _draw_wave



from evidex.mixins import PrefsMixin, ThemeMixin, NavMixin, SearchMixin, DataMixin, TreeMixin, PaneMixin, HelperMixin

class App(tb.Window if THEMED else tk.Tk, PrefsMixin, ThemeMixin, NavMixin, SearchMixin, DataMixin, TreeMixin, PaneMixin, HelperMixin):
    def __init__(self):
        if THEMED:
            super().__init__(themename="flatly")
        else:
            super().__init__()
            
        self.LONG_FIELDS = LONG_FIELDS
        self.HIDDEN_EDIT_FIELDS = HIDDEN_EDIT_FIELDS
        self.JP_LABEL = JP_LABEL
        self.CHOICES = CHOICES
        self.GCOL = GCOL
        self.STEP_FORM = STEP_FORM
        self.ACTION_CHOICES = ACTION_CHOICES
        self.MEDIA_SEEDS = MEDIA_SEEDS
        self.STEP_FIELDS = STEP_FIELDS
        self.FACETS = FACETS
        self.ADV_FILTERS = ADV_FILTERS
        self.LABEL_EN = LABEL_EN
        self.FEATURES = FEATURES
        self.WAVEFORM = WAVEFORM

        self.title(t("data.title.main", name="").split("—")[0].strip())
        self.geometry("1280x720")
        self.minsize(1024, 620)
        self._set_window_icon()
        self.nav_view = None
        self._nav_open = {f["field"]: False for f in FACETS}
        if FACETS:
            self._nav_open[FACETS[0]["field"]] = True
        self._nav_open["preset"] = False
        self.rows = []
        self.hits = []
        self.steps = {}
        self.fields = []
        self.step_fields = []
        self.mtime = 0.0
        # 起動シーケンス: (1)同梱アセット展開(exe初回のみ) →
        # (2)台帳CSVが無ければヘッダのみで自動生成 → (3)フォント → (4)UI構築 → (5)読込
        extract_bundled_assets()
        ensure_initial_csv_files(config.RECORDS_CSV.parent)
        # 【B】UIフォント: 候補フォールバック方式で一括更新
        fam = self._resolve_ui_font()
        self._ui_font_family = fam
        if fam:
            for named in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                          "TkHeadingFont", "TkTooltipFont"):
                try:
                    tkfont.nametofont(named).configure(family=fam)
                except tk.TclError:
                    pass
            try:
                style = self.style if hasattr(self, "style") else ttk.Style()
                style.configure(".", font=(fam, 10))
            except Exception:
                pass
        self._build()
        self._load(config.RECORDS_CSV)

    def get_label(self, field_key):
        return get_label(field_key)

    def has_feature(self, name):
        return bool(self.FEATURES.get(name, False))

    def destroy(self):
        if getattr(self, "_sash_after", None) is not None:
            try:
                self.after_cancel(self._sash_after)
            except (tk.TclError, ValueError):
                pass
            self._sash_after = None
        release_window_icons(self)
        super().destroy()

    def _set_window_icon(self):
        """Apply the icon to Tk and, on Windows, the taskbar HWND."""
        self._window_icon_status = apply_window_icon(self)

    def _build(self):
        # メニューバー: ファイル操作と表示切替はここに集約
        menubar = tk.Menu(self)
        fmenu = tk.Menu(menubar, tearoff=0)
        fmenu.add_command(label=t("menu.file.open"), command=self.open_file)
        fmenu.add_command(label=t("menu.file.reload"), command=lambda: self._load(self.path))
        fmenu.add_separator()
        fmenu.add_command(label=t("menu.file.settings"), command=self.open_settings)
        fmenu.add_command(label=t("menu.file.pack_manager"), command=lambda: self.open_schema_editor())
        fmenu.add_separator()
        fmenu.add_command(label=t("menu.file.exit"), command=self.destroy)
        menubar.add_cascade(label=t("menu.file"), menu=fmenu)
        vmenu = tk.Menu(menubar, tearoff=0)
        self.v_pane = tk.BooleanVar(value=True)
        if THEMED:
            self.v_dark = tk.BooleanVar(value=False)
            vmenu.add_checkbutton(label=t("menu.view.dark_mode"), variable=self.v_dark,
                                  command=self._menu_dark)
        menubar.add_cascade(label=t("menu.view"), menu=vmenu)
        smenu = None
        if self.has_feature("series"):
            smenu = tk.Menu(menubar, tearoff=0)
            smenu.add_command(label=t("menu.series.manage"),
                              command=self.open_series_manager)
            menubar.add_cascade(label=t("menu.series"), menu=smenu)
        self.config(menu=menubar)
        self._menus = (fmenu, vmenu, smenu)   # テスト用フック
        if THEMED:
            self.dark = False

        # ===== アプリヘッダ(新設) =====
        header = ttk.Frame(self, padding=(8, 4))
        header.pack(fill="x")
        self.nav_btn = ttk.Button(header, text="☰", width=3, command=self.toggle_nav)
        self.nav_btn.pack(side="left")
        Tooltip(self.nav_btn, t("main.tooltip.nav_btn"))
        ttk.Button(header, text=t("main.btn.new_run"),
                   command=lambda: self.edit_run(None),
                   **bstyle("primary.TButton")).pack(side="right")
        self.pane_btn = ttk.Button(header, text=t("main.btn.detail_panel"),
                                   command=self.toggle_pane)
        self.pane_btn.pack(side="right", padx=(0, 8))
        Tooltip(self.pane_btn, t("main.tooltip.pane_btn"))

        # ===== 操作グループ: 検索・絞り込み =====
        # (PLAN_ui_overhaul A-1。視線フローの最上段=操作の起点)
        opgroup = ttk.Labelframe(self, text=t("main.group.search_filter"),
                                 padding=(10, 6))
        opgroup.pack(fill="x", padx=10, pady=(8, 0))
        self._opgroup = opgroup

        # 行1: 検索が主役。入力即絞り込み
        row1 = ttk.Frame(opgroup)
        row1.pack(fill="x")
        ttk.Label(row1, text=t("btn.search")).pack(side="left")
        self.text = ttk.Entry(row1, font=("", 11))
        self.text.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.text.bind("<KeyRelease>", self.schedule_search)
        # ボタン並び順(PLAN_startup_and_encoding_fixes 【B】):
        # 検索 → 詳細フィルタ → クリア → プリセット → 条件を保存
        self.adv_visible = False
        self.adv_btn = ttk.Button(row1, text=t("btn.adv_filter", n="", arrow="▸"),
                                  command=self.toggle_adv)
        self.adv_btn.pack(side="left", padx=(6, 0))
        Tooltip(self.adv_btn, HELP_TEXT.get("adv_filter", ""))
        ttk.Button(row1, text=t("btn.clear"), command=self.clear
                   ).pack(side="left", padx=(6, 0))
        self.preset_box = ttk.Combobox(row1, width=14, state="readonly",
                                       postcommand=self._refresh_presets)
        self.preset_box.pack(side="left", padx=(12, 0))
        self.preset_box.bind("<<ComboboxSelected>>",
                             lambda e: self.apply_preset(
                                 self.preset_box.get()))
        Tooltip(self.preset_box, HELP_TEXT.get("preset", ""))
        ttk.Button(row1, text=t("btn.preset_save"), command=self.save_preset
                   ).pack(side="left", padx=(4, 0))

        # 詳細フィルタ(折りたたみ。pack(side="left")では左詰め固定のため
        # 各行を grid に切り替え、入力欄の列に weight=1 を設定して
        # ウィンドウ幅に追従させる。行2(フラグ)のみ checkbutton のみで pack を使用。
        # opgroupの子にし、表示時は fill="x" のみでpack(beforeを使わない)。
        # advの親自体がopgroupなので、再アンカー時のTclError(2026-06-12/
        # 06-13で踏んだ「親違いのbefore=」)が構造的に発生しない。
        self.adv = ttk.Frame(opgroup)
        adv_rows = [ttk.Frame(self.adv) for _ in range(4)]
        for r in adv_rows:
            r.pack(fill="x", pady=(4, 2))

        # Initialize placeholders to None so search() doesn't fail
        self.vmin = self.vmax = self.dfrom = self.dto = self.series_filter = None
        self.chip = self.who = self.understanding_filter = self.action_filter = None
        self.flag_has_raw = self.flag_no_steps = None
        self.gvars = {}
        self.gchecks = {}
        self.flag_unread = None
        self.status = self.liquid = None

        # ---- 行0: 粘度範囲 / 日付範囲 / シリーズ ----
        # grid 使用。入力欄の列に weight=1 → 幅に追従して伸縮
        _c, _exp = 0, []
        if "viscosity_range" in self.ADV_FILTERS:
            ttk.Label(adv_rows[0], text=t("main.label.viscosity")).grid(
                row=0, column=_c, sticky="w", padx=(6, 3)); _c += 1
            self.vmin = ttk.Entry(adv_rows[0], width=6)
            self.vmin.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
            ttk.Label(adv_rows[0], text=t("main.label.tilde")).grid(
                row=0, column=_c, padx=(4, 4)); _c += 1
            self.vmax = ttk.Entry(adv_rows[0], width=6)
            self.vmax.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
        if "date_range" in self.ADV_FILTERS:
            ttk.Label(adv_rows[0], text=t("main.label.date_from")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.dfrom = ttk.Entry(adv_rows[0], width=10)
            self.dfrom.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
            ttk.Label(adv_rows[0], text=t("main.label.date_to")).grid(
                row=0, column=_c, sticky="w", padx=(8, 3)); _c += 1
            self.dto = ttk.Entry(adv_rows[0], width=10)
            self.dto.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
        if "series" in self.ADV_FILTERS:
            ttk.Label(adv_rows[0], text=t("main.label.series")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.series_filter = ttk.Combobox(adv_rows[0], width=10, state="readonly", values=[""])
            self.series_filter.grid(row=0, column=_c, sticky="ew", padx=(0, 8))
            _exp.append(_c); _c += 1
        for col in _exp:
            adv_rows[0].columnconfigure(col, weight=1)

        # ---- 行1: チップ / 実験者 / 理解度 / 操作 ----
        _c, _exp = 0, []
        if "chip" in self.ADV_FILTERS:
            ttk.Label(adv_rows[1], text=t("main.label.chip")).grid(
                row=0, column=_c, sticky="w", padx=(6, 3)); _c += 1
            self.chip = ttk.Entry(adv_rows[1], width=9)
            self.chip.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
        if "experimenter" in self.ADV_FILTERS:
            ttk.Label(adv_rows[1], text=t("main.label.experimenter")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.who = ttk.Entry(adv_rows[1], width=10)
            self.who.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
        if "understanding" in self.ADV_FILTERS:
            ttk.Label(adv_rows[1], text=t("main.label.understanding")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.understanding_filter = ttk.Combobox(
                adv_rows[1], width=18, state="readonly",
                values=self.CHOICES.get("understanding", []))
            self.understanding_filter.grid(row=0, column=_c, sticky="ew")
            _exp.append(_c); _c += 1
            Tooltip(self.understanding_filter, HELP_TEXT.get("understanding", ""))
        if "action" in self.ADV_FILTERS:
            ttk.Label(adv_rows[1], text=t("main.label.action")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.action_filter = ttk.Combobox(adv_rows[1], width=10, state="readonly", values=[""])
            self.action_filter.grid(row=0, column=_c, sticky="ew", padx=(0, 8))
            _exp.append(_c); _c += 1
        for col in _exp:
            adv_rows[1].columnconfigure(col, weight=1)

        # ---- 行2: フラグ(生データあり / 工程未入力) ----
        # checkbutton のみなので pack で十分
        if "flags" in self.ADV_FILTERS:
            self.flag_has_raw = tk.BooleanVar(value=False)
            ttk.Checkbutton(adv_rows[2], text=t("main.label.has_raw"), variable=self.flag_has_raw,
                           command=self.search).pack(side="left", padx=(6, 0))
            self.flag_no_steps = tk.BooleanVar(value=False)
            ttk.Checkbutton(adv_rows[2], text=t("main.label.no_steps"), variable=self.flag_no_steps,
                           command=self.search).pack(side="left", padx=(20, 0))

        # ---- 行3: 格付け / 未読のみ / 状態 / 液体 ----
        # checkbutton は固定幅、combobox の列に weight=1
        _c, _exp = 0, []
        if "grades" in self.ADV_FILTERS:
            ttk.Label(adv_rows[3], text=t("main.label.grades")).grid(
                row=0, column=_c, sticky="w", padx=(6, 3)); _c += 1
            for g in "ABC":
                v = tk.BooleanVar(value=False)
                cb = ttk.Checkbutton(adv_rows[3], text=g, variable=v,
                                     command=self.search, width=4)
                cb.grid(row=0, column=_c, padx=(2, 2)); _c += 1
                self.gvars[g] = v
                self.gchecks[g] = cb
                Tooltip(cb, HELP_TEXT.get(f"grade_{g}", ""))
        if "unread" in self.ADV_FILTERS:
            self.flag_unread = tk.BooleanVar(value=False)
            ttk.Checkbutton(adv_rows[3], text=t("main.label.unread_only"), variable=self.flag_unread,
                           command=self.search).grid(row=0, column=_c, sticky="w", padx=(16, 0)); _c += 1
        if "status" in self.ADV_FILTERS:
            ttk.Label(adv_rows[3], text=t("main.label.status_colon")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.status = ttk.Combobox(adv_rows[3], width=11, state="readonly", values=[""])
            self.status.grid(row=0, column=_c, sticky="ew"); _exp.append(_c); _c += 1
            self.status.bind("<<ComboboxSelected>>", lambda e: self.search())
        if "liquid" in self.ADV_FILTERS:
            ttk.Label(adv_rows[3], text=t("main.label.liquid_colon")).grid(
                row=0, column=_c, sticky="w", padx=(16 if _c else 6, 3)); _c += 1
            self.liquid = ttk.Combobox(adv_rows[3], width=16, values=[""])
            self.liquid.grid(row=0, column=_c, sticky="ew", padx=(0, 8))
            _exp.append(_c); _c += 1
            self.liquid.bind("<<ComboboxSelected>>", lambda e: self.search())
            self.liquid.bind("<KeyRelease>", self.schedule_search)
        for col in _exp:
            adv_rows[3].columnconfigure(col, weight=1)

        for w in (self.vmin, self.vmax, self.chip, self.who,
                 self.dfrom, self.dto):
            if w is not None:
                w.bind("<KeyRelease>", self.schedule_search)
        for cb in (self.series_filter, self.understanding_filter,
                  self.action_filter):
            if cb is not None:
                cb.bind("<<ComboboxSelected>>", lambda e: self.search())

        # ===== フィルタ状態バー(A-2。条件があるときだけ表示) =====
        self.filter_bar = ttk.Frame(self, padding=(10, 2, 10, 0))
        self.filter_lbl = ttk.Label(self.filter_bar, text="")
        self.filter_lbl.pack(side="left")
        self._link(self.filter_bar, t("main.label.clear_all"), self.clear
                   ).pack(side="right")
        self._filter_bar_visible = False

        # ===== 結果グループ =====
        resgroup = ttk.Frame(self, padding=(0, 4, 0, 0))
        resgroup.pack(fill="both", expand=True, padx=10)
        self._resgroup = resgroup

        
        # 結果ヘッダ: 件数 + 新規実験記録(primary。色規則③=主操作は1つ)
        reshead = ttk.Frame(resgroup)
        reshead.pack(fill="x", pady=(0, 4))
        self._reshead = reshead
        self.result_header = ttk.Label(reshead, font=("", 10))
        self.result_header.pack(side="left")



        # 一覧: 格付けで行に色、ソート矢印、キー操作
        self._mid = ttk.PanedWindow(resgroup, orient="horizontal")
        self._mid.pack(fill="both", expand=True)
        self.nav_frame = ttk.Frame(self._mid, width=150)
        self._mid.add(self.nav_frame, weight=0)
        self.nav_visible = True
        self.nav_scroll = ScrollFrame(self.nav_frame)
        self.nav_scroll.pack(fill="both", expand=True)
        left = ttk.Frame(self._mid)
        self._mid.add(left, weight=3)
        ids = [c for c, _ in COLS]
        self.tree = ttk.Treeview(left, columns=ids, show="headings")
        configure_treeview_rows(self.tree, getattr(self, "dark", False))
        for c, w in COLS:
            self.tree.heading(c, text=HEAD[c],
                              command=lambda col=c: self.sort_by(col))
            self.tree.column(c, width=w, anchor="w",
                             stretch=(c == "result_summary"))
        self._apply_grade_tags()
        self.tree.pack(fill="both", expand=True)
        self.pane = ttk.Frame(self._mid, padding=(8, 0))
        self._mid.add(self.pane, weight=2)
        self.pane_visible = True
        self._pane_state = {"mode": self.WAVEFORM.get("default_mode", "all"),
                            "base": False, "axis": {},
                            "axis_open": False}
        self._sash_inited = False
        self._sash_after = None
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self._sash_after = self.after(150, self._init_sash)
        self._mid.bind("<Map>",
            lambda e: None if self._sash_inited else self._init_sash(),
            add="+")
        self.tree.bind("<Double-1>", self.show_detail)
        self.tree.bind("<Return>", self.show_detail)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Button-3>", self.popup_menu)
        self.bind("<Control-n>", lambda e: self.edit_run(None))

        # 右クリックメニュー: 主要操作へ直行
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=t("main.menu.show_detail"),
                              command=lambda: self.show_detail(None))
        self.menu.add_command(label=t("main.menu.edit_run"), command=self.edit_selected)
        if self.has_feature("steps"):
            self.menu.add_command(label=t("main.menu.edit_steps"),
                                  command=self.steps_selected)
        self.menu.add_separator()
        self.menu.add_command(label=t("main.menu.open_raw"),
                              command=lambda: self.open_selected("raw_path"))
        self.menu.add_command(label=t("main.menu.open_excel"),
                              command=lambda: self.open_selected("excel_path"))
        self.menu.add_command(label=t("main.menu.copy_paths"),
                              command=self.copy_paths)
        self.menu.add_separator()
        self.menu.add_command(label=t("btn.delete"), command=self.delete_selected)

        # 下段: 件数とヒント
        bottom = ttk.Frame(self, padding=(10, 6))
        bottom.pack(fill="x")
        self.count = ttk.Label(bottom, text="")
        self.count.pack(side="left")
        ttk.Label(bottom, foreground="#666",
                  text=t("main.label.hint")).pack(side="right")

        # ↑↓キーで一覧を移動(波形クリック後にフォーカスがCanvasへ移ると
        # Treeviewのクラスバインドが効かなくなるためアプリ全体で割り当てる。
        # ガード条件は _nav_list を参照)
        self.bind_all("<Down>", lambda e: self._nav_list(1))
        self.bind_all("<Up>", lambda e: self._nav_list(-1))

    # --- Views Integration ---
    from evidex.views import edit_series, _after_series_saved, open_series_manager, _refresh_series_manager, _render_series_detail, _new_series, _delete_series, _open_run_in_main, edit_run, edit_selected, delete_selected, validate_step, save_steps, step_form, open_steps_editor, open_schema_editor
    edit_series = edit_series
    _after_series_saved = _after_series_saved
    open_series_manager = open_series_manager
    _refresh_series_manager = _refresh_series_manager
    _render_series_detail = _render_series_detail
    _new_series = _new_series
    _delete_series = _delete_series
    _open_run_in_main = _open_run_in_main
    edit_run = edit_run
    edit_selected = edit_selected
    delete_selected = delete_selected
    validate_step = validate_step
    save_steps = save_steps
    step_form = step_form
    open_steps_editor = open_steps_editor
    open_schema_editor = open_schema_editor

    # --- Components Integration ---
    from evidex.components import _on_wave_click, _draw_wave
    _on_wave_click = _on_wave_click
    _draw_wave = _draw_wave
