from evidex.packs import active_pack

_s = active_pack().schema()

RUN_FIELDS = _s["RUN_FIELDS"]
STEP_FIELDS = _s["STEP_FIELDS"]
SERIES_FIELDS = _s["SERIES_FIELDS"]

COLS = [tuple(x) for x in _s["COLS"]]
HEAD = _s["HEAD"]

LONG_FIELDS = set(_s["LONG_FIELDS"])
HIDDEN_EDIT_FIELDS = set(_s["HIDDEN_EDIT_FIELDS"])

JP_LABEL = _s.get("JP_LABEL", {})
LABEL_EN = _s.get("LABEL_EN", {})
FACETS = _s.get("facets", [])
ADV_FILTERS = _s.get("adv_filters", [])
CHOICES = _s["CHOICES"]
GCOL = _s["GCOL"]

STEP_FORM = [tuple(x) for x in _s["STEP_FORM"]]
ACTION_CHOICES = _s["ACTION_CHOICES"]
MEDIA_SEEDS = _s["MEDIA_SEEDS"]
FEATURES = _s.get("features", {})
WAVEFORM = _s.get("waveform", {})

def feature_enabled(name, default=False):
    return bool(FEATURES.get(name, default))

def get_label(field_key):
    from evidex.core.i18n import current_locale
    if current_locale() == "en":
        return LABEL_EN.get(field_key, JP_LABEL.get(field_key, field_key))
    return JP_LABEL.get(field_key, field_key)
