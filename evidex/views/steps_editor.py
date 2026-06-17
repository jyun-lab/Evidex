import tkinter as tk
from tkinter import ttk, messagebox
import csv
import datetime
import shutil
from evidex.components import Tooltip
from evidex.core.backup import prune_backups
from evidex.core.filtering import fnum
from evidex.core.icons import icon_for_action, HELP_TEXT
from evidex.core.table_style import configure_treeview_rows, stripe_tag
from evidex.gui_runtime import bstyle
from evidex.core.i18n import t

def validate_step(self, out):
    """問題なければNone、あればエラーメッセージを返す"""
    primary = self.STEP_FORM[0][0] if self.STEP_FORM else None
    if primary and not out.get(primary, "").strip():
        return t("steps.msg.action_required")
    v = out.get("viscosity_mPas", "") if "viscosity_mPas" in self.STEP_FIELDS else ""
    if v and fnum(v) is None:
        return t("steps.msg.viscosity_num")
    sr = out.get("data_start_row", "") if "data_start_row" in self.STEP_FIELDS else ""
    er = out.get("data_end_row", "") if "data_end_row" in self.STEP_FIELDS else ""
    for val, lab in ((sr, t("steps.label.data_start_row")), (er, t("steps.label.data_end_row"))):
        if val and fnum(val) is None:
            return t("steps.msg.row_num", label=lab)
    if sr and er and fnum(sr) > fnum(er):
        return t("steps.msg.row_order")
    if (sr and fnum(sr) < 2) or (er and fnum(er) < 2):
        return t("steps.msg.row_min")
    for k, label in [("drop_volume_uL", t("steps.label.drop_volume")),
                     ("duration_min", t("steps.label.duration"))]:
        if k not in self.STEP_FIELDS:
            continue
        v = out.get(k, "").strip()
        if v and fnum(v) is None:
            return t("steps.msg.num_only", label=label)
    return None

def save_steps(self):
    sp = self.path.parent / "steps.csv"
    bdir = self.path.parent / "backup"
    bdir.mkdir(exist_ok=True)
    if sp.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(sp, bdir / f"steps-{stamp}.csv")
        prune_backups(bdir)
    fields = self.step_fields or self.STEP_FIELDS
    for k in self.STEP_FIELDS:           # 旧形式でも必須列は確保
        if k not in fields:
            fields.append(k)
    self.step_fields = fields
    with open(sp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for rid in sorted(self.steps):
            for s in self.steps[rid]:
                w.writerow({k: s.get(k, "") for k in fields})
    self.update_liquid_choices()

def step_form(self, parent, data, on_ok):
    win = tk.Toplevel(parent)
    win.title(t("steps.title.input"))
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    widgets = {}
    for i, (k, label) in enumerate(self.STEP_FORM):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="ne",
                                        padx=(0, 10), pady=2)
        if k == "action":
            w = ttk.Combobox(frm, width=34, values=self.ACTION_CHOICES)
            w.set(data.get(k, ""))
        elif k == "liquid":
            w = ttk.Combobox(frm, width=34,
                             values=self.known_liquids())
            w.set(data.get(k, ""))
        elif k in ("data_start_row", "data_end_row"):
            cell = ttk.Frame(frm)
            w = ttk.Entry(cell, width=12)
            w.insert(0, data.get(k, ""))
            w.pack(side="left")
            Tooltip(w, HELP_TEXT["data_rows"])

            def paste(e=w):
                v = getattr(self, "_last_click_row", None)
                if v is None:
                    messagebox.showinfo(
                        t("msg.info"), t("steps.msg.click_wave_first"),
                        parent=win)
                    return
                e.delete(0, "end")
                e.insert(0, str(v))
            ttk.Button(cell, text=t("steps.btn.from_wave"), width=6,
                       command=paste).pack(side="left", padx=(6, 0))
            cell.grid(row=i, column=1, sticky="w", pady=2)
            widgets[k] = w
            continue
        else:
            w = ttk.Entry(frm, width=36)
            w.insert(0, data.get(k, ""))
        w.grid(row=i, column=1, sticky="w", pady=2)
        widgets[k] = w

    def ok():
        out = dict(data)
        for k, w in widgets.items():
            out[k] = w.get().strip()
        err = self.validate_step(out)
        if err:
            messagebox.showerror(t("msg.input_error"), err, parent=win)
            return
        win.destroy()
        on_ok(out)

    bar = ttk.Frame(frm)
    bar.grid(row=len(self.STEP_FORM), column=1, sticky="e", pady=(10, 0))
    ttk.Button(bar, text=t("btn.cancel"), command=win.destroy).pack(
        side="right", padx=(6, 0))
    ttk.Button(bar, text=t("btn.ok"), command=ok).pack(side="right")
    win.grab_set()
    win._widgets = widgets
    win._ok = ok
    return win

