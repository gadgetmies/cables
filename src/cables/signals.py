"""Classify pin labels into electrical roles for the connectivity checks.

Labels are free text (``TX (OUT)``, ``VDD_3V3``, ``CAN_H`` ...), so the
classification works on tokens and is deliberately conservative: anything
it does not recognise is simply an unclassified signal.
"""

from __future__ import annotations

import re
from typing import List, Optional

POWER = "power"
GROUND = "ground"
SHIELD = "shield"
TX = "tx"
RX = "rx"
CTS = "cts"
RTS = "rts"
SCL = "scl"
SDA = "sda"
CAN_H = "can_h"
CAN_L = "can_l"
MOSI = "mosi"
MISO = "miso"
DIFF_P = "diff_p"
DIFF_N = "diff_n"

_GROUND = {"GND", "GROUND", "VSS", "0V", "AGND", "DGND", "PGND", "SGND", "GNDA", "GNDD", "BAT-", "VBAT-", "V-", "-", "NEG"}
_POWER_EXACT = {"VCC", "VDD", "VIN", "VBAT", "VBUS", "VSYS", "BAT+", "VBAT+", "V+", "+", "PWR", "POS", "VMOT"}
_POWER_RE = re.compile(r"^(\+?\d+(V\d*|\.\d+V))$|^(VCC|VDD|VBAT|VIN|VBUS)_?[\w.]*$")
_TOKEN_ROLES = {
    "TX": TX, "TXD": TX, "TXO": TX,
    "RX": RX, "RXD": RX, "RXI": RX,
    "CTS": CTS, "RTS": RTS,
    "SCL": SCL, "SDA": SDA,
    "MOSI": MOSI, "MISO": MISO,
    "CANH": CAN_H, "CAN_H": CAN_H, "CANL": CAN_L, "CAN_L": CAN_L,
    "SHIELD": SHIELD, "DRAIN": SHIELD, "SHLD": SHIELD,
}
# Differential pairs that should be twisted (role pairs).
TWIST_PAIRS = ((CAN_H, CAN_L), (DIFF_P, DIFF_N))


def _clean(label: str) -> str:
    label = re.sub(r"\(.*?\)", " ", str(label))  # drop "(OUT)", "(1.5K pullup)"
    return label.strip().upper()


def classify(label) -> Optional[str]:
    if label is None or str(label).strip() == "":
        return None
    raw = _clean(label)
    compact = raw.replace(" ", "")
    if compact in _GROUND or compact.startswith("GND"):
        return GROUND
    if compact in _POWER_EXACT or _POWER_RE.match(compact) or ("VOLTAGE" in raw and "TARGET" in raw):
        return POWER
    for key in ("CAN_H", "CANH", "CAN_L", "CANL"):
        if key in compact:
            return _TOKEN_ROLES[key]
    if re.search(r"(^|_)D\+$|USB_?DP$|DATA\+$", compact):
        return DIFF_P
    if re.search(r"(^|_)D-$|USB_?DM$|USB_?DN$|DATA-$", compact):
        return DIFF_N
    tokens: List[str] = [t for t in re.split(r"[^A-Z0-9]+", raw) if t]
    for tok in tokens:
        # Last-chance: "UART1_TX" style tokens are split by "_" above.
        role = _TOKEN_ROLES.get(tok)
        if role:
            return role
    return None


def voltage(label) -> Optional[float]:
    """Nominal voltage written in a supply label: '+5V' -> 5, 'VDD_3V3' -> 3.3."""
    m = re.search(r"(\d+)V(\d+)|(\d+(?:\.\d+)?)V(?![A-Z])", _clean(label).replace(" ", ""))
    if not m:
        return None
    if m.group(1):
        return float(f"{m.group(1)}.{m.group(2)}")
    return float(m.group(3))
