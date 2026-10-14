"""Manufacturing outputs: wire list, netlist, BOM and the drawing sheet."""

from __future__ import annotations

import csv
import html
import io
import re
from typing import Any, Dict, List, Optional, Sequence

from wireviz.wv_bom import bom_list
from wireviz.wv_colors import get_color_hex

from . import APP_NAME, __version__
from .checks import ERROR, INFO, WARNING, Finding
from .model import Model, Wire

WIRELIST_HEADER = [
    "Wire", "Cable", "No.", "Signal", "Color", "Gauge", "Length",
    "From", "From signal", "To", "To signal", "Twisted with",
]


def _ends(ends) -> str:
    return " + ".join(e.name for e in ends)


def _labels(ends) -> str:
    return " + ".join(e.label for e in ends if e.label)


def _length(w: Wire) -> str:
    return f"{w.length:g} {w.length_unit}" if w.length else ""


def wirelist_rows(model: Model) -> List[List[str]]:
    rows = []
    for w in model.wires:
        if w.is_shield and not (w.left or w.right):
            continue
        rows.append([
            f"{w.cable}-{w.wire}", w.cable, str(w.wire), w.net.name if w.net else "",
            w.color_name or w.color, w.gauge_text, _length(w),
            _ends(w.left), _labels(w.left), _ends(w.right), _labels(w.right),
            f"{w.cable}-{w.twisted_with}" if w.twisted_with else "",
        ])
    return rows


def jumper_rows(model: Model) -> List[List[str]]:
    rows = []
    for net in model.nets:
        for a, b, kind in net.jumpers:
            rows.append([kind, a.name, a.label, b.name, b.label])
    return rows


def netlist_rows(model: Model) -> List[List[str]]:
    """One row per net with every contact in it; what a continuity tester needs."""
    rows = []
    for net in model.nets:
        if len(net.ends) < 2:
            continue
        rows.append([f"N{net.id}", net.name, " ".join(e.name for e in net.ends)])
    return rows


def bom_rows(model: Model) -> List[List[str]]:
    return [[str(c) for c in row] for row in bom_list(model.harness.bom())]


