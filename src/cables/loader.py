"""Load harness YAML, resolve library templates and split out our extensions.

The result is a plain WireViz input dict plus an ``Extras`` object holding
the keys WireViz does not know about.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from wireviz.wv_helper import expand

BUILTIN_LIBRARY = Path(__file__).parent / "library"

# Keys we add on top of WireViz are removed before WireViz sees the data:
#   top level:  manufacturing
#   connectors: use, wire_awg, face, source
#   cables:     use, twisted, source
LIBRARY_ONLY_KEYS = ("library", "description", "source")


class HarnessError(Exception):
    """A problem in the input that stops a harness from being processed."""


@dataclass
class ComponentExtras:
    use: Optional[str] = None
    source: Optional[str] = None
    wire_awg: Optional[List[Any]] = None  # connectors: accepted wire range
    face: Optional[Dict[str, Any]] = None  # connectors: mating face drawing spec
    twisted: List[List[Any]] = field(default_factory=list)  # cables: wire pairs


@dataclass
class Extras:
    manufacturing: Dict[str, Any] = field(default_factory=dict)
    connectors: Dict[str, ComponentExtras] = field(default_factory=dict)
    cables: Dict[str, ComponentExtras] = field(default_factory=dict)


@dataclass
class LoadedHarness:
    path: Optional[Path]
    data: Dict[str, Any]  # WireViz input
    extras: Extras
    # designator of every instance -> designator of the definition it came from
    instance_templates: Dict[str, str] = field(default_factory=dict)

    def connector_extras(self, name: str) -> ComponentExtras:
        return self.extras.connectors.get(self.instance_templates.get(name, name), ComponentExtras())

    def cable_extras(self, name: str) -> ComponentExtras:
        return self.extras.cables.get(self.instance_templates.get(name, name), ComponentExtras())


def read_yaml(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise HarnessError(f"{path}: invalid YAML: {e}") from e


class Library:
    """Lazy collection of library files found on a search path.

    A reference ``pixhawk.telem`` means entry ``telem`` in library
    ``pixhawk``, i.e. ``pixhawk.yml`` in one of the search directories.
    Directories earlier in the path win, so projects can shadow built-ins.
    """

    def __init__(self, search_path: Sequence[Path]):
        self.search_path = [Path(p) for p in search_path]
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _load(self, name: str) -> Dict[str, Any]:
        if name not in self._cache:
            for directory in self.search_path:
                for ext in (".yml", ".yaml"):
                    candidate = directory / f"{name}{ext}"
                    if candidate.is_file():
                        content = read_yaml(candidate) or {}
                        if not isinstance(content, dict):
                            raise HarnessError(f"{candidate}: library must be a mapping")
                        content["__path__"] = candidate
                        self._cache[name] = content
                        break
                if name in self._cache:
                    break
            else:
                searched = ", ".join(str(p) for p in self.search_path)
                raise HarnessError(f'library "{name}" not found (searched: {searched})')
        return self._cache[name]

    def names(self) -> List[str]:
        found = set()
        for directory in self.search_path:
            if directory.is_dir():
                found.update(p.stem for p in directory.glob("*.y*ml"))
        return sorted(found)

    def entries(self, name: str, section: str) -> Dict[str, Any]:
        return self._load(name).get(section) or {}

    def info(self, name: str) -> Dict[str, Any]:
        return {k: v for k, v in self._load(name).items() if k in LIBRARY_ONLY_KEYS or k == "__path__"}

    def resolve(self, ref: str, section: str, _seen: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return the fully merged attributes for a reference."""
        _seen = list(_seen or [])
        if ref in _seen:
            raise HarnessError(f"circular library reference: {' -> '.join(_seen + [ref])}")
        _seen.append(ref)
        if "." not in ref:
            raise HarnessError(f'library reference "{ref}" must look like "library.entry"')
        lib, entry = ref.split(".", 1)
        entries = self.entries(lib, section)
        if entry not in entries:
            available = ", ".join(sorted(entries)) or "none"
            raise HarnessError(f'"{entry}" is not in the {section} of library "{lib}" (available: {available})')
        attrs = copy.deepcopy(entries[entry]) or {}
        # The most specific entry names the source, e.g. pixhawk.telem cites
        # DS-009 even though its housing comes from the jst library.
        source = attrs.get("source") or self._load(lib).get("source")
        parent = attrs.pop("use", None)
        if parent:
            if "." not in parent:  # relative to the same library
                parent = f"{lib}.{parent}"
            merged = self.resolve(parent, section, _seen)
            merged.update(attrs)
            attrs = merged
        if source:
            attrs["source"] = source
        return attrs


