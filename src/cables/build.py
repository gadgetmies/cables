"""Find harness files, check them and write all outputs."""

from __future__ import annotations

import base64
import contextlib
import copy
import dataclasses
import io
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from . import reports
from .checks import ERROR, WARNING, Finding, run_checks
from .faces import Face, to_png
from .loader import HarnessError, load
from .model import Model, build_model, parse_harness

SKIP_DIRS = {"library", "build", ".git", "node_modules", "__pycache__"}


@dataclass
class Result:
    source: Path
    group: str
    model: Optional[Model] = None
    findings: List[Finding] = field(default_factory=list)
    failure: Optional[str] = None
    outputs: List[Path] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(f.severity == ERROR for f in self.findings) + (1 if self.failure else 0)

    @property
    def warnings(self) -> int:
        return sum(f.severity == WARNING for f in self.findings)


def discover(paths: Sequence[Path]) -> List[tuple]:
    """Return (file, root) pairs; root is used to derive the output group."""
    found = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            found.append((p, p.parent))
        elif p.is_dir():
            for f in sorted(list(p.rglob("*.yml")) + list(p.rglob("*.yaml"))):
                if not SKIP_DIRS.intersection(part for part in f.relative_to(p).parts[:-1]):
                    found.append((f, p))
        else:
            raise HarnessError(f"{p}: no such file or directory")
    return found


def analyse(path: Path, root: Path, library_paths: Iterable[Path] = (), strict: bool = False) -> Result:
    group = str(path.parent.relative_to(root)) if path.parent != root else root.name
    result = Result(source=path, group=group)
    try:
        loaded = load(path, library_paths)
        result.model = build_model(loaded)
        result.findings = run_checks(result.model, strict=strict)
    except HarnessError as e:
        result.failure = str(e)
    return result


def render(result: Result, out_dir: Path, formats: Sequence[str] = ("svg", "png")) -> None:
    """Write diagram, CSVs and drawing for one analysed harness."""
    model = result.model
    assert model is not None
    target = out_dir / result.group
    target.mkdir(parents=True, exist_ok=True)
    stem = result.source.stem
    base = target / stem
    fmt = tuple(dict.fromkeys(("svg",) + tuple(f for f in formats if f in ("png", "svg", "gv"))))
    faces = {name: model.face(name) for name in model.harness.connectors}
    faces = {name: f for name, f in faces.items() if f is not None}
    harness = _harness_with_faces(model, faces, target / f"{stem}.faces") if faces else None
    harness = _fix_loop_ports(harness or copy.deepcopy(model.harness))
    with contextlib.redirect_stdout(io.StringIO()):  # WireViz prints repeated warnings
        harness.output(filename=base, fmt=fmt + ("tsv",), view=False)
    svg_path = target / f"{stem}.svg"
    svg = _vectorise_faces(svg_path.read_text(encoding="utf-8"), target / f"{stem}.faces", faces)
    svg_path.write_text(svg, encoding="utf-8")

    files = {}
    for label, suffix, content in (
        ("Wire list (CSV)", ".wirelist.csv", reports.wirelist_csv(model)),
        ("Netlist (CSV)", ".netlist.csv", reports.netlist_csv(model)),
        ("BOM (CSV)", ".bom.csv", reports.bom_csv(model)),
    ):
        p = target / f"{stem}{suffix}"
        p.write_text(content, encoding="utf-8")
        files[label] = p.name
        result.outputs.append(p)
    for label, ext in (("Diagram (SVG)", "svg"), ("Diagram (PNG)", "png"), ("Graphviz", "gv")):
        if ext in fmt:
            files[label] = f"{stem}.{ext}"
            result.outputs.append(target / f"{stem}.{ext}")
    files["Source (YAML)"] = result.source.name
    (target / result.source.name).write_bytes(result.source.read_bytes())

    drawing = target / f"{stem}.html"
    drawing.write_text(reports.drawing_html(model, svg, result.findings, files, faces), encoding="utf-8")
    result.outputs.append(drawing)


def _fix_loop_ports(harness):
    """Work around WireViz 0.4.1 drawing loops to port p<pin name> while
    ports are numbered p<pin index>; loops on pins named e.g. A3 vanish.
    Only call this on a harness used for rendering, not for the model."""
    for c in harness.connectors.values():
        c.loops = [[c.pins.index(p) + 1 for p in loop] for loop in c.loops]
    return harness


def _harness_with_faces(model: Model, faces: Dict[str, Face], face_dir: Path):
    """Re-parse the harness with each connector's face drawing as its image.

    Graphviz cannot load SVG images, so it gets a PNG rendering of each face;
    _vectorise_faces() swaps them back for the SVG afterwards. Without
    cairosvg the diagram has no faces (the drawing page still shows them).
    """
    face_dir.mkdir(parents=True, exist_ok=True)
    data = copy.deepcopy(model.loaded.data)
    instances = Counter(model.loaded.instance_templates.values())
    added = False
    for name, face in faces.items():
        # Template definitions used several times share one image, so only
        # connectors that are their own single instance get a coloured face.
        if name not in data["connectors"] or instances.get(name, 0) != 1:
            continue
        png = face_dir / f"{name}.png"
        if not to_png(face, png):
            break
        data["connectors"][name]["image"] = {
            "src": str(png.resolve()),
            "width": face.width,
            "height": face.height,
        }
        added = True
    if not added:
        return None
    loaded = dataclasses.replace(model.loaded, data=data)
    harness, _ = parse_harness(loaded)
    return harness


def _vectorise_faces(svg: str, face_dir: Path, faces: Dict[str, Face]) -> str:
    for name, face in faces.items():
        png = face_dir / f"{name}.png"
        if png.is_file():
            b64 = base64.b64encode(png.read_bytes()).decode("ascii")
            svg = svg.replace(f"data:image/png;base64, {b64}", face.data_uri())
    return svg


def write_index(results: List[Result], out_dir: Path) -> Path:
    entries = []
    for r in results:
        meta = r.model.metadata if r.model else {}
        entries.append({
            "group": r.group,
            "title": meta.get("title") or r.source.stem,
            "pn": meta.get("pn", ""),
            "revision": meta.get("revision", ""),
            "errors": r.errors,
            "warnings": r.warnings,
            "failed": r.failure,
            "drawing": f"{r.group}/{r.source.stem}.html" if r.model else None,
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    index.write_text(reports.index_html(entries), encoding="utf-8")
    return index
