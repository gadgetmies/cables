"""Schematic drawings of connector mating faces.

A connector gets a drawing when it has a ``face`` spec (library entries set
one). The drawing shows the housing outline, polarisation features, every
cavity with its pin number and signal name, and the colour of the wire
crimped into it. Drawings are schematic: proportions are not to scale.

face:
  style: row | dsub | xt      # single-row crimp housing, D-sub, Amass XT
  gender: female | male       # sockets (rings) or pins (filled)
  latch: true                 # row: draw a latch on top
  pin1: left | right          # row: pin 1 position in the drawn view
  view: mating face           # caption text
  rows: [5, 4]                # dsub: contacts per row, top row first
"""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from wireviz.wv_colors import get_color_hex

FONT = "Arial, Helvetica, sans-serif"
INK = "#1b1f24"
BODY = "#f1f3f5"
DSUB_ROWS = {9: [5, 4], 15: [8, 7], 25: [13, 12], 37: [19, 18], 50: [17, 16, 17]}


@dataclass
class Cavity:
    pin: Any
    label: str = ""
    colors: List[str] = field(default_factory=list)  # one entry per wire, WireViz color codes

    @property
    def populated(self) -> bool:
        return bool(self.colors)


@dataclass
class Face:
    svg: str
    width: int
    height: int

    def data_uri(self) -> str:
        return "data:image/svg+xml;base64," + base64.b64encode(self.svg.encode("utf-8")).decode("ascii")


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _text(x, y, s, size=11, anchor="middle", weight="normal", rotate=None, fill=INK) -> str:
    tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}"{tr}>{_e(s)}</text>')


def _fill_defs(uid: str, colors: Sequence[str]) -> (str, str):
    """Return (defs, fill) painting a wire colour; stripes become a gradient."""
    if not colors:
        return "", "none"
    hexes = get_color_hex(colors[0]) if colors[0] else ["#ffffff"]
    if len(hexes) == 1:
        return "", hexes[0]
    stops = []
    n = len(hexes)
    for i, h in enumerate(hexes):
        stops.append(f'<stop offset="{i / n:.3f}" stop-color="{h}"/><stop offset="{(i + 1) / n:.3f}" stop-color="{h}"/>')
    return f'<linearGradient id="{uid}" x1="0" y1="0" x2="1" y2="1">{"".join(stops)}</linearGradient>', f"url(#{uid})"


def _cavity(uid, cx, cy, r, cav: Cavity, gender: str, shape: str) -> (str, str):
    """Draw one contact. Returns (defs, body)."""
    defs, fill = _fill_defs(uid, cav.colors)
    if shape == "square":
        outer = f'<rect x="{cx - r:.1f}" y="{cy - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" rx="2" fill="#fff" stroke="{INK}" stroke-width="1.2"/>'
        inner_r = r * 0.62
        inner = f'<rect x="{cx - inner_r:.1f}" y="{cy - inner_r:.1f}" width="{2 * inner_r:.1f}" height="{2 * inner_r:.1f}" rx="1.5" fill="{fill}" stroke="{INK}" stroke-width="0.8"/>'
    else:
        outer = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#fff" stroke="{INK}" stroke-width="1.2"/>'
        inner_r = r * (0.7 if gender == "male" else 0.55)
        inner = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{inner_r:.1f}" fill="{fill}" stroke="{INK}" stroke-width="0.8"/>'
    if not cav.populated:
        # Unused cavity: empty, with a cross so it reads as "leave empty".
        d = r * 0.45
        inner = (f'<path d="M{cx - d:.1f},{cy - d:.1f} L{cx + d:.1f},{cy + d:.1f} M{cx + d:.1f},{cy - d:.1f} '
                 f'L{cx - d:.1f},{cy + d:.1f}" stroke="#9aa3ad" stroke-width="1"/>')
    elif gender == "male" and shape != "square":
        outer = outer.replace('fill="#fff"', 'fill="#d5dade"')
    return defs, outer + inner


