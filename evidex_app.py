#!/usr/bin/env python3
"""Evidex GUI application entry point."""

import sys


def _consume_data_arg(argv):
    for index, arg in enumerate(list(argv)):
        if arg == "--data":
            if index + 1 >= len(argv):
                raise SystemExit("--data requires a directory")
            value = argv[index + 1]
            del argv[index:index + 2]
            return value
        if arg.startswith("--data="):
            value = arg.split("=", 1)[1]
            del argv[index]
            return value
    return None


from evidex.core import config

config.set_base_dir(config.resolve_base_dir(_consume_data_arg(sys.argv)))

from evidex.main import App
from evidex.core.csvio import extract_bundled_assets, ensure_initial_csv_files

if __name__ == "__main__":
    try:
        extract_bundled_assets()
        ensure_initial_csv_files()
        App().mainloop()
    except Exception as e:
        import traceback
        import sys
        import os
        traceback.print_exc()
        # 安全網: アクティブパックでの起動に失敗したら汎用パックに戻す。
        # 設定ミスでアプリが二度と起動しない文鎮化を構造的に防ぐ。
        try:
            from evidex.core import config, settings
            settings.set("active_pack", config.DEFAULT_PACK)
        except Exception:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Startup Error",
                f"Failed to load the active pack.\n"
                f"Falling back to the generic time-series pack. "
                f"Please restart.\n\nDetails:\n{e}")
            root.destroy()
        except Exception:
            pass
