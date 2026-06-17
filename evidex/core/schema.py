import sys
import json
from pathlib import Path

def pack_resource_dir(pack_name):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "evidex" / "packs" / pack_name
    return Path(__file__).resolve().parent.parent / "packs" / pack_name

def load_schema(pack_name):
    p = pack_resource_dir(pack_name) / "schema.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
