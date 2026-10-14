"""Wire gauge conversions.

AWG sizes follow ASTM B258: d(n) = 0.127 mm * 92 ** ((36 - n) / 39).
Gauges 0, 00, 000 and 0000 are written as 0, -1, -2 and -3.
Metric sizes are nominal conductor cross sections (IEC 60228).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

# Preferred metric sizes from IEC 60228, used to suggest a metric equivalent.
IEC_60228_SIZES_MM2 = (
    0.05, 0.08, 0.14, 0.25, 0.34, 0.5, 0.75, 1, 1.5, 2.5, 4, 6, 10, 16, 25, 35, 50,
    70, 95, 120, 150, 185, 240,
)


def awg_diameter_mm(awg: float) -> float:
    return 0.127 * 92 ** ((36 - awg) / 39)


def awg_to_mm2(awg: float) -> float:
    d = awg_diameter_mm(awg)
    return math.pi / 4 * d * d


def mm2_to_awg(mm2: float) -> float:
    """Exact (fractional) AWG for a cross section."""
    d = math.sqrt(4 * mm2 / math.pi)
    return 36 - 39 * math.log(d / 0.127, 92)


def nearest_awg(mm2: float) -> int:
    return int(round(mm2_to_awg(mm2)))


def nearest_metric(mm2: float) -> float:
    return min(IEC_60228_SIZES_MM2, key=lambda s: abs(math.log(s / mm2)))


def parse_awg(value) -> int:
    """Parse '4/0', '00', '0' or 28 into the numeric AWG scale."""
    s = str(value).strip().upper().replace("AWG", "").strip()
    if "/" in s:
        n, _ = s.split("/", 1)
        return 1 - int(n)
    if len(s) > 1 and set(s) == {"0"}:
        return 1 - len(s)
    return int(float(s))


def format_awg(awg: float) -> str:
    awg = int(round(awg))
    return f"{1 - awg}/0" if awg < 0 else str(awg)


def normalise(gauge, unit: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Return (awg, mm2) for a WireViz cable gauge/gauge_unit pair.

    Unknown units return (None, None).
    """
    if gauge is None or gauge == "":
        return None, None
    unit = (unit or "mm2").strip()
    if unit.upper() == "AWG":
        awg = parse_awg(gauge)
        return float(awg), awg_to_mm2(awg)
    if unit.lower().replace("²", "2") in ("mm2", "sqmm"):
        mm2 = float(gauge)
        return mm2_to_awg(mm2), mm2
    return None, None


def describe(awg: Optional[float], mm2: Optional[float], unit: Optional[str]) -> str:
    """Human friendly gauge with its equivalent, e.g. '28 AWG (0.08 mm²)'."""
    if awg is None:
        return ""
    if (unit or "").upper() == "AWG":
        return f"{format_awg(awg)} AWG ({mm2:.2g} mm²)"
    return f"{mm2:g} mm² (≈{format_awg(awg)} AWG)"


def awg_in_range(awg: float, accepted) -> bool:
    """`accepted` is a two item list of AWG numbers in either order."""
    lo, hi = sorted(parse_awg(a) for a in accepted)
    # Allow half a gauge of slack so that metric wire whose exact AWG is
    # e.g. 26.4 counts as 26 AWG.
    return lo - 0.5 <= awg <= hi + 0.5
