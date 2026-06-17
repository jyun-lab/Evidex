from .i18n import t

HELP_TEXT = {
    "base_correction": t("help.base_correction"),
    "grade_A": t("help.grade_A"),
    "grade_B": t("help.grade_B"),
    "grade_C": t("help.grade_C"),
    "understanding": t("help.understanding"),
    "adv_filter": t("help.adv_filter"),
    "data_rows": t("help.data_rows"),
    "series_tab": t("help.series_tab"),
    "preset": t("help.preset"),
}

def icon_for_action(action):
    a = action.strip() if action else ""
    if a == "滴下": return "💧"
    if a == "静置": return "⏳"
    if a == "洗浄": return "🫧"
    if a == "乾燥": return "🌡"
    if a == "送気": return "💨"
    return "▫"

def icon_for_liquid(liquid):
    liq = liquid.strip() if liquid else ""
    if not liq: return ""
    if "空気" in liq: return "💨"
    if "水" in liq and "溶液" not in liq: return "💧"
    return "🧪"
