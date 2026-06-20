try:
    import matplotlib
    from matplotlib import font_manager
    MPL_AVAILABLE = True
except Exception:
    matplotlib = None
    font_manager = None
    MPL_AVAILABLE = False


_LIGHT = {
    "bg": "#FFFFFF",
    "bg_alt": "#FAFAFA",
    "bg_surface": "#F6F8FA",
    "text": "#344054",
    "text_muted": "#667085",
    "border": "#D0D7DE",
    "border_light": "#E5E7EB",
    "header_bg": "#EEF2F6",
    "nav_bg": "#FAFAFA",
    "nav_border": "#E5E7EB",
    "selection": "#2563EB",
    "selection_text": "#FFFFFF",
    "selection_border": "#1D4ED8",
    "selection_inactive": "#3B82F6",
    "hover": "#F3F4F6",
    "link": "#2563EB",
    "grade_row": {"A": "#E6F3EA", "B": "#FCF0DC", "C": "#ECEFF1"},
}

_DARK = {
    "bg": "#1E1E1E",
    "bg_alt": "#252526",
    "bg_surface": "#2D2D2D",
    "text": "#D4D4D4",
    "text_muted": "#9D9D9D",
    "border": "#404040",
    "border_light": "#333333",
    "header_bg": "#2D2D2D",
    "nav_bg": "#252526",
    "nav_border": "#333333",
    "selection": "#264F78",
    "selection_text": "#FFFFFF",
    "selection_border": "#1B3A57",
    "selection_inactive": "#2A4A6B",
    "hover": "#2A2D2E",
    "link": "#569CD6",
    "grade_row": {"A": "#1F3B2A", "B": "#4A3A1A", "C": "#2E3439"},
}


def configure_matplotlib_fonts():
    if not MPL_AVAILABLE:
        return
    matplotlib.rcParams["axes.unicode_minus"] = False
    candidates = [
        "Yu Gothic",
        "Yu Gothic UI",
        "Meiryo",
        "MS Gothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return


configure_matplotlib_fonts()
