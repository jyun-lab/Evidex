import tkinter as tk
from tkinter import ttk
from pathlib import Path
from evidex.core import config
from evidex.core.attachments import first_path
from evidex.packs import active_pack
from evidex.core.filtering import fnum
from evidex.core.icons import HELP_TEXT
from evidex.components import Tooltip
from evidex.gui_runtime import MPL, bstyle
from evidex.core.i18n import t

if MPL:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.ticker import MultipleLocator

def waveform_modes(config):
    modes = config.get("modes", [])
    if modes:
        return modes
    return [{"id": "all", "label": "Channels", "y_label": "Value",
             "channels": "all"}]

def waveform_mode(config, mode_id):
    modes = waveform_modes(config)
    return next(
        (mode for mode in modes if mode.get("id") == mode_id),
        next(
            (mode for mode in modes
             if mode.get("id") == config.get("default_mode")),
            modes[0],
        ),
    )

def waveform_channels(signal, mode):
    selected = mode.get("channels")
    if selected == "all":
        return [channel.name for channel in signal.channels]
    if isinstance(selected, list):
        return selected
    return signal.meta.get("groups", {}).get(mode.get("group", ""), [])

def _on_wave_click(self, event, info_label, spm=None, offset=None):
    """Copy the clicked waveform position and fill the next empty row field."""
    if spm is None or offset is None:
        return
    if event.xdata is None:
        return
    if getattr(event, "button", 1) != 1:   # Left click only.
        return
    tb_ = getattr(event.canvas, "toolbar", None)
    if tb_ is not None and getattr(tb_, "mode", ""):
        return                        # Ignore clicks while zoom/pan is active.
    row = max(int(offset), int(round(event.xdata * spm)) + int(offset))
    self._last_click_row = row        # Used by the step editor waveform shortcut.
    self.clipboard_clear()
    self.clipboard_append(str(row))
    filled = ""

    def all_tops(w):
        out = []
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel):
                out.append(c)
            out.extend(all_tops(c))
        return out

    for w_ in all_tops(self):
        if not hasattr(w_, "_widgets"):
            continue
        wd = w_._widgets
        if "data_start_row" not in wd:
            continue
        if not wd["data_start_row"].get().strip():
            tgt, lab = "data_start_row", t("wave.label.start_row")
        elif not wd["data_end_row"].get().strip():
            tgt, lab = "data_end_row", t("wave.label.end_row")
        else:
            break
        wd[tgt].insert(0, str(row))
        filled = t("wave.msg.auto_fill", lab=lab)
        break
    try:
        info_label.config(
            text=t("wave.msg.click_result", t=event.xdata, row=row, filled=filled))
    except tk.TclError:
        pass

