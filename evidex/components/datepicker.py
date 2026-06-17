import tkinter as tk
from tkinter import ttk
import datetime
import calendar
from evidex.core.i18n import t

class DatePicker(tk.Toplevel):
    """純tkinterの日付選択。選んだ日をISO形式でEntryに書き込む。"""

    def __init__(self, parent, entry):
        super().__init__(parent)
        self.title(t("date.title.select"))
        self.resizable(False, False)
        self.entry = entry
        try:
            cur = datetime.date.fromisoformat(entry.get().strip())
        except ValueError:
            cur = datetime.date.today()
        self.y, self.m = cur.year, cur.month
        nav = ttk.Frame(self, padding=(8, 8, 8, 0))
        nav.pack(fill="x")
        ttk.Button(nav, text="<", width=3,
                   command=lambda: self.shift(-1)).pack(side="left")
        ttk.Button(nav, text=">", width=3,
                   command=lambda: self.shift(1)).pack(side="right")
        self.head = ttk.Label(nav, anchor="center", font=("", 11, "bold"))
        self.head.pack(side="left", expand=True, fill="x")
        self.days = ttk.Frame(self, padding=8)
        self.days.pack()
        ttk.Button(self, text=t("date.btn.today"), command=self.today).pack(pady=(0, 8))
        self.draw()
        self.grab_set()

    def shift(self, d):
        m = self.m + d
        self.y += (m - 1) // 12
        self.m = (m - 1) % 12 + 1
        self.draw()

    def draw(self):
        for w in self.days.winfo_children():
            w.destroy()
        self.head.config(text=t("date.label.ym", y=self.y, m=self.m))
        for j, wd in enumerate(t("date.weekdays").split(",")):
            ttk.Label(self.days, text=wd, width=3,
                      anchor="center").grid(row=0, column=j)
        for i, week in enumerate(calendar.monthcalendar(self.y, self.m), 1):
            for j, day in enumerate(week):
                if day == 0:
                    continue
                ttk.Button(self.days, text=str(day), width=3,
                           command=lambda d=day: self.pick(d)
                           ).grid(row=i, column=j, padx=1, pady=1)

    def today(self):
        d = datetime.date.today()
        self.y, self.m = d.year, d.month
        self.pick(d.day)

    def pick(self, day):
        self.entry.delete(0, "end")
        self.entry.insert(0, datetime.date(self.y, self.m, day).isoformat())
        self.destroy()