def open_steps_editor(self, run_id):
    if not run_id:
        messagebox.showinfo(t("msg.info"), t("steps.msg.no_run_id"))
        return
    ws = [dict(s) for s in self.steps.get(run_id, [])]
    win = tk.Toplevel(self)
    win.title(t("steps.title.edit", run_id=run_id))
    win.geometry("760x470")
    win.minsize(640, 400)
    cols = [("step_no", t("steps.col.no"), 50)]
    for field, label in self.STEP_FORM:
        width = 180 if field == "notes" else 110
        cols.append((field, label, width))
    tree = ttk.Treeview(win, columns=[c for c, _, _ in cols],
                        show="headings", height=10)
    configure_treeview_rows(tree, getattr(self, "dark", False))
    for c, lab, wd in cols:
        tree.heading(c, text=lab)
        tree.column(c, width=wd, anchor="w")
    # packは下部バー定義後に行う(縮小時にボタンが切られるのを防ぐ)

    def refresh():
        tree.delete(*tree.get_children())
        for i, s in enumerate(ws):
            def cell(c):
                if c == "action":
                    act = s.get(c, "")
                    return f"{icon_for_action(act)} {act}".strip()
                return s.get(c, "")
            tree.insert("", "end", iid=str(i), tags=(stripe_tag(i),),
                        values=[i + 1] + [cell(c) for c, _, _ in cols[1:]])

    def sel_index():
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def append(out):
        ws.append(out)
        refresh()

    def add():
        self.step_form(win, {}, append)

    def edit():
        i = sel_index()
        if i is None:
            messagebox.showinfo(t("msg.info"), t("steps.msg.select_edit"),
                                parent=win)
            return
        self.step_form(win, dict(ws[i]),
                       lambda out: (ws.__setitem__(i, out), refresh()))

    def delete():
        i = sel_index()
        if i is None:
            messagebox.showinfo(t("msg.info"), t("steps.msg.select_delete"),
                                parent=win)
            return
        del ws[i]
        refresh()

    def move(d):
        i = sel_index()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(ws):
            ws[i], ws[j] = ws[j], ws[i]
            refresh()
            tree.selection_set(str(j))

    def save():
        for i, s in enumerate(ws):       # 並び順から自動採番
            s["run_id"] = run_id
            s["step_no"] = str(i + 1)
        if ws:
            self.steps[run_id] = ws
        else:
            self.steps.pop(run_id, None)
        self.save_steps()
        self.search()
        win.destroy()

    # --- 基準行(波形補正用)の表示と設定 ---
    run_row = next((r for r in self.rows
                    if r.get("run_id", "") == run_id), None)

    def base_text():
        br = fnum((run_row or {}).get("base_row", ""))
        if br is None:
            return t("steps.label.base_unassigned")
        br = int(br)
        for s in ws:
            sr, er = fnum(s.get("data_start_row", "")), \
                     fnum(s.get("data_end_row", ""))
            if sr is not None and er is not None and sr <= br <= er:
                return t("steps.label.base_assigned", br=br, step_no=s.get('step_no','?'), action=s.get('action',''), liquid=s.get('liquid',''))
        return t("steps.label.base_outside", br=br)

    baseline_bar = None
    base_lbl = None
    if self.has_feature("baseline"):
        baseline_bar = ttk.Frame(win, padding=(10, 0, 10, 2))
        base_lbl = ttk.Label(baseline_bar, text=base_text(),
                             foreground="#666")
        base_lbl.pack(side="left")

    def set_baseline(row_value=None):
        i = sel_index()
        if i is None:
            messagebox.showinfo(t("msg.info"), t("steps.msg.select_base"),
                                parent=win)
            return False
        if run_row is None:
            messagebox.showerror(t("msg.error"), t("steps.msg.no_run_loaded"),
                                 parent=win)
            return False
        s = ws[i]
        sr = fnum(s.get("data_start_row", ""))
        er = fnum(s.get("data_end_row", ""))
        if row_value is None:
            prompt = t("steps.msg.base_prompt_desc")
            if sr is not None and er is not None:
                prompt += t("steps.msg.base_prompt_range", sr=int(sr), er=int(er))
            from tkinter import simpledialog
            row_value = simpledialog.askinteger(
                t("steps.title.base_prompt"), prompt, parent=win,
                initialvalue=int(sr) if sr is not None else 2)
        if row_value is None:
            return False
        v = fnum(row_value)
        if v is None or v < 2:
            messagebox.showerror(t("msg.input_error"),
                                 t("steps.msg.base_min"), parent=win)
            return False
        if sr is not None and er is not None and not (sr <= v <= er):
            if not messagebox.askyesno(
                    t("msg.confirm"),
                    t("steps.msg.base_outside_confirm", v=int(v), step_no=s.get('step_no','?'), sr=int(sr), er=int(er)),
                    parent=win):
                return False
        run_row["base_row"] = str(int(v))
        if not self.save_evidence():
            return False
        base_lbl.config(text=base_text())
        self._wave_cache.clear() if hasattr(self, "_wave_cache") else None
        self.search()
        return True

    def clear_baseline():
        if run_row is None:
            return
        run_row["base_row"] = ""
        if self.save_evidence():
            base_lbl.config(text=base_text())
            self.search()

    if baseline_bar is not None:
        ttk.Button(baseline_bar, text=t("steps.btn.set_base"),
                   command=set_baseline).pack(side="right", padx=3)
        self._link(baseline_bar, t("steps.btn.clear_base"),
                   clear_baseline).pack(side="right", padx=8)

    bar = ttk.Frame(win, padding=(10, 4, 10, 10))
    for label, cmd in [(t("btn.add"), add), (t("btn.edit"), edit), (t("btn.delete"), delete),
                       (t("btn.up"), lambda: move(-1)),
                       (t("btn.down"), lambda: move(1))]:
        ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=3)
    ttk.Button(bar, text=t("btn.cancel"), command=win.destroy).pack(
        side="right", padx=3)
    ttk.Button(bar, text=t("btn.save"), command=save).pack(side="right", padx=3)
    hint_bar = ttk.Frame(win, padding=(10, 0, 10, 4))
    hint_label = ttk.Label(
        hint_bar,
        text=t("steps.label.auto_no"),
        foreground="#666",
        justify="left",
    )
    hint_label.pack(fill="x")
    hint_bar.bind(
        "<Configure>",
        lambda event: hint_label.configure(
            wraplength=max(160, event.width - 20)
        ),
        add="+",
    )
    # 下から順に確保: ボタンバー → 基準行バー → 残り全部が一覧
    bar.pack(side="bottom", fill="x")
    hint_bar.pack(side="bottom", fill="x")
    if baseline_bar is not None:
        baseline_bar.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True, padx=10, pady=(10, 4))
    refresh()
    win.grab_set()
    win._ws = ws
    win._append = append
    win._move = move
    win._delete = delete
    win._save = save
    win._tree = tree
    win._hint_bar = hint_bar
    win._hint_label = hint_label
    win._set_baseline = set_baseline
    win._clear_baseline = clear_baseline
    win._base_lbl = base_lbl
    return win
