import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

from evidex.core.config import _UI_FONT_CANDIDATES

THEMED = False
try:
    import ttkbootstrap as tb
    THEMED = True
except ImportError:
    tb = ttk

MPL = False
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.ticker import MultipleLocator
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    MPL = True
    
    _fonts = set(f.name for f in fm.fontManager.ttflist)
    for cand in _UI_FONT_CANDIDATES:
        if cand in _fonts:
            plt.rcParams["font.family"] = cand
            break
except ImportError:
    Figure = FigureCanvasTkAgg = NavigationToolbar2Tk = MultipleLocator = None

def bstyle(s):
    return {"style": s} if THEMED else {}

def resolve_tk_font():
    # Will be called from App.__init__ after root is created
    available = set(tkfont.families())
    chosen = ""
    for cand in _UI_FONT_CANDIDATES:
        if cand in available:
            chosen = cand
            break
    if chosen:
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family=chosen)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family=chosen)
        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family=chosen)
