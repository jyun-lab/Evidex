import csv
from pathlib import Path
from evidex.signal import Signal, Axis, Channel


def parse(path) -> Signal:
    p = Path(path)
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    r = csv.reader(lines)
    header = [x.strip() for x in next(r)]
    if not header or header[0] != "time":
        raise ValueError("time column required")

    t = []
    chans = {k: [] for k in header[1:]}
    for row in r:
        if not row or len(row) != len(header):
            continue
        try:
            t_val = float(row[0])
            c_vals = [float(row[i]) for i in range(1, len(header))]
            t.append(t_val)
            for i, k in enumerate(header[1:]):
                chans[k].append(c_vals[i])
        except ValueError:
            pass

    return Signal(
        x=Axis("time", "s", t),
        channels=[Channel(k, "V", v) for k, v in chans.items()],
        meta={"source": "synthetic oscilloscope demo"},
    )
