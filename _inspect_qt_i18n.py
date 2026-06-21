import ast
import json
import re
import sys
from pathlib import Path


JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")


def docstring_nodes(tree: ast.AST) -> set[int]:
    result: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                result.add(id(body[0].value))
    return result


root = Path("evidex/qt_app")
ja = json.loads(Path("evidex/locales/ja.json").read_text(encoding="utf-8"))
value_to_keys: dict[str, list[str]] = {}
for key, value in ja.items():
    value_to_keys.setdefault(value, []).append(key)

unmatched: dict[str, list[tuple[str, int, str]]] = {}
matched = 0
joined: dict[tuple[str, int], tuple[str, str]] = {}
for path in sorted(root.glob("*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    docs = docstring_nodes(tree)
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and JP_RE.search(node.value)
            and id(node) not in docs
        ):
            parent = parents.get(id(node))
            if isinstance(parent, ast.JoinedStr):
                joined[(str(path), parent.lineno)] = (
                    ast.get_source_segment(source, parent) or ast.unparse(parent),
                    ast.unparse(parent),
                )
                if "--summary-joined" in sys.argv:
                    continue
            keys = value_to_keys.get(node.value, [])
            if keys:
                matched += 1
            else:
                unmatched.setdefault(node.value, []).append(
                    (str(path), node.lineno, type(parent).__name__ if parent else "")
                )
            if (
                "--summary" in sys.argv
                or "--summary-joined" in sys.argv
                or "--summary-simple" in sys.argv
            ):
                continue
            print(
                json.dumps(
                    {
                        "file": str(path),
                        "line": node.lineno,
                        "parent": type(parent).__name__ if parent else "",
                        "value": node.value,
                    },
                    ensure_ascii=False,
                )
            )

if "--summary" in sys.argv:
    print(f"matched instances: {matched}")
    print(f"unmatched unique: {len(unmatched)}")
    for value, locations in unmatched.items():
        print(json.dumps({"value": value, "locations": locations}, ensure_ascii=False))

if "--summary-joined" in sys.argv:
    print(f"joined unique: {len(joined)}")
    for (path, line), (source_text, unparsed) in joined.items():
        print(
            json.dumps(
                {
                    "file": path,
                    "line": line,
                    "source": source_text,
                    "unparsed": unparsed,
                },
                ensure_ascii=False,
            )
        )

if "--summary-simple" in sys.argv:
    simple_unmatched = {
        value: locations
        for value, locations in unmatched.items()
        if not all(parent == "JoinedStr" for _path, _line, parent in locations)
    }
    print(f"simple unmatched unique: {len(simple_unmatched)}")
    for value, locations in simple_unmatched.items():
        print(json.dumps({"value": value, "locations": locations}, ensure_ascii=False))
