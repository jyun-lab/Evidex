import csv
import io
from evidex.signal import Signal, Axis, Channel

DEFAULT_ENCODINGS = ["utf-8-sig", "cp932"]
COMMON_DELIMITERS = ",\t;"


def _read_text(path, encodings):
    last_error = None
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read(), encoding
        except (OSError, UnicodeError) as error:
            last_error = error
    raise ValueError(
        f"Failed to read {path} with encodings {encodings}: {last_error}"
    )


def inspect_csv(path, skip_rows=0, delimiter=None, encodings=None):
    """Read a CSV header and sample rows without depending on tkinter."""
    if skip_rows < 0:
        raise ValueError("skip_rows must be zero or greater")
    content, encoding = _read_text(path, encodings or DEFAULT_ENCODINGS)
    if delimiter is None:
        detection_lines = content.splitlines()[skip_rows:]
        detection_sample = "\n".join(detection_lines[:30])
        try:
            delimiter = csv.Sniffer().sniff(
                detection_sample[:8192], delimiters=COMMON_DELIMITERS
            ).delimiter
        except csv.Error:
            delimiter = ","
    if len(delimiter) != 1:
        raise ValueError("delimiter must be exactly one character")

    rows = list(csv.reader(io.StringIO(content), delimiter=delimiter))
    if len(rows) <= skip_rows:
        raise ValueError(
            f"File {path} has too few rows ({len(rows)}) "
            f"for skip_rows={skip_rows}"
        )
    header = [column.strip() for column in rows[skip_rows]]
    if not header or any(not column for column in header):
        raise ValueError("The CSV header contains an empty column name")
    if len(header) != len(set(header)):
        raise ValueError("The CSV header contains duplicate column names")
    return {
        "encoding": encoding,
        "delimiter": delimiter,
        "header": header,
        "rows": rows[skip_rows + 1:],
    }


def parse_with_config(path, config_dict) -> Signal:
    """adapter_config.json の設定に従って CSV を Signal に変換する汎用パーサ。"""
    fallbacks = config_dict.get("encoding_fallback", DEFAULT_ENCODINGS)
    delimiter = config_dict.get("delimiter", ",")
    skip_rows = config_dict.get("skip_rows", 0)
    x_col_name = config_dict.get("x_column", "")
    ch_col_names = config_dict.get("channel_columns", [])
    inspected = inspect_csv(
        path,
        skip_rows=skip_rows,
        delimiter=delimiter,
        encodings=fallbacks,
    )
    header = inspected["header"]
    data_rows = inspected["rows"]
    
    try:
        x_idx = header.index(x_col_name)
    except ValueError:
        raise ValueError(f"Column '{x_col_name}' not found in header: {header}")
        
    ch_indices = []
    for c in ch_col_names:
        try:
            ch_indices.append(header.index(c))
        except ValueError:
            raise ValueError(f"Column '{c}' not found in header: {header}")
            
    x_values = []
    ch_values = [[] for _ in ch_col_names]
    
    for row in data_rows:
        if len(row) <= x_idx or any(len(row) <= i for i in ch_indices):
            continue
        try:
            xv = float(row[x_idx].strip())
            cvs = [float(row[i].strip()) for i in ch_indices]
            x_values.append(xv)
            for i, cv in enumerate(cvs):
                ch_values[i].append(cv)
        except ValueError:
            pass

    if not x_values:
        raise ValueError("No numeric data rows matched the selected columns")
            
    x_axis = Axis(
        name=config_dict.get("x_name", x_col_name),
        unit=config_dict.get("x_unit", ""),
        values=x_values
    )
    
    ch_units = list(config_dict.get(
        "channel_units", [""] * len(ch_col_names)
    ))
    if len(ch_units) < len(ch_col_names):
        ch_units.extend([""] * (len(ch_col_names) - len(ch_units)))
        
    channels = []
    for cname, cunit, cvals in zip(ch_col_names, ch_units, ch_values):
        channels.append(Channel(name=cname, unit=cunit, values=cvals))
        
    return Signal(x=x_axis, channels=channels, meta={})