def _wrap(width, height, defs, body, caption) -> Face:
    height_total = height + 18
    # Narrow housings: widen the canvas so the caption fits, keep the drawing centred.
    full = max(width, int(len(caption) * 5.6 + 16))
    shift = (full - width) / 2
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{full}" height="{height_total}" '
           f'viewBox="0 0 {full} {height_total}">'
           f'<defs>{"".join(defs)}</defs>'
           f'<rect width="100%" height="100%" fill="#fff"/><g transform="translate({shift:.1f} 0)">{body}</g>'
           f'{_text(full / 2, height_total - 5, caption, size=10, fill="#5d6670")}</svg>')
    return Face(svg=svg, width=full, height=height_total)


def _label_len(cavities) -> int:
    return max([len(str(c.label)) for c in cavities] + [0])


def draw_row(cavities: List[Cavity], spec: Dict[str, Any], uid: str) -> Face:
    n = len(cavities)
    step, r = 30, 9
    gender = spec.get("gender", "female")
    order = cavities if spec.get("pin1", "left") == "left" else list(reversed(cavities))
    label_h = min(_label_len(cavities), 18) * 6.2 + 6
    margin_x, top = 18, 26
    body_w = (n - 1) * step + 2 * r + 2 * 12
    width = int(body_w + 2 * margin_x)
    body_h = 2 * r + 2 * 10
    y = top + body_h / 2
    height = int(top + body_h + 18 + label_h + 6)
    defs, parts = [], []
    x0 = margin_x
    parts.append(f'<rect x="{x0}" y="{top}" width="{body_w}" height="{body_h}" rx="5" fill="{BODY}" stroke="{INK}" stroke-width="1.5"/>')
    if spec.get("latch"):
        lw = min(body_w * 0.5, 70)
        lx = x0 + (body_w - lw) / 2
        parts.append(f'<path d="M{lx:.1f},{top} L{lx + 6:.1f},{top - 12} L{lx + lw - 6:.1f},{top - 12} L{lx + lw:.1f},{top}" '
                     f'fill="{BODY}" stroke="{INK}" stroke-width="1.5"/>')
        parts.append(_text(lx + lw / 2, top - 3, "latch", size=8, fill="#5d6670"))
    for i, cav in enumerate(order):
        cx = x0 + 12 + r + i * step
        d, b = _cavity(f"{uid}g{i}", cx, y, r, cav, gender, "square")
        defs.append(d)
        parts.append(b)
        weight = "bold" if str(cav.pin) == str(cavities[0].pin) else "normal"
        parts.append(_text(cx, top + body_h + 13, cav.pin, size=11, weight=weight))
        if cav.label:
            parts.append(_text(cx + 4, top + body_h + 20, str(cav.label)[:18], size=10, anchor="end", rotate=-90))
    # Pin 1 marker on the housing.
    p1x = x0 + 12 + r + (0 if spec.get("pin1", "left") == "left" else (n - 1) * step)
    parts.append(f'<path d="M{p1x - 5:.1f},{top + body_h - 1} L{p1x + 5:.1f},{top + body_h - 1} L{p1x:.1f},{top + body_h - 7}" fill="{INK}"/>')
    caption = f'{spec.get("view", "mating face")} · {gender} · schematic'
    return _wrap(width, height, defs, "".join(parts), caption)