def _draw_wave(self, holder, r, mode, set_mode, figsize=(6.6, 2.7),
               base=False, set_base=None, axis=None, set_axis=None,
               axis_open=False, set_axis_open=None):
    for w in holder.winfo_children():
        w.destroy()
    if not MPL:
        ttk.Label(holder, foreground="#888",
                  text=t("wave.msg.need_mpl")
                  ).pack(anchor="w")
        return
    rp = self._resolve_path(first_path(r.get("raw_path", "")))
    if rp is None:
        ttk.Label(holder, foreground="#888",
                  text=t("wave.msg.no_raw_path")
                  ).pack(anchor="w")
        return
    if not rp.exists():
        ttk.Label(holder, foreground="#888",
                  text=t("wave.msg.not_found", path=rp)).pack(anchor="w")
        return
    if not hasattr(self, "_wave_cache"):
        self._wave_cache = {}
    key = str(rp)
    if key not in self._wave_cache:
        try:
            self._wave_cache[key] = active_pack().parse(rp)
        except Exception as e:
            self._wave_cache[key] = e
    d = self._wave_cache[key]
    if isinstance(d, Exception):
        ttk.Label(holder, foreground="#888",
                  text=t("wave.msg.read_error", error=d)).pack(anchor="w")
        return
    wave_config = getattr(self, "WAVEFORM", {})
    modes = waveform_modes(wave_config)
    mode_config = waveform_mode(wave_config, mode)
    mode = mode_config.get("id", "all")
    top = ttk.Frame(holder)
    top.pack(fill="x")
    if len(modes) > 1:
        for item in modes:
            mo = item.get("id", "all")
            st = ("primary.TButton" if mode == mo
                  else "secondary.Outline.TButton")
            ttk.Button(top, text=item.get("label", mo), width=10,
                       command=lambda m_=mo: set_mode(m_),
                       **bstyle(st)).pack(side="left", padx=(0, 4))
    if set_base is not None:
        # Baseline correction is a state toggle, so use the same selected /
        # unselected button treatment as the waveform mode buttons.
        bst = "primary.TButton" if base else "secondary.Outline.TButton"
        base_btn = ttk.Button(top, text=t("wave.btn.base_correction"), width=8,
                              command=lambda: set_base(not base),
                              **bstyle(bst))
        base_btn.pack(side="left", padx=(0, 4))
        Tooltip(base_btn, HELP_TEXT["base_correction"])
    show_step_markers = bool(
        wave_config.get("step_markers", False)
        and self.has_feature("steps")
    )
    rsteps = self.steps.get(r.get("run_id", ""), []) if show_step_markers else []
    has_rows = any(fnum(s.get("data_start_row", "")) is not None
                   for s in rsteps)
    if show_step_markers:
        row2 = ttk.Frame(holder)
        row2.pack(fill="x")
        ttk.Label(row2, foreground="#888", font=("", 8),
                  text=(t("wave.msg.span_actual") if has_rows else
                        t("wave.msg.span_assume"))
                  ).pack(side="left")
    fig = Figure(figsize=figsize, dpi=100)
    ax = fig.add_subplot(111)
    keys = waveform_channels(d, mode_config)
    ylab = mode_config.get("y_label", "Value")
    off = {k: 0.0 for k in keys}
    t_base = None
    spm = d.meta.get("samples_per_min")
    offset = d.meta.get("row_offset", 2)
    t_vals = d.x.values
    
    def get_channel(name):
        return next((channel for channel in d.channels
                     if channel.name == name), None)

    def get_chan(name):
        channel = get_channel(name)
        return channel.values if channel is not None else []

    selected_units = {
        channel.unit for channel in (get_channel(name) for name in keys)
        if channel is not None and channel.unit
    }
    if (mode_config.get("channels") == "all"
            and ylab == "Value" and len(selected_units) == 1):
        ylab = f"Value [{next(iter(selected_units))}]"

    if base and spm is not None:
        br = fnum(r.get("base_row", ""))
        t_base = ((br - offset) / spm if br is not None
                  else t_vals[0])
        i0 = min(range(len(t_vals)),
                 key=lambda i: abs(t_vals[i] - t_base))
        off = {k: get_chan(k)[i0] if get_chan(k) else 0.0 for k in keys}
        base_lab = (t("wave.label.base_row", row=int(br)) if br is not None
                    else t("wave.label.base_head"))
        ax.set_title(base_lab, fontsize=8, loc="left", color="#888")
    for k in keys:
        channel = get_channel(k)
        vals = channel.values if channel is not None else []
        if not vals: continue
        channel_label = k
        if channel.unit:
            channel_label += f" [{channel.unit}]"
        ax.plot(t_vals, [v - off[k] for v in vals], ".", ms=2,
                label=(channel_label + ("-base" if base else "")))
    
    unit_str = f" [{d.x.unit}]" if d.x.unit else ""
    ax.set_ylabel(ylab)
    ax.set_xlabel(f"{d.x.name.capitalize()}{unit_str}")
    ax.grid(True, alpha=0.4)
    # Apply axis limits and tick spacing before drawing baseline or step markers.
    # Markers use ax.get_ylim()[1], so the final upper bound must be known first.
    a = axis or {}

    def _ax(k):
        return fnum(a.get(k, ""))
    if _ax("xmin") is not None or _ax("xmax") is not None:
        ax.set_xlim(left=_ax("xmin"), right=_ax("xmax"))
    if _ax("ymin") is not None or _ax("ymax") is not None:
        ax.set_ylim(bottom=_ax("ymin"), top=_ax("ymax"))
    _xs, _ys = _ax("xstep"), _ax("ystep")
    if _xs is not None and _xs > 0:
        ax.xaxis.set_major_locator(MultipleLocator(_xs))
    if _ys is not None and _ys > 0:
        ax.yaxis.set_major_locator(MultipleLocator(_ys))
    if t_base is not None:
        ax.axvline(t_base, color="#777", lw=0.9, ls=":")
    SPAN = ["#378ADD", "#1D9E75", "#BA7517", "#9B6DD6", "#C2543A"]
    if has_rows and spm is not None:
        # Convention: t[min] = (row - offset) / samples_per_min.
        for j, s in enumerate(rsteps):
            sr = fnum(s.get("data_start_row", ""))
            if sr is None:
                continue
            er = fnum(s.get("data_end_row", ""))
            t0 = (sr - offset) / spm
            lab = f"{s.get('step_no','')} {s.get('action','')}" \
                  f" {s.get('liquid','')}".strip()
            col = SPAN[j % len(SPAN)]
            if er is not None:
                t1 = (er - offset) / spm
                ax.axvspan(t0, t1, color=col, alpha=0.10)
            ax.axvline(t0, ls="--", lw=0.9, color=col, alpha=0.9)
            ax.text(t0, ax.get_ylim()[1], lab, fontsize=7,
                    rotation=90, va="top", ha="right", color=col)
    else:
        tcum = 0.0
        for s in rsteps:
            dur = fnum(s.get("duration_min", ""))
            lab = f"{s.get('step_no','')} {s.get('action','')}" \
                  f" {s.get('liquid','')}".strip()
            ax.axvline(tcum, ls="--", lw=0.9, color="#BA7517", alpha=0.8)
            ax.text(tcum, ax.get_ylim()[1], lab, fontsize=7,
                    rotation=90, va="top", ha="right", color="#854F0B")
            if dur is None:
                break
            tcum += dur
    leg = None
    if keys:
        leg = ax.legend(fontsize=8, loc="lower right",
                        bbox_to_anchor=(1.0, 1.0), ncol=2,
                        frameon=False, borderaxespad=0)
    if getattr(self, "dark", False):
        fig.patch.set_facecolor("#222629")
        ax.set_facecolor("#222629")
        for sp in ax.spines.values():
            sp.set_color("#777")
        ax.tick_params(colors="#CCCCCC")
        ax.xaxis.label.set_color("#CCCCCC")
        ax.yaxis.label.set_color("#CCCCCC")
        ax.grid(True, alpha=0.25, color="#888")
        if leg is not None:
            for txt in leg.get_texts():
                txt.set_color("#CCCCCC")
    fig.tight_layout()
    fig.subplots_adjust(top=0.86)   # Leave room for the external legend/title.
    canvas = FigureCanvasTkAgg(fig, master=holder)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="x", pady=(4, 0))
    toolbar = NavigationToolbar2Tk(canvas, holder, pack_toolbar=False)
    toolbar.update()
    toolbar.pack(fill="x")
    click_info = None
    if spm is not None:
        click_info = ttk.Label(holder, foreground="#888", font=("", 8),
                               text=t("wave.msg.click_hint"))
        click_info.pack(anchor="w")
        canvas.mpl_connect(
            "button_press_event",
            lambda ev: self._on_wave_click(ev, click_info, spm, offset),
        )

    # Axis settings are advanced controls, so keep them collapsed by default.
    # The toggle remains visible; expanded mode shows X and Y rows of entries.
    axhead = ttk.Frame(holder)
    axhead.pack(fill="x", pady=(2, 0))
    if set_axis is not None:
        holder._set_axis = set_axis      # Always expose for tests and hooks.
    if set_axis_open is not None:
        try:
            bg = ttk.Style(self).lookup("TFrame", "background")
        except tk.TclError:
            bg = None
        fg = "#CCCCCC" if getattr(self, "dark", False) else "#000000"
        kw = {"font": ("", 8), "relief": "flat", "bd": 0,
              "fg": fg, "activeforeground": fg}
        if bg:
            kw.update(bg=bg, activebackground=bg,
                      highlightbackground=bg)
        tk.Button(axhead, text=(t("wave.btn.axis_open") if axis_open else t("wave.btn.axis_closed")),
                  command=lambda: set_axis_open(not axis_open),
                  **kw).pack(side="left")
        holder._set_axis_open = set_axis_open
    if axis_open and set_axis is not None:
        a = axis or {}
        axbox = ttk.Frame(holder)
        axbox.pack(fill="x")
        ents = {}

        def _axis_line(parent, keys):
            ln = ttk.Frame(parent)
            ln.pack(fill="x")
            for k, lab in keys:
                ttk.Label(ln, text=lab, font=("", 8)).pack(side="left")
                e = ttk.Entry(ln, width=6)
                e.insert(0, str(a.get(k, "")))
                e.pack(side="left", padx=(0, 6))
                ents[k] = e

        _axis_line(axbox, [("xmin", t("wave.field.xmin")), ("xmax", t("wave.field.xmax")),
                           ("xstep", t("wave.field.xstep"))])
        _axis_line(axbox, [("ymin", t("wave.field.ymin")), ("ymax", t("wave.field.ymax")),
                           ("ystep", t("wave.field.ystep"))])
        btnrow = ttk.Frame(axbox)
        btnrow.pack(fill="x", pady=(2, 0))

        def _apply_axis():
            set_axis({k: e.get().strip() for k, e in ents.items()})

        ttk.Button(btnrow, text=t("btn.apply"), width=6,
                   command=_apply_axis).pack(side="left")
        ttk.Button(btnrow, text=t("btn.auto"), width=6,
                   command=lambda: set_axis({})).pack(side="left",
                                                      padx=(4, 0))
        ttk.Label(btnrow, text=t("wave.msg.axis_hint"),
                  font=("", 8), foreground="#888"
                  ).pack(side="left", padx=(8, 0))
        holder._axis_ents = ents
        holder._axis_apply = _apply_axis

    holder._canvas = canvas
    holder._on_click = (lambda ev:
        self._on_wave_click(ev, click_info, spm, offset)) if click_info else None
    holder._click_lbl = click_info   # Test hook.
