import json
import os
from pathlib import Path
from evidex.core import config
from evidex.core.fsio import atomic_write

DEFAULTS = {
    "active_pack": config.DEFAULT_PACK,
    "theme": "system",
    "language": "en",
}

def _settings_path():
    return config.RECORDS_CSV.parent / "evidex_settings.json"

def _load():
    try:
        path = _settings_path()
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def all():
    """全設定(DEFAULTS にファイル内容を上書きした dict)を返す。"""
    res = DEFAULTS.copy()
    res.update(_load())
    return res

def get(key, default=None):
    """設定値を返す。ファイル/キーが無ければ DEFAULTS→引数 default の順。例外は握って既定。"""
    try:
        data = all()
        if key in data:
            return data[key]
    except Exception:
        pass
    if key in DEFAULTS:
        return DEFAULTS[key]
    return default

def set(key, value):
    """1件更新して保存(他キーは保持)。成功可否を返す。"""
    try:
        data = _load()
        data[key] = value
        path = _settings_path()
        with atomic_write(path, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False
