"""Turn a loaded harness into wires and nets using WireViz' own parser."""

from __future__ import annotations

import contextlib
import copy
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from wireviz import wireviz
from wireviz.DataClasses import MateComponent, MatePin
from wireviz.Harness import Harness
from wireviz.wv_colors import translate_color

from . import gauge as g
from .faces import Cavity, Face, draw
from .loader import HarnessError, LoadedHarness


@dataclass
class End:
    connector: str
    pin: Any
    label: str = ""
    display: str = ""  # connector name as shown to people

    @property
    def ref(self) -> str:
        """Stable identifier, e.g. ``FC:2``."""
        return f"{self.connector}:{self.pin}"

    @property
    def name(self) -> str:
        """Readable reference; auto-generated single pin parts show their template."""
        if self.display:
            return self.display
        return self.ref


@dataclass
class Wire:
    cable: str
    wire: Any  # 1-based wire number, or "s" for the shield
    label: str
    color: str  # WireViz short color code, e.g. "RD" or "WHBU"
    awg: Optional[float]
    mm2: Optional[float]
    gauge_text: str
    length: float
    length_unit: str
    left: List[End] = field(default_factory=list)
    right: List[End] = field(default_factory=list)
    twisted_with: Optional[Any] = None
    net: Optional["Net"] = None

    @property
    def ref(self) -> str:
        return f"{self.cable}:{self.wire}"

    @property
    def is_shield(self) -> bool:
        return self.wire == "s"

    @property
    def color_name(self) -> str:
        return translate_color(self.color, "full") if self.color and not self.color.startswith("#") else (self.color or "")


@dataclass
class Net:
    id: int
    ends: List[End] = field(default_factory=list)
    wires: List[Wire] = field(default_factory=list)
    jumpers: List[Tuple[End, End, str]] = field(default_factory=list)  # loops and mates

    @property
    def labels(self) -> List[str]:
        out: List[str] = []
        for e in self.ends:
            if e.label and e.label not in out:
                out.append(e.label)
        return out

    @property
    def name(self) -> str:
        return " / ".join(self.labels) or f"NET{self.id}"


@dataclass
class Model:
    loaded: LoadedHarness
    harness: Harness
    wires: List[Wire]
    nets: List[Net]
    wireviz_messages: List[str]

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self.harness.metadata)

    @property
    def manufacturing(self) -> Dict[str, Any]:
        return self.loaded.extras.manufacturing

    def wires_at(self, connector: str, pin) -> List[Wire]:
        return [w for w in self.wires if any(e.connector == connector and e.pin == pin for e in w.left + w.right)]

    def cavities(self, connector: str) -> List[Cavity]:
        """Pins of a connector with signal names and the colours of the wires in them."""
        c = self.harness.connectors[connector]
        out = []
        for i, pin in enumerate(c.pins):
            label = c.pinlabels[i] if i < len(c.pinlabels) and c.pinlabels[i] is not None else ""
            colors = [w.color or "" for w in self.wires_at(connector, pin)]
            out.append(Cavity(pin=pin, label=str(label), colors=colors))
        return out

    def face(self, connector: str) -> Optional[Face]:
        """Mating face drawing for a connector, or None when it has no face spec."""
        spec = self.loaded.connector_extras(connector).face
        uid = "".join(ch for ch in connector if ch.isalnum()) or "c"
        return draw(self.cavities(connector), spec, uid=uid)


def pin_label(harness: Harness, connector: str, pin) -> str:
    c = harness.connectors[connector]
    if pin in c.pins:
        i = c.pins.index(pin)
        if i < len(c.pinlabels) and c.pinlabels[i] not in (None, ""):
            return str(c.pinlabels[i])
    return ""


def make_end(harness: Harness, connector: str, pin) -> End:
    end = End(connector, pin, pin_label(harness, connector, pin))
    c = harness.connectors[connector]
    if connector.startswith("__"):  # auto-generated instance, e.g. __PAD_1
        template = connector[2:].rsplit("_", 1)[0]
        end.display = template if c.pincount == 1 else f"{template}:{pin}"
    return end


def resolve_pin(harness: Harness, connector: str, pin):
    c = harness.connectors[connector]
    if pin not in c.pins and pin in c.pinlabels:
        return c.pins[c.pinlabels.index(pin)]
    return pin


