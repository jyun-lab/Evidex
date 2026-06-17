import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter import font as tkfont
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
from ..core.table_style import configure_treeview_rows
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame

class ThemeMixin:
    def _resolve_ui_font(self):
        """UIフォントの候補リストから利用可能なフォントを解決する"""
        try:
            avail = set(tkfont.families(self))
        except tk.TclError:
            return None
        for fam in config._UI_FONT_CANDIDATES:
            if fam in avail:
                return fam
        return None

    # ---------- UI ----------
    def toggle_theme(self):
        if not THEMED:
            return
        self.dark = not getattr(self, "dark", False)
        self.style.theme_use("darkly" if self.dark else "flatly")
        self._apply_grade_tags()
        if hasattr(self, "v_dark"):
            self.v_dark.set(self.dark)
        self.on_select()

    def _apply_grade_tags(self):
        if hasattr(self, "tree"):
            configure_treeview_rows(self.tree, getattr(self, "dark", False))
        light = {"A": "#E6F3EA", "B": "#FCF0DC", "C": "#ECEFF1"}
        dark = {"A": "#1F3B2A", "B": "#4A3A1A", "C": "#2E3439"}
        palette = dark if getattr(self, "dark", False) else light
        colors = {
            grade: palette.get(grade, color)
            for grade, color in getattr(self, "GCOL", {}).items()
        }
        for g, c in colors.items():
            self.tree.tag_configure(g, background=c)

    def _menu_dark(self):
        if self.v_dark.get() != getattr(self, "dark", False):
            self.toggle_theme()

    def open_settings(self):
        from ..core import settings
        from ..packs import get_pack_names
        from ..core.i18n import t

        top = tk.Toplevel(self)
        top.title(t("dialog.settings.title"))
        top.transient(self)
        top.grab_set()

        outer = ttk.Frame(top)
        outer.pack(fill="both", expand=True)

        # Keep actions visible when DPI scaling or a short screen increases
        # the content's requested height. Pack the fixed bottom bar first.
        btn_frame = ttk.Frame(outer, padding=(16, 8, 16, 16))
        btn_frame.pack(side="bottom", fill="x")

        frame = ttk.Frame(outer, padding=(16, 16, 16, 8))
        frame.pack(side="top", fill="both", expand=True)

        ttk.Label(frame, text=t("dialog.settings.pack")).pack(anchor="w", pady=(0, 4))
        pack_var = tk.StringVar(value=settings.get("active_pack"))
        pack_cb = ttk.Combobox(frame, textvariable=pack_var, values=list(get_pack_names()), state="readonly")
        pack_cb.pack(fill="x", pady=(0, 12))

        ttk.Label(frame, text=t("dialog.settings.theme")).pack(anchor="w", pady=(0, 4))
        theme_var = tk.StringVar(value=settings.get("theme"))
        theme_cb = ttk.Combobox(frame, textvariable=theme_var, values=["system", "light", "dark"], state="readonly")
        theme_cb.pack(fill="x", pady=(0, 12))

        ttk.Label(frame, text=t("dialog.settings.language")).pack(anchor="w", pady=(0, 4))
        lang_map = {"ja": "日本語", "en": "English"}
        rev_map = {v: k for k, v in lang_map.items()}
        current_lang = settings.get("language", "en")
        
        lang_var = tk.StringVar(value=lang_map.get(current_lang, "English"))
        lang_cb = ttk.Combobox(frame, textvariable=lang_var, values=list(lang_map.values()), state="readonly")
        lang_cb.pack(fill="x", pady=(0, 16))

        def save():
            old_pack = settings.get("active_pack")
            new_pack = pack_var.get()
            old_theme = settings.get("theme")
            new_theme = theme_var.get()
            old_lang = settings.get("language", "en")
            new_lang = rev_map.get(lang_var.get(), "en")

            settings.set("active_pack", new_pack)
            settings.set("theme", new_theme)
            settings.set("language", new_lang)

            target_dark = (new_theme == "dark")
            current_dark = getattr(self, "dark", False)
            if target_dark != current_dark:
                self.toggle_theme()

            if old_pack != new_pack or old_lang != new_lang:
                messagebox.showinfo(t("dialog.settings.title"), t("dialog.settings.msg_reboot"), parent=top)
            
            top.destroy()

        cancel_btn = ttk.Button(
            btn_frame, text=t("btn.cancel"), command=top.destroy
        )
        cancel_btn.pack(side="right", padx=(8, 0))
        save_btn = ttk.Button(
            btn_frame,
            text=t("btn.save"),
            command=save,
            style="primary.TButton" if THEMED else "",
        )
        save_btn.pack(side="right")

        top.update_idletasks()
        screen_w = top.winfo_screenwidth()
        screen_h = top.winfo_screenheight()
        max_w = max(320, screen_w - 80)
        max_h = max(220, screen_h - 80)
        width = min(max(360, top.winfo_reqwidth()), max_w)
        height = min(max(280, top.winfo_reqheight()), max_h)
        top.minsize(min(360, max_w), min(top.winfo_reqheight(), max_h))

        self.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - height) // 2)
        x = max(0, min(x, screen_w - width))
        y = max(0, min(y, screen_h - height))
        top.geometry(f"{width}x{height}+{x}+{y}")

        top._settings_button_bar = btn_frame
        top._settings_save_button = save_btn
        top._settings_cancel_button = cancel_btn
        return top