def draw_dsub(cavities: List[Cavity], spec: Dict[str, Any], uid: str) -> Face:
    n = len(cavities)
    rows = spec.get("rows") or DSUB_ROWS.get(n) or [(n + 1) // 2, n // 2]
    gender = spec.get("gender", "female")
    step, r, row_gap = 34, 9, 34
    widest = max(rows)
    label_pad = 70
    shell_w = (widest - 1) * step + 2 * r + 44
    width = int(shell_w + 2 * 16)
    top = label_pad
    shell_h = (len(rows) - 1) * row_gap + 2 * r + 30
    height = int(top + shell_h + label_pad)
    x0 = 16
    defs, parts = [], []
    # D-shaped shell: wider at the top, both sides slanted by 10 degrees.
    inset = shell_h * 0.18
    parts.append(
        f'<path d="M{x0 + 6},{top} L{x0 + shell_w - 6},{top} Q{x0 + shell_w},{top} {x0 + shell_w - 1},{top + 6} '
        f'L{x0 + shell_w - inset},{top + shell_h - 6} Q{x0 + shell_w - inset - 1},{top + shell_h} {x0 + shell_w - inset - 7},{top + shell_h} '
        f'L{x0 + inset + 7},{top + shell_h} Q{x0 + inset + 1},{top + shell_h} {x0 + inset},{top + shell_h - 6} '
        f'L{x0 + 1},{top + 6} Q{x0},{top} {x0 + 6},{top} Z" fill="{BODY}" stroke="{INK}" stroke-width="1.5"/>'
    )
    # Male numbering runs left to right on the mating face; female is the mirror image.
    idx = 0
    for ri, count in enumerate(rows):
        row = cavities[idx:idx + count]
        idx += count
        y = top + 15 + r + ri * row_gap
        row_w = (count - 1) * step
        start = x0 + shell_w / 2 - row_w / 2
        placed = row if gender == "male" else list(reversed(row))
        for i, cav in enumerate(placed):
            cx = start + i * step
            d, b = _cavity(f"{uid}d{ri}_{i}", cx, y, r, cav, gender, "round")
            defs.append(d)
            parts.append(b)
            num_y = y - r - 4 if ri == 0 else y + r + 12
            parts.append(_text(cx, num_y, cav.pin, size=10, weight="bold" if str(cav.pin) == "1" else "normal"))
            if cav.label:
                if ri == 0:
                    parts.append(_text(cx + 4, top - 4, str(cav.label)[:10], size=10, anchor="start", rotate=-90))
                elif ri == len(rows) - 1:
                    parts.append(_text(cx + 4, top + shell_h + 6, str(cav.label)[:10], size=10, anchor="end", rotate=-90))
    caption = f'{spec.get("view", "mating face")} · {gender} · schematic'
    return _wrap(width, height, defs, "".join(parts), caption)


def draw_xt(cavities: List[Cavity], spec: Dict[str, Any], uid: str) -> Face:
    gender = spec.get("gender", "female")
    r = 14
    x0, top, w, h = 20, 14, 130, 54
    c = 14  # chamfer on the negative side
    defs, parts = [], []
    parts.append(
        f'<path d="M{x0},{top} L{x0 + w - c},{top} L{x0 + w},{top + c} L{x0 + w},{top + h - c} '
        f'L{x0 + w - c},{top + h} L{x0},{top + h} Z" fill="{BODY}" stroke="{INK}" stroke-width="1.5"/>'
    )
    # Square end is +, chamfered end is - (the common convention; the housing is also marked).
    positions = [x0 + 34, x0 + w - 38]
    for i, (cav, cx) in enumerate(zip(cavities[:2], positions)):
        d, b = _cavity(f"{uid}x{i}", cx, top + h / 2, r, cav, gender, "round")
        defs.append(d)
        parts.append(b)
        sign = "+" if i == 0 else "−"
        parts.append(_text(cx, top + h + 16, f"{cav.pin} ({sign})", size=11, weight="bold"))
        if cav.label and cav.label not in ("+", "-"):
            parts.append(_text(cx, top + h + 30, cav.label, size=10))
    width, height = x0 * 2 + w, top + h + 36
    caption = f'{spec.get("view", "mating face")} · {gender} · schematic'
    return _wrap(width, height, defs, "".join(parts), caption)


STYLES = {"row": draw_row, "dsub": draw_dsub, "xt": draw_xt}


def draw(cavities: List[Cavity], spec: Optional[Dict[str, Any]], uid: str = "f") -> Optional[Face]:
    if not spec or not cavities:
        return None
    style = spec.get("style", "row")
    if style not in STYLES:
        raise ValueError(f"unknown face style {style!r} (use one of: {', '.join(STYLES)})")
    return STYLES[style](cavities, spec, uid)


def to_png(face: Face, path, scale: float = 3.0) -> bool:
    """Rasterise for Graphviz. Returns False when cairosvg/cairo is unavailable."""
    try:
        import cairosvg
    except (ImportError, OSError):
        return False
    cairosvg.svg2png(bytestring=face.svg.encode("utf-8"), write_to=str(path), scale=scale)
    return True
