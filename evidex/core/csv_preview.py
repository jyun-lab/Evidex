from dataclasses import dataclass
from pathlib import Path

from evidex.core.nocode_adapter import inspect_csv


@dataclass(frozen=True)
class CsvPreview:
    path: Path
    encoding: str
    delimiter: str
    header: list[str]
    rows: list[list[str]]
    total_rows: int


def load_csv_preview(path, max_rows=50):
    if max_rows < 1:
        raise ValueError("max_rows must be one or greater")
    source = Path(path)
    inspected = inspect_csv(source)
    rows = inspected["rows"]
    return CsvPreview(
        path=source,
        encoding=inspected["encoding"],
        delimiter=inspected["delimiter"],
        header=inspected["header"],
        rows=rows[:max_rows],
        total_rows=len(rows),
    )
