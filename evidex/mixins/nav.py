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
from ..core.csvio import ensure_initial_csv_files, parse_device_csv
from ..core.filtering import norm, fnum, row_matches
from ..core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame
from ..core.i18n import t

class NavMixin:
    def _nav_list(self, d):
        """↑↓キーで一覧の選択を1件移動する(bind_allハンドラ)。
        入力欄・別ウィンドウ・一覧自身では奪わない(二重移動/誤動作防止)。"""
        w = self.focus_get()
        if w is None:
            return
        # 1) 入力中は奪わない(Entry/Text/Combobox/Spinboxの↑↓は本来の動作)
        if w.winfo_class() in ("TEntry", "Entry", "Text", "TCombobox",
                               "TSpinbox", "Spinbox"):
            return
        # 2) 別ウィンドウ(編集フォーム・詳細ウィンドウ等)にいる間は奪わない
        if w.winfo_toplevel() is not self:
            return
        # 3) 一覧自身がフォーカス時はTreeviewの既定動作に任せる(二重移動防止)
        if w is self.tree:
            return
        sel = self.tree.selection()
        cur = int(sel[0]) if sel else -1
        new = max(0, min(len(self.hits) - 1, cur + d))
        if new == cur or not self.hits:
            return "break"
        self.tree.selection_set(str(new))
        self.tree.see(str(new))
        return "break"

    def build_nav(self):
        if not hasattr(self, "nav_scroll"):
            return
        for w in self.nav_scroll.inner.winfo_children():
            w.destroy()
        
        def set_view(view):
            self.nav_view = view
            self.search()
            self.build_nav()
            
        def is_sel(view):
            return getattr(self, "nav_view", None) == view

        def _item(parent, label, view, count):
            f = ttk.Frame(parent, padding=(12, 2))
            f.pack(fill="x")
            bg = "#E8F0FE" if is_sel(view) else ("#2C3136" if getattr(self, "dark", False) else "#FFFFFF")
            fg = "#1967D2" if is_sel(view) else ("#CCCCCC" if getattr(self, "dark", False) else "#333333")
            if is_sel(view):
                f.config(style="SelectedNav.TFrame")
                # Need style setup, but for now just basic ttk frame.
                # Actually, ttkbootstrap handles colors, we might just use labels.
            lbl = ttk.Label(f, text=label, foreground=fg, background=bg, cursor="hand2")
            lbl.pack(side="left")
            cnt = ttk.Label(f, text=str(count), foreground="#888", background=bg)
            cnt.pack(side="right")
            for w in (f, lbl, cnt):
                w.bind("<Button-1>", lambda e, v=view: set_view(v))

        # "すべて"
        _item(self.nav_scroll.inner, t("nav.section.all"), None, len(self.rows))
        
        # セクション生成
        def _sec(title, kind, items):
            if not items:
                return
            open_st = self._nav_open.get(kind, False)
            sf = ttk.Frame(self.nav_scroll.inner)
            sf.pack(fill="x", pady=(4, 0))
            head = ttk.Frame(sf)
            head.pack(fill="x")
            arrow = "▾ " if open_st else "▸ "
            hlbl = ttk.Label(head, text=arrow + title, font=("", 9, "bold"), cursor="hand2")
            hlbl.pack(side="left", padx=4)
            
            body = ttk.Frame(sf)
            if open_st:
                body.pack(fill="x")
                
            def toggle(e, k=kind, b=body, hl=hlbl, t=title):
                self._nav_open[k] = not self._nav_open[k]
                if self._nav_open[k]:
                    b.pack(fill="x")
                    hl.config(text="▾ " + t)
                else:
                    b.pack_forget()
                    hl.config(text="▸ " + t)
            hlbl.bind("<Button-1>", toggle)
            
            for label, val, cnt in items:
                _item(body, label, (kind, val), cnt)
                
        for facet in getattr(self, "FACETS", []):
            field = facet["field"]
            label_key = facet.get("label_key", "")
            source = facet["source"]
            match_type = facet["match"]
            
            if source == "data":
                vals = sorted({r.get(field, "") for r in self.rows if r.get(field, "").strip()})
                if match_type == "norm":
                    items = [(v, v, sum(1 for r in self.rows if norm(r.get(field, "")) == norm(v))) for v in vals]
                else: # exact, etc.
                    items = [(v, v, sum(1 for r in self.rows if r.get(field, "") == v)) for v in vals]
            elif source == "choices":
                choices = [c for c in getattr(self, "CHOICES", {}).get(field, []) if c]
                items = []
                for c in choices:
                    if match_type == "strip":
                        cnt = sum(1 for r in self.rows if r.get(field, "").strip() == c)
                    elif match_type == "upper":
                        cnt = sum(1 for r in self.rows if r.get(field, "").strip().upper() == c)
                    else:
                        cnt = sum(1 for r in self.rows if r.get(field, "") == c)
                    if cnt:
                        items.append((c, c, cnt))
            
            section_label = t(label_key) if label_key else self.get_label(field)
            _sec(section_label, field, items)
        
        # 保存した検索
        prefs = self._load_prefs().get("presets", {})
        p_items = []
        for p in sorted(prefs.keys()):
            f_p = self._preset_to_filters(prefs[p])
            cnt = sum(1 for r in self.rows if row_matches(r, f_p, self.steps))
            p_items.append((p, p, cnt))
        _sec(t("nav.section.presets"), "preset", p_items)

    def _in_nav_view(self, row, view):
        if view is None:
            return True
        kind, val = view
        if kind == "preset":
            st = self._load_prefs().get("presets", {}).get(val)
            if not st:
                return True
            f = self._preset_to_filters(st)
            return row_matches(row, f, self.steps)
            
        facet = next((f for f in getattr(self, "FACETS", []) if f["field"] == kind), None)
        if facet:
            match_type = facet["match"]
            row_val = row.get(kind, "")
            if match_type == "norm":
                return norm(row_val) == norm(val)
            elif match_type == "strip":
                return row_val.strip() == val
            elif match_type == "upper":
                return row_val.strip().upper() == val
            else:
                return row_val == val
                
        return True

    def toggle_nav(self):
        if self.nav_visible:
            self._mid.forget(self.nav_frame)
            self.nav_visible = False
        else:
            self._mid.insert(0, self.nav_frame, weight=0)
            self.nav_visible = True
            self._sash_after = self.after(100, self._init_sash)
