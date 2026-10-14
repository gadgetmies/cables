"""Design rule checks.

Every finding has a stable code so it can be looked up in docs/checks.md
and silenced per harness with ``manufacturing: {ignore: [CODE, ...]}``.

Severity:
  error    the cable would be wrong or cannot be built as drawn
  warning  probably wrong, or information a manufacturer will ask for
  info     worth knowing, nothing to fix
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, List

from . import gauge as g
from . import signals as s
from .model import Model

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    where: str = ""

    def __str__(self) -> str:
        where = f" [{self.where}]" if self.where else ""
        return f"{self.severity.upper():7} {self.code}{where}: {self.message}"


CHECKS: List[Callable[[Model], List[Finding]]] = []


def check(fn):
    CHECKS.append(fn)
    return fn


@check
def wireviz_messages(m: Model) -> List[Finding]:
    out = []
    for msg in m.wireviz_messages:
        if "not referenced in any connection set" in msg:
            continue  # the next line lists the components; reported by unused_components
        if msg.startswith("Warning") or "Unknown color" in msg or "Invalid hex" in msg:
            out.append(Finding(WARNING, "C001", f"WireViz: {msg}"))
    return out


@check
def unused_components(m: Model) -> List[Finding]:
    used = set(m.loaded.instance_templates.values())
    out = []
    for section in ("connectors", "cables"):
        for name in m.loaded.data.get(section, {}):
            if name not in used:
                out.append(Finding(WARNING, "C002", f"{section[:-1]} is defined but never connected", name))
    return out


@check
def unterminated_wires(m: Model) -> List[Finding]:
    out = []
    for w in m.wires:
        if w.is_shield and not (w.left or w.right):
            out.append(Finding(INFO, "C010", "shield is not terminated at either end", w.ref))
            continue
        if w.is_shield:
            continue
        missing = [side for side, ends in (("left", w.left), ("right", w.right)) if not ends]
        if len(missing) == 2:
            out.append(Finding(WARNING, "C011", "wire is not connected at either end (spare?)", w.ref))
        elif missing:
            out.append(Finding(INFO, "C012", f"wire has a free {missing[0]} end (flying lead)", w.ref))
    return out


@check
def multiple_wires_per_pin(m: Model) -> List[Finding]:
    count = Counter(e.ref for w in m.wires for e in w.left + w.right)
    return [
        Finding(INFO, "C013", f"{n} wires terminate in this contact; check the contact accepts the combined cross section", ref)
        for ref, n in count.items() if n > 1
    ]


@check
def gauge_vs_contact(m: Model) -> List[Finding]:
    bad = {}  # (connector, cable) -> wire numbers that do not fit
    for w in m.wires:
        if w.awg is None:
            continue
        for e in w.left + w.right:
            accepted = m.loaded.connector_extras(e.connector).wire_awg
            if accepted and not g.awg_in_range(w.awg, accepted):
                bad.setdefault((e.connector, w.cable), []).append(w)
    out = []
    for (connector, cable), wires in bad.items():
        lo, hi = sorted(g.parse_awg(a) for a in m.loaded.connector_extras(connector).wire_awg)
        numbers = ", ".join(str(w.wire) for w in wires)
        out.append(Finding(
            ERROR, "G001",
            f"{cable} wire {numbers} is {wires[0].gauge_text}; the contacts accept {g.format_awg(hi)}\u2013{g.format_awg(lo)} AWG",
            connector,
        ))
    return out


@check
def gauge_missing(m: Model) -> List[Finding]:
    out = []
    for name, c in m.harness.cables.items():
        if c.gauge is None:
            out.append(Finding(WARNING, "G002", "no wire gauge given", name))
        elif g.normalise(c.gauge, c.gauge_unit) == (None, None):
            out.append(Finding(WARNING, "G003", f"unknown gauge unit '{c.gauge_unit}', use AWG or mm2", name))
    return out


def _roles(net):
    return [(e, s.classify(e.label)) for e in net.ends]


@check
def supply_shorts(m: Model) -> List[Finding]:
    out = []
    for net in m.nets:
        roles = _roles(net)
        power = [e for e, r in roles if r == s.POWER]
        ground = [e for e, r in roles if r == s.GROUND]
        if power and ground:
            out.append(Finding(ERROR, "S001", f"supply shorted to ground: {power[0].name} ({power[0].label}) ↔ {ground[0].name} ({ground[0].label})", net.name))
        volts = {s.voltage(e.label) for e in power} - {None}
        if len(volts) > 1:
            listed = ", ".join(f"{e.name} ({e.label})" for e in power)
            out.append(Finding(ERROR, "S002", f"different supply voltages joined: {listed}", net.name))
        if power and not ground:
            others = [(e, r) for e, r in roles if r not in (s.POWER, None, s.SHIELD)]
            if others:
                e, _ = others[0]
                out.append(Finding(ERROR, "S003", f"supply {power[0].name} ({power[0].label}) joined to signal {e.name} ({e.label})", net.name))
        if ground and not power:
            others = [(e, r) for e, r in roles if r not in (s.GROUND, None, s.SHIELD)]
            if others:
                e, _ = others[0]
                out.append(Finding(ERROR, "S004", f"ground {ground[0].name} joined to signal {e.name} ({e.label})", net.name))
    return out


_SAME_ROLE_IS_WRONG = {
    s.TX: "TX connected to TX; TX must go to RX",
    s.RX: "RX connected to RX; RX must go to TX",
    s.CTS: "CTS connected to CTS; CTS must go to RTS",
    s.RTS: "RTS connected to RTS; RTS must go to CTS",
}
_MUST_NOT_MEET = [
    ({s.SCL, s.SDA}, ERROR, "I²C SCL and SDA swapped"),
    ({s.CAN_H, s.CAN_L}, ERROR, "CAN_H and CAN_L swapped"),
    ({s.MOSI, s.MISO}, WARNING, "MOSI joined to MISO (SPI normally connects MOSI to MOSI)"),
    ({s.DIFF_P, s.DIFF_N}, ERROR, "differential pair polarity swapped (D+ to D-)"),
    ({s.TX, s.CTS}, WARNING, "TX joined to CTS"),
    ({s.TX, s.RTS}, WARNING, "TX joined to RTS"),
    ({s.RX, s.CTS}, WARNING, "RX joined to CTS"),
    ({s.RX, s.RTS}, WARNING, "RX joined to RTS"),
]


@check
def signal_pairing(m: Model) -> List[Finding]:
    out = []
    for net in m.nets:
        roles = _roles(net)
        counts = Counter(r for _, r in roles if r)
        connectors = {e.connector for e in net.ends}
        if len(connectors) < 2:
            continue  # only one connector: nothing to pair (e.g. a flying lead)
        for role, msg in _SAME_ROLE_IS_WRONG.items():
            opposite = {s.TX: s.RX, s.RX: s.TX, s.CTS: s.RTS, s.RTS: s.CTS}[role]
            if counts[role] >= 2 and counts[opposite] == 0:
                refs = ", ".join(f"{e.name} ({e.label})" for e, r in roles if r == role)
                out.append(Finding(ERROR, "S010", f"{msg}: {refs}", net.name))
        present = set(counts)
        for pair, severity, msg in _MUST_NOT_MEET:
            if pair <= present:
                refs = ", ".join(f"{e.name} ({e.label})" for e, r in roles if r in pair)
                out.append(Finding(severity, "S011", f"{msg}: {refs}", net.name))
    return out


@check
def twisted_pairs(m: Model) -> List[Finding]:
    out = []
    for name, cable in m.harness.cables.items():
        for pair in m.loaded.cable_extras(name).twisted:
            for n in pair:
                if not isinstance(n, int) or not 1 <= n <= cable.wirecount:
                    out.append(Finding(ERROR, "T001", f"twisted pair {pair} refers to wire {n}, cable has {cable.wirecount} wires", name))
    def carries(w, role):
        return any(s.classify(e.label) == role for e in w.left + w.right)

    for pos, neg in s.TWIST_PAIRS:
        for w in m.wires:
            if not carries(w, pos) or carries(w, neg):
                continue  # a wire carrying both is already reported as swapped
            partners = [x.wire for x in m.wires if x.cable == w.cable and carries(x, neg) and not carries(x, pos)]
            if partners and w.twisted_with not in partners:
                out.append(Finding(
                    WARNING, "T002",
                    f"wire {w.wire} ({pos.upper()}) is not twisted with wire {partners[0]} ({neg.upper()}); "
                    f"add twisted: [[{w.wire}, {partners[0]}]]",
                    w.cable,
                ))
    return out


@check
def manufacturing_ready(m: Model) -> List[Finding]:
    """Information a manufacturer needs to quote and build the cable."""
    out = []
    meta = m.metadata
    for key, why in (("pn", "part number"), ("revision", "revision")):
        if not meta.get(key):
            out.append(Finding(WARNING, "M001", f"metadata.{key} missing ({why} for ordering and traceability)"))
    mfg = m.manufacturing
    if not mfg.get("ipc_class"):
        out.append(Finding(WARNING, "M002", "manufacturing.ipc_class missing (IPC/WHMA-A-620 class 1, 2 or 3)"))
    elif str(mfg.get("ipc_class")) not in ("1", "2", "3"):
        out.append(Finding(ERROR, "M002", f"manufacturing.ipc_class must be 1, 2 or 3, not {mfg.get('ipc_class')!r}"))
    if not mfg.get("length_tolerance"):
        out.append(Finding(WARNING, "M003", "manufacturing.length_tolerance missing; the manufacturer will apply its default"))
    for name, c in m.harness.connectors.items():
        if c.ignore_in_bom:
            continue
        if not c.mpn:
            out.append(Finding(WARNING, "M004", "no manufacturer part number (mpn)", name))
    for name, c in m.harness.cables.items():
        if c.ignore_in_bom:
            continue
        if not c.length:
            out.append(Finding(WARNING, "M005", "no length", name))
        if not any(c.colors):
            out.append(Finding(WARNING, "M006", "no wire colors (manufacturer cannot match the wire list)", name))
        if not c.mpn and not c.type:
            out.append(Finding(WARNING, "M007", "no wire type or part number (e.g. type: UL1007, mpn: ...)", name))
    return out


def run_checks(model: Model, strict: bool = False) -> List[Finding]:
    findings: List[Finding] = []
    for fn in CHECKS:
        findings.extend(fn(model))
    ignore = {str(c) for c in model.manufacturing.get("ignore", []) or []}
    findings = [f for f in findings if f.code not in ignore]
    if strict:
        findings = [Finding(ERROR, f.code, f.message, f.where) if f.severity == WARNING else f for f in findings]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.code, f.where))
    return findings