def parse_harness(loaded: LoadedHarness) -> Tuple[Harness, List[str]]:
    data = copy.deepcopy(loaded.data)
    image_paths = [loaded.path.parent] if loaded.path else []
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            harness = wireviz.parse(data, return_types="harness", image_paths=image_paths)
    except HarnessError:
        raise
    except Exception as e:  # WireViz raises bare Exceptions for input errors
        raise HarnessError(f"{type(e).__name__}: {e}") from e
    messages = [line.strip() for line in out.getvalue().splitlines() if line.strip()]
    return harness, messages


def build_model(loaded: LoadedHarness) -> Model:
    harness, messages = parse_harness(loaded)

    wires: List[Wire] = []
    index: Dict[Tuple[str, Any], Wire] = {}
    for cname, cable in harness.cables.items():
        awg, mm2 = g.normalise(cable.gauge, cable.gauge_unit)
        gauge_text = g.describe(awg, mm2, cable.gauge_unit)
        twisted = {}
        for a, b in loaded.cable_extras(cname).twisted:
            twisted[a], twisted[b] = b, a
        numbers: List[Any] = list(range(1, cable.wirecount + 1))
        if cable.shield:
            numbers.append("s")
        for n in numbers:
            if n == "s":
                color = cable.shield if isinstance(cable.shield, str) else ""
                label = "Shield"
                w_awg = w_mm2 = None
                w_gauge = ""
            else:
                color = cable.colors[n - 1] if n - 1 < len(cable.colors) else ""
                label = str(cable.wirelabels[n - 1]) if n - 1 < len(cable.wirelabels) else ""
                w_awg, w_mm2, w_gauge = awg, mm2, gauge_text
            wire = Wire(
                cable=cname, wire=n, label=label, color=color or "", awg=w_awg, mm2=w_mm2,
                gauge_text=w_gauge, length=cable.length, length_unit=cable.length_unit or "m",
                twisted_with=twisted.get(n),
            )
            wires.append(wire)
            index[(cname, n)] = wire
        for conn in cable.connections:
            wire = index[(cname, conn.via_port)]
            if conn.from_name is not None:
                end = make_end(harness, conn.from_name, conn.from_pin)
                if end.ref not in [e.ref for e in wire.left]:
                    wire.left.append(end)
            if conn.to_name is not None:
                end = make_end(harness, conn.to_name, conn.to_pin)
                if end.ref not in [e.ref for e in wire.right]:
                    wire.right.append(end)

    nets = _build_nets(harness, wires)
    return Model(loaded=loaded, harness=harness, wires=wires, nets=nets, wireviz_messages=messages)


def _build_nets(harness: Harness, wires: List[Wire]) -> List[Net]:
    parent: Dict[Any, Any] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    order: List[Any] = []

    def node(key):
        if key not in parent:
            order.append(key)
        find(key)
        return key

    jumpers: List[Tuple[End, End, str]] = []
    for w in wires:
        wn = node(("W", w.cable, w.wire))
        for e in w.left + w.right:
            union(wn, node(("P", e.connector, e.pin)))
    for cname, c in harness.connectors.items():
        for a, b in c.loops:
            jumpers.append((make_end(harness, cname, a), make_end(harness, cname, b), "loop"))
    for mate in harness.mates:
        if isinstance(mate, MatePin):
            fp = resolve_pin(harness, mate.from_name, mate.from_pin)
            tp = resolve_pin(harness, mate.to_name, mate.to_pin)
            jumpers.append((make_end(harness, mate.from_name, fp), make_end(harness, mate.to_name, tp), "mate"))
        elif isinstance(mate, MateComponent):
            a, b = harness.connectors[mate.from_name], harness.connectors[mate.to_name]
            for p in a.pins:
                if p in b.pins:
                    jumpers.append((make_end(harness, a.name, p), make_end(harness, b.name, p), "mate"))
    for a, b, _ in jumpers:
        union(node(("P", a.connector, a.pin)), node(("P", b.connector, b.pin)))

    groups: Dict[Any, Net] = {}
    nets: List[Net] = []
    for key in order:
        root = find(key)
        if root not in groups:
            groups[root] = Net(id=len(nets) + 1)
            nets.append(groups[root])
        net = groups[root]
        if key[0] == "P":
            net.ends.append(make_end(harness, key[1], key[2]))
    wire_by_key = {("W", w.cable, w.wire): w for w in wires}
    for key, w in wire_by_key.items():
        w.net = groups[find(key)]
        w.net.wires.append(w)
    for a, b, kind in jumpers:
        groups[find(("P", a.connector, a.pin))].jumpers.append((a, b, kind))
    return nets
