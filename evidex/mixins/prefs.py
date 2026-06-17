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

class PrefsMixin:
    @staticmethod
    def _widget_value(widget, default=""):
        return widget.get() if widget is not None else default

    def _prefs_path(self):
        return self.path.parent / "evidex_prefs.json"

    def _load_prefs(self):
        try:
            return json.loads(
                self._prefs_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_prefs(self, prefs):
        try:
            self._prefs_path().write_text(
                json.dumps(prefs, ensure_ascii=False, indent=1),
                encoding="utf-8")
            return True
        except Exception as e:
            messagebox.showerror(t("data.msg.save_error"), str(e))
            return False

    def _refresh_presets(self):
        self.preset_box["values"] = sorted(
            self._load_prefs().get("presets", {}))

    def _filter_state(self):
        return {"text": self.text.get(),
                "status": self._widget_value(self.status),
                "liquid": self._widget_value(self.liquid),
                "grades": {g: v.get() for g, v in self.gvars.items()},
                "unread": self._widget_value(self.flag_unread, False),
                "vmin": self._widget_value(self.vmin),
                "vmax": self._widget_value(self.vmax),
                "chip": self._widget_value(self.chip),
                "who": self._widget_value(self.who),
                "dfrom": self._widget_value(self.dfrom),
                "dto": self._widget_value(self.dto),
                "series": self._widget_value(self.series_filter),
                "understanding": self._widget_value(self.understanding_filter),
                "action": self._widget_value(self.action_filter),
                "has_raw": self._widget_value(self.flag_has_raw, False),
                "no_steps": self._widget_value(self.flag_no_steps, False)}

    def _apply_state(self, st):
        for w, key in ((self.text, "text"), (self.vmin, "vmin"),
                       (self.vmax, "vmax"), (self.chip, "chip"),
                       (self.who, "who"), (self.dfrom, "dfrom"),
                       (self.dto, "dto")):
            if w is None:
                continue
            w.delete(0, "end")
            w.insert(0, st.get(key, ""))
        for widget, key in (
            (self.status, "status"), (self.liquid, "liquid"),
            (self.series_filter, "series"),
            (self.understanding_filter, "understanding"),
            (self.action_filter, "action"),
        ):
            if widget is not None:
                widget.set(st.get(key, ""))
        for g, v in self.gvars.items():
            v.set(bool(st.get("grades", {}).get(g, False)))
        for variable, key in (
            (self.flag_unread, "unread"),
            (self.flag_has_raw, "has_raw"),
            (self.flag_no_steps, "no_steps"),
        ):
            if variable is not None:
                variable.set(bool(st.get(key, False)))
        self.search()

    def save_preset(self):
        from tkinter import simpledialog
        name = (simpledialog.askstring(
            t("btn.preset_save"), t("prefs.msg.preset_name"), parent=self) or "").strip()
        if not name:
            return
        prefs = self._load_prefs()
        prefs.setdefault("presets", {})[name] = self._filter_state()
        if self._save_prefs(prefs):
            self._refresh_presets()
            self.preset_box.set(name)

    def apply_preset(self, name):
        st = self._load_prefs().get("presets", {}).get(name)
        if st:
            self._apply_state(st)

    def _preset_to_filters(self, st):
        return {
            "vmin": fnum(st.get("vmin")),
            "vmax": fnum(st.get("vmax")),
            "grades": [g for g, v in st.get("grades", {}).items() if v],
            "chip": st.get("chip", "").strip(),
            "status": st.get("status", "").strip(),
            "who": st.get("who", "").strip(),
            "liquid": st.get("liquid", "").strip(),
            "unread": bool(st.get("unread", False)),
            "text": st.get("text", "").strip(),
            "dfrom": st.get("dfrom", "").strip(),
            "dto": st.get("dto", "").strip(),
            "series": st.get("series", "").strip(),
            "understanding": st.get("understanding", "").strip(),
            "action": st.get("action", "").strip(),
            "has_raw": bool(st.get("has_raw", False)),
            "no_steps": bool(st.get("no_steps", False)),
        }
