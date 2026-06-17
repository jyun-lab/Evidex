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
from ..gui_runtime import THEMED, MPL, tb, bstyle, resolve_tk_font
from ..components import Tooltip, DatePicker, ScrollFrame
from ..core.i18n import t

class TreeMixin:
    def sort_by(self, col):
        def key(r):
            raw = (self._liquid_disp(r) if col == "liquid_disp"
                   else r.get(col, ""))
            v = fnum(raw)
            return (0, v) if v is not None else (1, raw)
        rev = (getattr(self, "_sort_col", None) == col
               and not getattr(self, "_sort_rev", False))
        self.hits.sort(key=key, reverse=rev)
        self._sort_col, self._sort_rev = col, rev
        self.refresh()

    # ---------- actions ----------
    def selected_rows(self):
        return [self.hits[int(i)] for i in self.tree.selection()]

    def on_select(self, *_):
        if not self.pane_visible:
            return
        sel = self.tree.selection()
        if sel:
            self.render_pane(int(sel[0]))

    def popup_menu(self, e):
        iid = self.tree.identify_row(e.y)
        if iid:
            self.tree.selection_set(iid)
        self.menu.tk_popup(e.x_root, e.y_root)

    def copy_paths(self):
        paths = []
        for row in self.selected_rows():
            paths.extend(split_paths(row.get("raw_path", "")))
        if not paths:
            messagebox.showinfo(t("msg.info"), t("tree.msg.select_raw_path"))
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(paths))
        self.count.config(text=t("tree.msg.paths_copied", n=len(paths)))

    def show_detail(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        self.open_detail(int(sel[0]))

    def steps_selected(self):
        sel = self.selected_rows()
        if not sel:
            messagebox.showinfo(t("msg.info"), t("tree.msg.select_row"))
            return
        self.open_steps_editor(sel[0].get("run_id", ""))

    def open_selected(self, col):
        sel = self.selected_rows()
        if not sel:
            messagebox.showinfo(t("msg.info"), t("tree.msg.select_row"))
            return
        self.open_path(sel[0], col)

    # ---------- data ----------
