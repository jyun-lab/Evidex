import json
import os
import sys
from pathlib import Path

DEFAULT_LOCALE = "en"
_cache = {}

def _load_locale(loc):
    if loc in _cache:
        return _cache[loc]
    
    cands = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        cands.append(os.path.join(mp, "evidex", "locales", f"{loc}.json"))
    cands.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales", f"{loc}.json"))
    
    path = next((c for c in cands if os.path.exists(c)), None)
    if not path:
        _cache[loc] = {}
        return {}
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            _cache[loc] = json.load(f)
    except Exception:
        _cache[loc] = {}
        
    return _cache[loc]

def current_locale():
    try:
        from evidex.core import settings
        loc = settings.get("language", DEFAULT_LOCALE)
    except Exception:
        loc = DEFAULT_LOCALE
    return loc if loc in ("ja", "en") else DEFAULT_LOCALE

def t(key, **fmt):
    """キーに対応する現ロケールの文字列。無ければ ja→キー自身の順でフォールバック。
    fmt があれば str.format で差し込む(壊れても例外を握ってキーを返す)。"""
    loc = current_locale()
    
    cat = _load_locale(loc)
    text = cat.get(key)
    if text is None and loc != "ja":
        cat_ja = _load_locale("ja")
        text = cat_ja.get(key)
        
    if text is None:
        text = key
        
    if fmt:
        try:
            return text.format(**fmt)
        except Exception:
            return text
            
    return text
