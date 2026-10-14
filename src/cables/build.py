"""Find harness files, check them and write all outputs."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from . import reports
from .checks import ERROR, WARNING, Finding, run_checks
from .loader import HarnessError, load
from .model import Model, build_model

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
    with contextlib.redirect_stdout(io.StringIO()):  # WireViz prints repeated warnings
        model.harness.output(filename=base, fmt=fmt + ("tsv",), view=False)
    svg = (target / f"{stem}.svg").read_text(encoding="utf-8")

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
    drawing.write_text(reports.drawing_html(model, svg, result.findings, files), encoding="utf-8")
    result.outputs.append(drawing)


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
