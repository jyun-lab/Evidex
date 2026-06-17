import tkinter as tk

class Tooltip:
    """汎用ツールチップ(Toplevel+overrideredirect、表示遅延600ms)。

    region=None なら widget 全体に <Enter>/<Leave> でバインド。
    region=callable(event)->bool を渡すと widget上の<Motion>でその領域に
    入っている間だけ表示する(例: Notebookの特定タブのみ)。

    罠対策: ウィジェットが消えた後にafterが発火しても落ちないよう、
    _show/_hideをtry/except TclErrorで包み、<Destroy>でafter_cancelする。
    """
    DELAY_MS = 600

    def __init__(self, widget, text, region=None):
        self.widget = widget
        self.text = text
        self.region = region
        self.tip = None
        self._after_id = None
        self._in_region = False
        if region is None:
            widget.bind("<Enter>", lambda e: self._schedule(), add="+")
        else:
            widget.bind("<Motion>", self._on_motion, add="+")
        widget.bind("<Leave>", lambda e: self._cancel(), add="+")
        widget.bind("<Destroy>", lambda e: self._cancel(), add="+")

    def _on_motion(self, event):
        try:
            inside = bool(self.region(event))
        except Exception:
            inside = False
        if inside and not self._in_region:
            self._in_region = True
            self._schedule()
        elif not inside and self._in_region:
            self._in_region = False
            self._cancel()

    def _schedule(self):
        self._cancel_timer()
        self._after_id = self.widget.after(self.DELAY_MS, self._show)

    def _cancel_timer(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _cancel(self):
        self._cancel_timer()
        self._hide()

    def _show(self):
        self._after_id = None
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + 16
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            try:
                self.tip.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            self.tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self.tip, text=self.text, justify="left",
                     background="#FFFFE0", foreground="#000000",
                     relief="solid", borderwidth=1, wraplength=320,
                     font=("", 9), padx=6, pady=3).pack()
        except tk.TclError:
            pass

    def _hide(self):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None
