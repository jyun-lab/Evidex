from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class Axis:
    name: str             # "time" / "potential" / "wavelength"
    unit: str             # "min" / "V" / "nm"
    values: List[float]

@dataclass
class Channel:
    name: str             # "intensity" / "current"
    unit: str             # "" / "uA"
    values: List[float]

@dataclass
class Signal:
    x: Axis
    channels: List[Channel]
    meta: Dict[str, Any] = field(default_factory=dict)