def to_csv(header: Optional[Sequence[str]], rows: List[List[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    if header:
        writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def wirelist_csv(model: Model) -> str:
    return to_csv(WIRELIST_HEADER, wirelist_rows(model))


def netlist_csv(model: Model) -> str:
    return to_csv(["Net", "Name", "Contacts"], netlist_rows(model))


def bom_csv(model: Model) -> str:
    return to_csv(None, bom_rows(model))


# Drawing ---------------------------------------------------------------------

def _as_list(value) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def drawing_notes(model: Model) -> List[str]:
    mfg = model.manufacturing
    notes = []
    if mfg.get("ipc_class"):
        notes.append(f"Workmanship and acceptance per IPC/WHMA-A-620, Class {mfg['ipc_class']}, unless stated otherwise.")
    tol = mfg.get("length_tolerance")
    ref = mfg.get("length_reference", "connector mating face to connector mating face")
    if tol:
        notes.append(f"Cable lengths are measured {ref}. Length tolerance {tol}.")
    else:
        notes.append(f"Cable lengths are measured {ref}.")
    for cname, cable in model.harness.cables.items():
        pairs = model.loaded.cable_extras(cname).twisted
        if pairs:
            listed = ", ".join(f"{a}+{b}" for a, b in pairs)
            rate = f" at {mfg['twist_rate']}" if mfg.get("twist_rate") else ""
            notes.append(f"{cname}: twist wire pairs {listed}{rate}.")
    for label in _as_list(mfg.get("labels")):
        notes.append(f"Label: {label}")
    for test in _as_list(mfg.get("tests")):
        notes.append(f"Test: {test}")
    compliance = _as_list(mfg.get("compliance"))
    if compliance:
        notes.append("Materials compliant with " + ", ".join(compliance) + ".")
    notes.extend(_as_list(mfg.get("notes")))
    return notes


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _swatch(color: str) -> str:
    if not color:
        return ""
    hexes = get_color_hex(color)
    if len(hexes) == 1:
        bg = hexes[0]
    else:
        step = 100 / len(hexes)
        stops = ", ".join(f"{h} {i * step:.0f}% {(i + 1) * step:.0f}%" for i, h in enumerate(hexes))
        bg = f"linear-gradient(90deg, {stops})"
    return f'<span class="sw" style="background:{bg}"></span>'


def _table(header: Sequence[str], rows: List[List[str]], raw_cols: Sequence[int] = ()) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in header)
    body = []
    for row in rows:
        cells = "".join(f"<td>{c if i in raw_cols else _e(c)}</td>" for i, c in enumerate(row))
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _heading(name: str) -> str:
    """'__PAD_1' (auto-generated from template PAD) -> 'PAD #1'."""
    if name.startswith("__") and "_" in name[2:]:
        template, n = name[2:].rsplit("_", 1)
        return f"{template} #{n}"
    return name


def _pinout_tables(model: Model, faces: Dict[str, Any]) -> str:
    parts = []
    for name, c in model.harness.connectors.items():
        rows = []
        for i, pin in enumerate(c.pins):
            label = c.pinlabels[i] if i < len(c.pinlabels) and c.pinlabels[i] is not None else ""
            wires = model.wires_at(name, pin)
            if not wires:
                rows.append([_e(pin), _e(label), "", "", "", '<span class="muted">not connected</span>'])
                continue
            for w in wires:
                others = [e for e in w.left + w.right if not (e.connector == name and e.pin == pin)]
                rows.append([
                    _e(pin), _e(label), _e(w.ref), f"{_swatch(w.color)}{_e(w.color_name or w.color)}",
                    _e(w.gauge_text), _e(", ".join(f"{e.name} {e.label}".strip() for e in others)),
                ])
        ext = model.loaded.connector_extras(name)
        desc = ", ".join(_e(x) for x in (c.type, c.subtype) if x)
        pn = " ".join(x for x in (_e(c.manufacturer or ""), f"MPN {_e(c.mpn)}" if c.mpn else "") if x)
        meta = " · ".join(x for x in (desc, pn, f"{c.pincount} pos") if x)
        source = f'<p class="muted">Pinout source: {_e(ext.source)}</p>' if ext.source else ""
        notes = f"<p>{_e(c.notes)}</p>" if c.notes else ""
        face = faces.get(name)
        figure = f'<figure class="face">{face.svg}</figure>' if face else ""
        parts.append(
            f'<section class="pinout"><h3>{_e(_heading(name))}</h3><p class="muted">{meta}</p>{notes}'
            + f'<div class="pinout-body">{figure}<div class="pinout-table">'
            + _table(["Pin", "Signal", "Wire", "Color", "Gauge", "Goes to"], rows, raw_cols=range(6))
            + "</div></div>" + source + "</section>"
        )
    return "".join(parts)


def _findings_html(findings: List[Finding]) -> str:
    if not findings:
        return '<p class="ok">All checks passed.</p>'
    rows = [[f'<span class="sev {f.severity}">{_e(f.severity)}</span>', _e(f.code), _e(f.where), _e(f.message)] for f in findings]
    return _table(["Severity", "Code", "Where", "Finding"], rows, raw_cols=range(4))


def _svg_inline(svg: str) -> str:
    start = svg.find("<svg")
    svg = svg[start:] if start >= 0 else svg
    return re.sub(r"<!--.*?-->", "", svg, flags=re.S)


CSS = """
:root{--fg:#1b1f24;--muted:#5d6670;--line:#c9d0d7;--head:#eef1f4;--bg:#fff;--accent:#0b62c4;
--err:#b42318;--warn:#a15c00;--info:#475467;--okc:#067647}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--fg:#e6e9ec;--muted:#9aa4ae;--line:#3a424b;
--head:#232a31;--bg:#15191d;--accent:#6aa9ff;--err:#ff8a80;--warn:#ffc061;--info:#b0bac4;--okc:#6fd39a}
:root:not([data-theme="light"]) .diagram{background:#fff;border-radius:4px}}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--fg);background:var(--bg)}
main{max-width:1200px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
h3{font-size:15px;margin:18px 0 2px}
.muted{color:var(--muted)} p{margin:4px 0 8px} a{color:var(--accent)}
.titleblock{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border:1px solid var(--line);margin:12px 0}
.titleblock div{padding:6px 8px;border:1px solid var(--line);margin:-1px 0 0 -1px}
.titleblock b{display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.diagram{overflow-x:auto}
.diagram svg{width:100%;min-width:720px;height:auto;display:block}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top;white-space:nowrap}
th{background:var(--head);font-weight:600}
td:last-child{white-space:normal}
.sw{display:inline-block;width:22px;height:10px;border:1px solid #777;margin-right:6px;vertical-align:middle}
.sev{font-weight:600;text-transform:uppercase;font-size:11px}
.sev.error{color:var(--err)} .sev.warning{color:var(--warn)} .sev.info{color:var(--info)} .ok{color:var(--okc)}
ol li{margin:2px 0}
.pinout-body{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start}
.pinout-table{flex:1 1 420px;min-width:0}
.face{margin:0;flex:0 0 auto;max-width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:#fff}
.face svg{display:block}
footer{margin-top:32px;font-size:12px}
@media print{body{padding:0;font-size:11px}h2{break-after:avoid}.pinout,table{break-inside:avoid}
@page{size:A3 landscape;margin:10mm}}
"""


def drawing_html(model: Model, svg: str, findings: List[Finding], files: Dict[str, str],
                 faces: Optional[Dict[str, Any]] = None) -> str:
    meta = model.metadata
    mfg = model.manufacturing
    title = meta.get("title", "Cable")
    date = meta.get("date", "")
    block = [
        ("Title", title), ("Part number", meta.get("pn", "")), ("Revision", meta.get("revision", "")),
        ("Date", date), ("Author", meta.get("author", "")),
        ("IPC/WHMA-A-620", f"Class {mfg['ipc_class']}" if mfg.get("ipc_class") else ""),
        ("Length tolerance", mfg.get("length_tolerance", "")),
    ]
    titleblock = "".join(f"<div><b>{_e(k)}</b>{_e(v) or '&mdash;'}</div>" for k, v in block)
    description = f"<p>{_e(meta.get('description'))}</p>" if meta.get("description") else ""
    notes = "".join(f"<li>{_e(n)}</li>" for n in drawing_notes(model))
    wl = wirelist_rows(model)
    wl_html = [[_e(c) for c in r] for r in wl]
    for row, w in zip(wl_html, [w for w in model.wires if not (w.is_shield and not (w.left or w.right))]):
        row[4] = _swatch(w.color) + row[4]
    jumpers = jumper_rows(model)
    jumper_html = ""
    if jumpers:
        jumper_html = "<h3>Jumpers and mated contacts</h3>" + _table(["Kind", "From", "Signal", "To", "Signal"], jumpers)
    bom = bom_rows(model)
    bom_html = _table(bom[0], bom[1:]) if bom else "<p>No parts.</p>"
    downloads = " · ".join(f'<a href="{_e(href)}">{_e(label)}</a>' for label, href in files.items())
    counts = {s: sum(f.severity == s for f in findings) for s in (ERROR, WARNING, INFO)}
    summary = ", ".join(f"{n} {s}{'s' if n != 1 else ''}" for s, n in counts.items() if n) or "clean"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(meta.get('pn') or title)} {_e(meta.get('revision', ''))}</title>
<style>{CSS}</style></head>
<body><main>
<h1>{_e(title)}</h1>{description}
<div class="titleblock">{titleblock}</div>
<p class="muted">Files: {downloads}</p>
<h2>Diagram</h2><div class="diagram">{_svg_inline(svg)}</div>
<h2>Notes</h2><ol>{notes}</ol>
<h2>Wire list</h2>{_table(WIRELIST_HEADER, wl_html, raw_cols=range(len(WIRELIST_HEADER)))}{jumper_html}
<h2>Connector pinouts</h2>{_pinout_tables(model, faces or {})}
<h2>Bill of materials</h2>{bom_html}
<h2>Design checks <span class="muted">({_e(summary)})</span></h2>{_findings_html(findings)}
<footer class="muted">Generated by {APP_NAME} {__version__} from {_e(model.loaded.path.name if model.loaded.path else 'input')}.</footer>
</main></body></html>
"""


def index_html(entries: List[Dict[str, Any]], title: str = "Cables") -> str:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries:
        groups.setdefault(e["group"], []).append(e)
    sections = []
    for group, items in groups.items():
        rows = []
        for e in items:
            if e.get("failed"):
                status = f'<span class="sev error">failed</span> {_e(e["failed"])}'
            else:
                status = (f'<span class="sev error">{e["errors"]} errors</span>' if e["errors"] else '<span class="ok">ok</span>')
                if e["warnings"]:
                    status += f' <span class="sev warning">{e["warnings"]} warnings</span>'
            link = f'<a href="{_e(e["drawing"])}">{_e(e["title"])}</a>' if e.get("drawing") else _e(e["title"])
            rows.append([link, _e(e.get("pn", "")), _e(e.get("revision", "")), status])
        sections.append(f"<h2>{_e(group)}</h2>" + _table(["Cable", "P/N", "Rev", "Checks"], rows, raw_cols=range(4)))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><style>{CSS}</style></head>
<body><main><h1>{_e(title)}</h1>{''.join(sections)}
<footer class="muted">Generated by {APP_NAME} {__version__}.</footer></main></body></html>
"""
