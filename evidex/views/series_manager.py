import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from evidex.components import ScrollFrame
from evidex.core.table_style import configure_treeview_rows, stripe_tag
from evidex.gui_runtime import bstyle
from evidex.core.filtering import norm
from evidex.core.i18n import t

def edit_series(self, sid):
    """series.csv(既知マップ)のGUI編集"""
    SERIES_JP = {"experimenter": t("series.field.experimenter"), "period": t("series.field.period"),
                 "objective": t("series.field.objective"), "claim": t("series.field.claim"),
                 "established_knowns": t("series.field.established_knowns"),
                 "unresolved": t("series.field.unresolved"),
                 "evidence_docs": t("series.field.evidence_docs"),
                 "my_assessment": t("series.field.my_assessment")}
    LONG = {"objective", "claim", "established_knowns", "unresolved",
            "evidence_docs", "my_assessment"}
    srow = next((s for s in self.series_rows
                 if (s.get("series_id", "") or "").strip() == sid), None)
    is_new = srow is None
    data = dict(srow) if srow else {k: "" for k in self.series_fields}
    data["series_id"] = sid
    win = tk.Toplevel(self)
    win.title(t("series.title.edit", sid=sid))
    win.minsize(560, 420)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    widgets = {}
    fields = [f for f in self.series_fields if f != "series_id"]
    ttk.Label(frm, text="series_id").grid(row=0, column=0, sticky="ne",
                                          padx=(0, 10), pady=2)
    ttk.Label(frm, text=sid, font=("", 10, "bold")).grid(
        row=0, column=1, sticky="w", pady=2)
    for i, k in enumerate(fields, start=1):
        ttk.Label(frm, text=SERIES_JP.get(k, k)).grid(
            row=i, column=0, sticky="ne", padx=(0, 10), pady=2)
        if k in LONG:
            w = tk.Text(frm, width=52, height=3)
            w.insert("1.0", data.get(k, ""))
        else:
            w = ttk.Entry(frm, width=40)
            w.insert(0, data.get(k, ""))
        w.grid(row=i, column=1, sticky="we", pady=2)
        widgets[k] = w
    frm.columnconfigure(1, weight=1)

    def ok():
        for k, w in widgets.items():
            if isinstance(w, tk.Text):
                data[k] = w.get("1.0", "end").strip()
            else:
                data[k] = w.get().strip()
        if is_new:
            self.series_rows.append(data)
        else:
            srow.update(data)
        if self.save_series():
            win.destroy()
            self.on_select()   # 系列タブを再描画
            self._after_series_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=len(fields) + 1, column=1, sticky="e", pady=(10, 0))
    ttk.Button(bar, text=t("btn.cancel"),
               command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(bar, text=t("btn.save"), command=ok,
               **bstyle("primary.TButton")).pack(side="right")
    win.grab_set()
    win._widgets = widgets
    win._ok = ok
    return win

def _after_series_saved(self):
    """series.csv保存後に呼ぶ共有フック(新規・編集どちらの保存からも)。
    詳細フィルタの「シリーズ」候補を最新化し、シリーズ管理ウィンドウが
    開いていれば一覧・詳細パネルを再描画する(計画書C-2)。"""
    self.update_series_choices()
    if getattr(self, "_series_win", None) is not None:
        self._refresh_series_manager()

def open_series_manager(self):
    """シリーズ管理ウィンドウを開く(多重起動防止: 既存なら lift)。"""
    win = getattr(self, "_series_win", None)
    if win is not None and win.winfo_exists():
        win.lift()
        return win

    win = tk.Toplevel(self)
    win.title(t("series.title.manager"))
    win.minsize(720, 460)
    win.geometry("880x540")

    # レイアウト鉄則①: 下部バーをside="bottom"で先にpack
    bar = ttk.Frame(win, padding=(10, 8))
    bar.pack(side="bottom", fill="x")
    ttk.Button(bar, text=t("btn.new_series"),
               command=lambda: self._new_series(win),
               **bstyle("primary.TButton")).pack(side="left")
    ttk.Button(bar, text=t("btn.close"), command=win.destroy).pack(side="right")

    pw = ttk.PanedWindow(win, orient="horizontal")
    pw.pack(fill="both", expand=True, padx=10, pady=(10, 0))

    left = ttk.Frame(pw)
    pw.add(left, weight=2)
    cols = [("sid", t("series.col.sid"), 70),
            ("n", t("series.col.n_runs"), 56),
            ("period", t("series.col.period"), 150)]
    if self.has_feature("grading"):
        cols.append(("grades", t("series.col.grade_seq"), 110))
    cols.append(("objective", t("series.col.objective"), 220))
    tree = ttk.Treeview(left, columns=[c for c, _, _ in cols],
                        show="headings")
    configure_treeview_rows(tree, getattr(self, "dark", False))
    for c, lab, w in cols:
        tree.heading(c, text=lab)
        tree.column(c, width=w, anchor="w", stretch=(c == "objective"))
    tree.pack(fill="both", expand=True)

    right = ttk.Frame(pw, padding=(8, 0))
    pw.add(right, weight=3)
    sf = ScrollFrame(right)
    sf.pack(fill="both", expand=True)

    win._tree = tree
    win._right = sf.inner
    win._series_rows_cache = []

    tree.bind("<<TreeviewSelect>>",
              lambda e: self._render_series_detail(
                  win, (tree.selection() or [None])[0]))

    def on_destroy(e):
        if e.widget is win:
            self._series_win = None
    win.bind("<Destroy>", on_destroy)

    self._series_win = win
    self._refresh_series_manager()
    return win

def _refresh_series_manager(self):
    """左一覧を再構築し、選択中シリーズがあれば右ペインも再描画する。
    ウィンドウが閉じていれば何もしない(計画書の再描画フック)。"""
    win = getattr(self, "_series_win", None)
    if win is None or not win.winfo_exists():
        return
    tree = win._tree
    sel = tree.selection()
    cur_sid = sel[0] if sel else None
    tree.delete(*tree.get_children())
    rows = self._series_manager_rows()
    win._series_rows_cache = rows
    for index, row in enumerate(rows):
        values = [row["sid"], row["n"], row["period"]]
        if self.has_feature("grading"):
            values.append(row["grades"])
        values.append(row["objective"])
        tree.insert("", "end", iid=row["sid"], values=values,
                    tags=(stripe_tag(index),))
    if cur_sid is not None and any(r["sid"] == cur_sid for r in rows):
        tree.selection_set(cur_sid)
        self._render_series_detail(win, cur_sid)
    else:
        self._render_series_detail(win, None)

def _render_series_detail(self, win, sid):
    """右ペイン: 選択シリーズの概要・既知マップ・所属実験(計画書B-2)。"""
    parent = win._right
    for w in parent.winfo_children():
        w.destroy()
    if sid is None:
        ttk.Label(parent, foreground="#888",
                  text=t("series.msg.select_series")
                  ).pack(anchor="w", pady=10)
        return
    row = next((x for x in win._series_rows_cache if x["sid"] == sid),
               None)
    if row is None:
        return
    runs, srow = row["runs"], row["srow"]

    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(4, 0))
    ttk.Label(head, text=sid, font=("", 13, "bold")).pack(side="left")
    # 色規則②: 操作ボタンはニュートラル色(primaryは新規シリーズのみ)
    ttk.Button(head, text=t("btn.delete"),
               command=lambda: self._delete_series(win, sid)
               ).pack(side="right")
    ttk.Button(head, text=t("btn.edit"), command=lambda: self.edit_series(sid)
               ).pack(side="right", padx=(0, 6))

    ttk.Label(parent, foreground="#888",
              text=t("series.label.summary", n=row['n'], period=row['period'])
              ).pack(anchor="w", pady=(2, 0))

    if self.has_feature("grading"):
        gline = ttk.Frame(parent)
        gline.pack(anchor="w", pady=(2, 0))
        ttk.Label(gline, text=t("series.label.grade_seq"),
                  foreground="#888").pack(side="left")
        seq = self._series_grade_seq(runs)
        if not seq:
            ttk.Label(gline, text="—", foreground="#888").pack(side="left")
        for j, g in enumerate(seq):
            if j:
                ttk.Label(gline, text="→",
                          foreground="#888").pack(side="left", padx=2)
            ttk.Label(gline, text=g, font=("", 10, "bold"),
                      foreground=self.GCOL.get(g, "#888")).pack(side="left")

    if srow:
        for key, lab in (("objective", t("series.field.objective")), ("claim", t("series.field.claim")),
                         ("established_knowns", t("series.field.established_knowns")),
                         ("unresolved", t("series.field.unresolved")),
                         ("my_assessment", t("series.field.my_assessment"))):
            if srow.get(key, "").strip():
                ttk.Label(parent, text=lab, foreground="#888",
                          font=("", 9)).pack(anchor="w", pady=(8, 0))
                ttk.Label(parent, text=srow[key], wraplength=460,
                          justify="left").pack(anchor="w")
    else:
        ttk.Label(parent, foreground="#888",
                  text=t("series.msg.not_registered")
                  ).pack(anchor="w", pady=(6, 0))

    ttk.Label(parent, text=t("series.label.runs", n=row['n']), foreground="#888",
              font=("", 9)).pack(anchor="w", pady=(12, 2))
    if not runs:
        ttk.Label(parent, foreground="#888", text=t("series.msg.no_runs")
                  ).pack(anchor="w")
    for x in runs:
        line = ttk.Frame(parent, padding=(0, 2))
        line.pack(fill="x", anchor="w")
        rid = x.get("run_id", "")
        self._link(line, rid,
                   lambda rid=rid: self._open_run_in_main(rid)
                   ).pack(side="left")
        if self.has_feature("grading"):
            g = (x.get("grade", "") or "").strip().upper()
            ttk.Label(line, text=f" {g}" if g else "",
                      font=("", 10, "bold"),
                      foreground=self.GCOL.get(g, "#888")).pack(side="left")
        if "liquid" in self.fields or "liquid" in self.STEP_FIELDS:
            ttk.Label(line, text=f"  {self._liquid_disp(x)}",
                      foreground="#888").pack(side="left")

