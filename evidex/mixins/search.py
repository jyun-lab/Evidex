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
from ..core.fields import get_label
from ..core.backup import prune_backups
from ..core.csvio import ensure_initial_csv_files, parse_device_csv
from ..core.filtering import norm, fnum, row_matches
from ..core.icons import icon_for_action, icon_for_liquid, HELP_TEXT
from ..core.table_style import stripe_tag
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame

class SearchMixin:
    def filters(self):
        f = {"text": self.text.get().strip() if getattr(self, "text", None) else ""}
        f["vmin"] = fnum(self.vmin.get()) if getattr(self, "vmin", None) else None
        f["vmax"] = fnum(self.vmax.get()) if getattr(self, "vmax", None) else None
        f["grades"] = [g for g, v in getattr(self, "gvars", {}).items() if v.get()]
        f["chip"] = self.chip.get().strip() if getattr(self, "chip", None) else ""
        f["status"] = self.status.get().strip() if getattr(self, "status", None) else ""
        f["who"] = self.who.get().strip() if getattr(self, "who", None) else ""
        f["liquid"] = self.liquid.get().strip() if getattr(self, "liquid", None) else ""
        f["unread"] = getattr(self, "flag_unread").get() if getattr(self, "flag_unread", None) else False
        f["dfrom"] = self.dfrom.get().strip() if getattr(self, "dfrom", None) else ""
        f["dto"] = self.dto.get().strip() if getattr(self, "dto", None) else ""
        f["series"] = self.series_filter.get().strip() if getattr(self, "series_filter", None) else ""
        f["understanding"] = self.understanding_filter.get().strip() if getattr(self, "understanding_filter", None) else ""
        f["action"] = self.action_filter.get().strip() if getattr(self, "action_filter", None) else ""
        f["has_raw"] = getattr(self, "flag_has_raw").get() if getattr(self, "flag_has_raw", None) else False
        f["no_steps"] = getattr(self, "flag_no_steps").get() if getattr(self, "flag_no_steps", None) else False
        return f

    def search(self):
        f = self.filters()
        base = self.rows
        if getattr(self, "nav_view", None) is not None:
            base = [r for r in self.rows if self._in_nav_view(r, self.nav_view)]
        self.hits = [r for r in base if row_matches(r, f, self.steps)]
        self.refresh()

    def schedule_search(self, *_):
        """入力のたびに呼ばれ、200ms静止したら検索(打鍵中の連発を防ぐ)"""
        if getattr(self, "_pending", None):
            self.after_cancel(self._pending)
        self._pending = self.after(200, self.search)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.hits):
            g = (r.get("grade", "") or "").strip().upper()
            tags = (g,) if g and self.has_feature("grading") else (stripe_tag(i),)
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             values=[(self._liquid_disp_icons(r)
                                      if c == "liquid_disp" else r.get(c, ""))
                                     for c, _ in COLS])
        from ..core.i18n import t
        self.count.config(text=t("search.label.count", hits=len(self.hits), total=len(self.rows)))
        self.result_header.config(
            text=t("search.label.result_header", hits=len(self.hits), total=len(self.rows)))
        for g in "ABC":   # 格付けチェックに現在の該当件数を表示
            if hasattr(self, "gchecks") and g in self.gchecks:
                n = sum(1 for r in self.hits
                        if (r.get("grade", "") or "").strip().upper() == g)
                self.gchecks[g].config(text=f"{g} {n}")
        for c, _ in COLS:  # ソート対象の列見出しに矢印
            arrow = ""
            if getattr(self, "_sort_col", None) == c:
                arrow = " ▼" if getattr(self, "_sort_rev", False) else " ▲"
            self.tree.heading(c, text=get_label(c) + arrow)
        # フィルタ状態バー(A-2): 条件があるときだけ表示
        txt = self._active_filter_text(self.filters())
        if txt:
            self.filter_lbl.config(text=txt)
            if not self._filter_bar_visible:
                self.filter_bar.pack(fill="x", before=self._resgroup)
                self._filter_bar_visible = True
        elif self._filter_bar_visible:
            self.filter_bar.pack_forget()
            self._filter_bar_visible = False
        self._update_adv_btn_text()
        if self.pane_visible:
            sel = self.tree.selection()
            self.render_pane(int(sel[0]) if sel else -1)

    def clear(self):
        for e in (getattr(self, "vmin", None), getattr(self, "vmax", None), getattr(self, "chip", None), 
                  getattr(self, "who", None), getattr(self, "text", None), getattr(self, "dfrom", None), getattr(self, "dto", None)):
            if e: e.delete(0, "end")
        for cb in (getattr(self, "status", None), getattr(self, "liquid", None), getattr(self, "series_filter", None),
                   getattr(self, "understanding_filter", None), getattr(self, "action_filter", None)):
            if cb: cb.set("")
        for v in (getattr(self, "flag_unread", None), getattr(self, "flag_has_raw", None), getattr(self, "flag_no_steps", None)):
            if v: v.set(False)
        for v in getattr(self, "gvars", {}).values():
            v.set(False)
        self.search()

    def toggle_unread(self):
        """カード配線は裁定1で外したが、テスト・将来用に温存。"""
        self.flag_unread.set(not self.flag_unread.get())
        self.search()

    def set_grade_only(self, g):
        """カード配線は裁定1で外したが、テスト・将来用に温存。"""
        for k, v in self.gvars.items():
            v.set(k == g)
        self.search()

    def toggle_adv(self):
        self.adv_visible = not self.adv_visible
        if self.adv_visible:
            self.adv.pack(fill="x", pady=(4, 0))
        else:
            self.adv.pack_forget()
        self._update_adv_btn_text()

    def _adv_active_count(self, f):
        """詳細フィルタのうち有効な条件数(ボタン文言用)"""
        n = 0
        if f["vmin"] is not None:
            n += 1
        if f["vmax"] is not None:
            n += 1
        for k in ("dfrom", "dto", "series", "chip", "who",
                 "understanding", "action"):
            if f.get(k):
                n += 1
        if f.get("has_raw"):
            n += 1
        if f.get("no_steps"):
            n += 1
        if f.get("grades"):
            n += 1
        if f.get("unread"):
            n += 1
        if f.get("status"):
            n += 1
        if f.get("liquid"):
            n += 1
        return n

    def _update_adv_btn_text(self):
        from ..core.i18n import t
        n = self._adv_active_count(self.filters())
        suffix = f"({n})" if n else ""
        arrow = "▾" if self.adv_visible else "▸"
        self.adv_btn.config(text=t("btn.adv_filter", n=suffix, arrow=arrow))

    def _active_filter_text(self, f):
        """フィルタ状態バーの文言。条件が無ければ空文字を返す(非表示)。"""

        def num(v):
            return str(int(v)) if v == int(v) else str(v)

        from ..core.i18n import t
        parts = []
        if getattr(self, "nav_view", None):
            kind, val = self.nav_view
            if kind == "preset":
                parts.append(t("search.filter.preset", val=val))
            else:
                facet = next((f for f in getattr(self, "FACETS", []) if f["field"] == kind), None)
                if facet:
                    parts.append(t(facet["label_key"]) + ": " + val)
                else:
                    parts.append(val)
        if f["text"]:
            parts.append(t("search.filter.text", val=f["text"]))
        if f["grades"]:
            parts.append(t("search.filter.grade", val=",".join(f["grades"])))
        if f["unread"]:
            from ..core.fields import CHOICES
            u_choices = [c for c in CHOICES.get("understanding", []) if c]
            unread_val = u_choices[0] if u_choices else ""
            parts.append(unread_val)
        if f["status"]:
            parts.append(t("search.filter.status", val=f["status"]))
        if f["liquid"]:
            parts.append(t("search.filter.liquid", val=f["liquid"]))
        vmin, vmax = f["vmin"], f["vmax"]
        if vmin is not None and vmax is not None:
            parts.append(t("search.filter.viscosity_range", min=num(vmin), max=num(vmax)))
        elif vmin is not None:
            parts.append(t("search.filter.viscosity_min", min=num(vmin)))
        elif vmax is not None:
            parts.append(t("search.filter.viscosity_max", max=num(vmax)))
        if f["dfrom"] and f["dto"]:
            parts.append(t("search.filter.date_range", start=f["dfrom"], end=f["dto"]))
        elif f["dfrom"]:
            parts.append(t("search.filter.date_min", start=f["dfrom"]))
        elif f["dto"]:
            parts.append(t("search.filter.date_max", end=f["dto"]))
        if f["series"]:
            parts.append(t("search.filter.series", val=f["series"]))
        if f["understanding"]:
            parts.append(t("search.filter.understanding", val=f["understanding"]))
        if f["action"]:
            parts.append(t("search.filter.action", val=f["action"]))
        if f["chip"]:
            parts.append(t("search.filter.chip", val=f["chip"]))
        if f["who"]:
            parts.append(t("search.filter.experimenter", val=f["who"]))
        if f["has_raw"]:
            parts.append(t("search.filter.has_raw"))
        if f["no_steps"]:
            parts.append(t("search.filter.no_steps"))
        if not parts:
            return ""
        return t("search.msg.filtering", conditions=" · ".join(parts))
