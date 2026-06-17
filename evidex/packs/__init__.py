import sys
import json
import importlib
from pathlib import Path

registry = {
    "generic_ts": "evidex.packs.generic_ts"
}

class PackInterface:
    def __init__(self, name, module=None, user_path=None):
        self.__name__ = name
        self.name = name
        self._module = module
        self._user_path = user_path
        
    def schema(self):
        if self._user_path:
            with open(Path(self._user_path) / "schema.json", "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            from evidex.core.schema import load_schema
            return load_schema(self.name)

    def parse(self, path):
        if self._module and hasattr(self._module, 'adapter') and hasattr(self._module.adapter, 'parse'):
            return self._module.adapter.parse(path)
        elif self._module and hasattr(self._module, 'parse'):
            return self._module.parse(path)
        elif self._user_path:
            user_dir = Path(self._user_path)
            adp_py = user_dir / "adapter.py"
            if adp_py.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("user_adapter", adp_py)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.parse(path)
            
            cfg_path = user_dir / "adapter_config.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                from evidex.core.nocode_adapter import parse_with_config
                return parse_with_config(path, cfg)
        raise NotImplementedError("No parser available for this pack")

def _discover_user_packs():
    from evidex.core import config
    user_dir = config.RECORDS_CSV.parent / "packs"
    found = {}
    if user_dir.is_dir():
        for d in user_dir.iterdir():
            if d.is_dir() and (d / "schema.json").exists():
                found[d.name] = str(d)
    return found

def get_pack_names():
    base = list(registry.keys())
    user_packs = _discover_user_packs()
    for k in user_packs.keys():
        if k not in base:
            base.append(k)
    return base

def active_pack():
    try:
        from evidex.core import config, settings
        name = settings.get("active_pack", config.DEFAULT_PACK)
        user_packs = _discover_user_packs()
        
        if name in user_packs:
            return PackInterface(name, user_path=user_packs[name])
            
        if name not in registry:
            name = config.DEFAULT_PACK
        mod = importlib.import_module(registry[name])
        return PackInterface(name, module=mod)
    except Exception:
        from evidex.core import config
        name = config.DEFAULT_PACK
        mod = importlib.import_module(registry[name])
        return PackInterface(name, module=mod)