def _new_series(self, win):
    """新規シリーズ: IDを手入力させ、重複チェック後にedit_seriesへ委譲
    (空の編集フォーム=新規作成。edit_seriesを使い回す)。"""
    sid = (simpledialog.askstring(
        t("series.title.new_prompt"), t("series.msg.new_prompt"), parent=win) or ""
    ).strip()
    if not sid:
        return
    existing = {norm(x["sid"]) for x in self._series_manager_rows()}
    if norm(sid) in existing:
        messagebox.showerror(t("msg.duplicate"), t("series.msg.duplicate", sid=sid),
                             parent=win)
        return
    self.edit_series(sid)

def _delete_series(self, win, sid):
    """シリーズ削除。所属実験がある場合は件数を見せて確認、
    実験行は残しseries_idのみ空欄にする(計画書: データ破壊厳禁)。"""
    runs = [r for r in self.rows
            if (r.get("series_id", "") or "").strip() == sid]
    if runs:
        if not messagebox.askyesno(
                t("msg.confirm"),
                t("series.msg.confirm_delete_with_runs", sid=sid, n=len(runs)), parent=win):
            return
        for r in runs:
            r["series_id"] = ""
        if not self.save_evidence():
            return
    else:
        if not messagebox.askyesno(
                t("msg.confirm"), t("series.msg.confirm_delete", sid=sid), parent=win):
            return
    self.series_rows[:] = [s for s in self.series_rows
                           if (s.get("series_id", "") or "").strip()
                           != sid]
    if not self.save_series():
        return
    self.update_series_choices()
    self.search()
    self._refresh_series_manager()

def _open_run_in_main(self, rid):
    """所属実験のrun_idリンク: メイン一覧で該当行を選択して詳細表示。
    フィルタ中でも到達できるよう、先に絞り込みを解除する。"""
    self.clear()
    idx = next((i for i, x in enumerate(self.hits)
                if x.get("run_id", "") == rid), None)
    if idx is None:
        return
    iid = str(idx)
    self.tree.selection_set(iid)
    self.tree.see(iid)
    self.on_select()
    self.lift()
    self.focus_force()
