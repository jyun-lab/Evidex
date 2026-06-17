import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from evidex.gui_runtime import bstyle
from evidex.components import DatePicker
from evidex.core.attachments import join_paths, split_paths
from evidex.core.filtering import norm
from evidex.core.i18n import t


class FileListEditor(ttk.Frame):
    def __init__(self, parent, app, initial_value="", owner=None):
        super().__init__(parent)
        self.app = app
        self.owner = owner
        self.paths = split_paths(initial_value)

        self.listbox = tk.Listbox(
            self,
            height=max(2, min(4, len(self.paths) or 2)),
            exportselection=False,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.listbox.yview
        )
        scrollbar.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(self)
        buttons.pack(side="left", padx=(6, 0), anchor="n")
        ttk.Button(
            buttons,
            text=t("run.files.add"),
            command=self.add_files,
        ).pack(fill="x")
        ttk.Button(
            buttons,
            text=t("run.files.remove_selected"),
            command=self.remove_selected,
        ).pack(fill="x", pady=(4, 0))
        self.refresh()

    def display_name(self, path):
        normalized = path.replace("\\", "/")
        return normalized.rsplit("/", 1)[-1] or normalized

    def refresh(self):
        self.listbox.delete(0, "end")
        for path in self.paths:
            self.listbox.insert("end", self.display_name(path))
        if self.paths:
            self.listbox.selection_set(0)

    def add_paths(self, paths):
        self.paths[:] = split_paths(self.paths + list(paths))
        self.refresh()

    def add_files(self):
        selected = self.app.choose_file_paths(self.owner)
        if selected:
            self.add_paths(selected)

    def remove_selected(self):
        selected = set(self.listbox.curselection())
        if not selected:
            return
        self.paths[:] = [
            path for index, path in enumerate(self.paths)
            if index not in selected
        ]
        self.refresh()

    def get(self):
        return join_paths(self.paths)


def edit_run(self, row):
    if not self.fields:
        messagebox.showinfo(t("msg.info"), t("run.msg.not_loaded"))
        return
    is_new = row is None
    data = dict(row) if row else {k: "" for k in self.fields}
    if is_new:
        today = datetime.date.today().strftime("%Y%m%d")
        n = sum(1 for r in self.rows
                if r.get("run_id", "").startswith(today)) + 1
        data["run_id"] = f"{today}-{n:02d}"
        if "date" in data:
            data["date"] = datetime.date.today().isoformat()
    win = tk.Toplevel(self)
    win.title(t("run.title.new") if is_new else t("run.title.edit", run_id=data.get('run_id', '')))
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    widgets = {}
    form_fields = [k for k in self.fields
                   if k not in self.HIDDEN_EDIT_FIELDS]
    for i, k in enumerate(form_fields):
        ttk.Label(frm, text=self.get_label(k)).grid(
            row=i, column=0, sticky="ne", padx=(0, 10), pady=2)
        if k in self.LONG_FIELDS:
            w = tk.Text(frm, width=46, height=3)
            w.insert("1.0", data.get(k, ""))
            w.grid(row=i, column=1, sticky="w", pady=2)
        elif k in self.CHOICES:
            w = ttk.Combobox(frm, width=44, values=self.CHOICES[k])
            w.set(data.get(k, ""))
            w.grid(row=i, column=1, sticky="w", pady=2)
        elif k == "date":
            cell = ttk.Frame(frm)
            cell.grid(row=i, column=1, sticky="w", pady=2)
            w = ttk.Entry(cell, width=34)
            w.insert(0, data.get(k, ""))
            w.pack(side="left")
            ttk.Button(cell, text=t("btn.calendar"),
                       command=lambda e=w: DatePicker(win, e)
                       ).pack(side="left", padx=(4, 0))
        elif k.endswith("_path"):
            w = FileListEditor(frm, self, data.get(k, ""), owner=win)
            w.grid(row=i, column=1, sticky="ew", pady=2)
        else:
            w = ttk.Entry(frm, width=46)
            w.insert(0, data.get(k, ""))
            w.grid(row=i, column=1, sticky="w", pady=2)
        widgets[k] = w
    frm.columnconfigure(1, weight=1)

    def collect():
        out = dict(data)  # 非表示欄(粘度など)の既存値を保持
        for k, w in widgets.items():
            out[k] = (w.get("1.0", "end-1c") if isinstance(w, tk.Text)
                      else w.get()).strip()
        return out

    def ok():
        out = collect()
        if self.apply_edit(row, out, is_new, parent=win):
            win.destroy()
            if (is_new and self.has_feature("steps")
                    and messagebox.askyesno(
                        t("run.msg.ask_steps_title"),
                        t("run.msg.ask_steps"))):
                self.open_steps_editor(out.get("run_id", ""))

    # 使用液体は工程が正本: 由来表示+その場で工程エディタへの導線
    n_rows = len(form_fields)
    if self.has_feature("steps") and "liquid" in self.STEP_FIELDS:
        ttk.Label(frm, text=t("run.label.liquid_from_steps")).grid(
            row=n_rows, column=0, sticky="ne", padx=(0, 10), pady=(8, 2))
        liq_cell = ttk.Frame(frm)
        liq_cell.grid(row=n_rows, column=1, sticky="w", pady=(8, 2))
        rid = data.get("run_id", "")
        seen = {}
        for s in self.steps.get(rid, []):
            v = (s.get("liquid", "") or "").strip()
            if v:
                seen.setdefault(norm(v), v)
        if is_new:
            ttk.Label(liq_cell, foreground="#888",
                      text=t("run.label.liquid_hint_new")).pack(side="left")
        else:
            ttk.Label(liq_cell, text=(" → ".join(seen.values())
                                      if seen else t("run.label.unentered"))
                      ).pack(side="left")
            ttk.Button(liq_cell, text=t("btn.edit_steps"),
                       command=lambda: (win.destroy(),
                                        self.open_steps_editor(rid))
                       ).pack(side="left", padx=(10, 0))

    bar = ttk.Frame(frm)
    bar.grid(row=n_rows + 1, column=1, sticky="e", pady=(10, 0))
    ttk.Button(bar, text=t("btn.cancel"), command=win.destroy).pack(
        side="right", padx=(6, 0))
    ttk.Button(bar, text=t("btn.save"), command=ok,
               **bstyle("primary.TButton")).pack(side="right")
    win.grab_set()
    win._widgets = widgets
    win._ok = ok
    return win

def edit_selected(self):
    sel = self.selected_rows()
    if not sel:
        messagebox.showinfo(t("msg.info"), t("run.msg.select_edit"))
        return
    self.edit_run(sel[0])

def delete_selected(self):
    sel = self.selected_rows()
    if not sel:
        messagebox.showinfo(t("msg.info"), t("run.msg.select_delete"))
        return
    ids = ", ".join(r.get("run_id", "?") for r in sel)
    if not messagebox.askyesno(
            t("run.msg.confirm_delete_title"),
            t("run.msg.confirm_delete", n=len(sel), ids=ids)):
        return
    for r in sel:
        self.rows.remove(r)
    if self.save_evidence():
        self.search()