def default_search_path(harness_path: Optional[Path], extra: Iterable[Path] = ()) -> List[Path]:
    paths: List[Path] = [Path(p) for p in extra]
    if harness_path is not None:
        for parent in [harness_path.parent, *harness_path.parent.parents]:
            paths.append(parent / "library")
    paths.append(BUILTIN_LIBRARY)
    return paths


def _split_component(name: str, attrs: Any, section: str, library: Library) -> Tuple[Dict, ComponentExtras]:
    if attrs is None:
        attrs = {}
    if not isinstance(attrs, dict):
        raise HarnessError(f'{section[:-1]} "{name}" must be a mapping')
    attrs = copy.deepcopy(attrs)
    ref = attrs.pop("use", None)
    if ref:
        base = library.resolve(ref, section)
        base.update(attrs)
        attrs = base
    extras = ComponentExtras(use=ref, source=attrs.pop("source", None))
    if "wire_awg" in attrs:
        if section != "connectors":
            raise HarnessError(f'cable "{name}": wire_awg is only valid for connectors')
        rng = attrs.pop("wire_awg")
        if not isinstance(rng, list) or len(rng) != 2:
            raise HarnessError(f'connector "{name}": wire_awg must be [min, max], e.g. [30, 26]')
        extras.wire_awg = rng
    if "face" in attrs:
        if section != "connectors":
            raise HarnessError(f'cable "{name}": face is only valid for connectors')
        face = attrs.pop("face")
        if face not in (None, False) and not isinstance(face, dict):
            raise HarnessError(f'connector "{name}": face must be a mapping (e.g. {{style: row}}) or false')
        extras.face = face or None
    if "twisted" in attrs:
        if section != "cables":
            raise HarnessError(f'connector "{name}": twisted is only valid for cables')
        pairs = attrs.pop("twisted") or []
        if not isinstance(pairs, list) or any(not isinstance(p, list) or len(p) != 2 for p in pairs):
            raise HarnessError(f'cable "{name}": twisted must be a list of wire pairs, e.g. [[2, 3]]')
        extras.twisted = pairs
    return attrs, extras


def _instance_templates(connection_sets: list, separator: str) -> Dict[str, str]:
    """Replicate WireViz' designator resolution to map instances to templates."""
    mapping: Dict[str, str] = {}
    autogen: Dict[str, int] = {}

    def resolve(item: str) -> None:
        item = str(item)
        if separator in item and item.count(separator) == 1:
            template, designator = item.split(separator)
            if designator == "":
                autogen[template] = autogen.get(template, 0) + 1
                designator = f"__{template}_{autogen[template]}"
            mapping.setdefault(designator, template)
        else:
            mapping.setdefault(item, item)

    for cset in connection_sets or []:
        if not isinstance(cset, list):
            continue
        counts = []
        for entry in cset:
            if isinstance(entry, list):
                counts.append(len(entry))
            elif isinstance(entry, dict) and entry:
                counts.append(len(expand(list(entry.values())[0])))
        count = counts[0] if counts else 1
        for entry in cset:
            if isinstance(entry, str):
                for _ in range(count):
                    resolve(entry)
            elif isinstance(entry, list):
                for item in entry:
                    resolve(item)
            elif isinstance(entry, dict):
                for key in entry:
                    resolve(key)
    return mapping


def load(source, library_paths: Iterable[Path] = ()) -> LoadedHarness:
    """Load a harness from a path, YAML string or dict."""
    path: Optional[Path] = None
    if isinstance(source, dict):
        raw = copy.deepcopy(source)
    elif isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).suffix in (".yml", ".yaml")):
        path = Path(source).resolve()
        if not path.is_file():
            raise HarnessError(f"{path}: file not found")
        raw = read_yaml(path)
    else:
        try:
            raw = yaml.safe_load(source)
        except yaml.YAMLError as e:
            raise HarnessError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise HarnessError(f"{path or 'input'}: top level must be a mapping")

    library = Library(default_search_path(path, library_paths))
    extras = Extras(manufacturing=raw.pop("manufacturing", None) or {})
    if not isinstance(extras.manufacturing, dict):
        raise HarnessError("manufacturing must be a mapping")

    for section, store in (("connectors", extras.connectors), ("cables", extras.cables)):
        items = raw.get(section) or {}
        if not isinstance(items, dict):
            raise HarnessError(f"{section} must be a mapping of designator: attributes")
        resolved = {}
        for name, attrs in items.items():
            resolved[name], store[name] = _split_component(str(name), attrs, section, library)
        raw[section] = resolved

    raw.setdefault("connections", [])
    separator = (raw.get("options") or {}).get("template_separator", ".")
    instances = _instance_templates(raw["connections"], separator)
    return LoadedHarness(path=path, data=raw, extras=extras, instance_templates=instances)
