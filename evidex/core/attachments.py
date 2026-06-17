import re


PATH_SEPARATOR = ";"


def split_paths(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r"[;\r\n]+", str(value))
    paths = []
    seen = set()
    for item in items:
        path = str(item).strip()
        if not path or path in seen:
            continue
        paths.append(path)
        seen.add(path)
    return paths


def join_paths(paths):
    return f"{PATH_SEPARATOR} ".join(split_paths(paths))


def first_path(value):
    paths = split_paths(value)
    return paths[0] if paths else ""
