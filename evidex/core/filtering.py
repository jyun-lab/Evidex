import unicodedata
from evidex.core.fields import CHOICES

def norm(s):
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).lower().replace(" ", "").replace("　", "")

def fnum(s):
    if not s:
        return None
    try:
        return float(str(s).strip())
    except ValueError:
        return None

def row_matches(r, f, steps=None):
    if f["text"] and f["text"].lower() not in " ".join(str(v) for v in r.values()).lower():
        return False
    if f["grades"] and (r.get("grade", "") or "").strip().upper() not in f["grades"]:
        return False
    if f["status"] and r.get("status", "").strip() != f["status"]:
        return False
    if f["liquid"] and r.get("liquid", "").strip() != f["liquid"]:
        return False
    if f["vmin"] is not None:
        v = fnum(r.get("viscosity_mPas", ""))
        if v is None or v < f["vmin"]:
            return False
    if f["vmax"] is not None:
        v = fnum(r.get("viscosity_mPas", ""))
        if v is None or v > f["vmax"]:
            return False
    if f["chip"] and f["chip"].lower() not in r.get("chip_id", "").lower():
        return False
    if f["who"] and f["who"].lower() not in r.get("experimenter", "").lower():
        return False
    if f["unread"]:
        u_choices = [c for c in CHOICES.get("understanding", []) if c]
        unread_val = u_choices[0] if u_choices else "未読"
        if r.get("understanding", "").strip() != unread_val:
            return False
    
    # adv
    if f["dfrom"]:
        if not r.get("date") or r.get("date") < f["dfrom"]:
            return False
    if f["dto"]:
        if not r.get("date") or r.get("date") > f["dto"]:
            return False
    if f["series"] and norm(r.get("series_id", "")) != norm(f["series"]):
        return False
    if f["understanding"] and norm(r.get("understanding", "")) != norm(f["understanding"]):
        return False
    if f["action"] and steps is not None:
        st = steps.get(r.get("run_id", ""), [])
        if not any(norm(s.get("action", "")) == norm(f["action"]) for s in st):
            return False
    if f["has_raw"] and not r.get("raw_path", "").strip():
        return False
    if f["no_steps"] and steps is not None:
        st = steps.get(r.get("run_id", ""), [])
        if len(st) > 0:
            return False
            
    return True
