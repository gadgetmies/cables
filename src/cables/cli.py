"""Command line interface: ``cables check|build|clean|library``."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from . import APP_NAME, __version__
from .build import Result, analyse, discover, render, write_index
from .checks import ERROR, INFO
from .loader import HarnessError, Library, default_search_path

DEFAULT_INPUT = Path("harnesses")
DEFAULT_OUTPUT = Path("build")


def _print_result(r: Result, verbose: bool) -> None:
    status = "FAILED" if r.failure else ("errors" if r.errors else "ok")
    print(f"{r.source}: {status} ({r.errors} errors, {r.warnings} warnings)")
    if r.failure:
        print(f"  ERROR   {r.failure}")
    for f in r.findings:
        if f.severity == INFO and not verbose:
            continue
        print(f"  {f}")


def _analyse_all(args) -> List[Result]:
    files = discover(args.paths or [DEFAULT_INPUT])
    if not files:
        print("no harness files found", file=sys.stderr)
    return [analyse(f, root, args.library, args.strict) for f, root in files]


def cmd_check(args) -> int:
    results = _analyse_all(args)
    for r in results:
        _print_result(r, args.verbose)
    return 1 if any(r.errors for r in results) else 0


def cmd_build(args) -> int:
    results = _analyse_all(args)
    for r in results:
        if r.model is not None:
            try:
                render(r, args.output, args.formats)
            except Exception as e:  # Graphviz missing, unwritable output ...
                r.failure = f"rendering failed: {type(e).__name__}: {e}"
        _print_result(r, args.verbose)
    index = write_index(results, args.output)
    print(f"wrote {index}")
    return 1 if any(r.errors for r in results) else 0


def cmd_clean(args) -> int:
    if args.output.exists():
        shutil.rmtree(args.output)
        print(f"removed {args.output}")
    return 0


def cmd_library(args) -> int:
    lib = Library(default_search_path(Path.cwd() / "_", args.library))
    names = [args.name] if args.name else lib.names()
    for name in names:
        info = lib.info(name)
        print(f"{name}  ({info['__path__']})")
        if info.get("description"):
            print(f"  {' '.join(str(info['description']).split())}")
        for section in ("connectors", "cables"):
            for entry, attrs in lib.entries(name, section).items():
                if args.name:
                    full = lib.resolve(f"{name}.{entry}", section)
                    labels = full.get("pinlabels")
                    detail = ", ".join(str(x) for x in (full.get("type"), full.get("mpn"), full.get("gauge")) if x)
                    print(f"  {section[:-1]:9} {name}.{entry:22} {detail}")
                    if labels:
                        print(f"  {'':9} {'':{len(name) + 23}} pins: {', '.join(str(x) for x in labels)}")
                else:
                    print(f"  {section[:-1]:9} {name}.{entry}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=APP_NAME, description="Document, check and order cables (WireViz based).")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp, inputs=True):
        if inputs:
            sp.add_argument("paths", nargs="*", type=Path, help=f"harness files or directories (default: {DEFAULT_INPUT}/)")
            sp.add_argument("--strict", action="store_true", help="treat warnings as errors (use before ordering)")
            sp.add_argument("-v", "--verbose", action="store_true", help="also print info findings")
        sp.add_argument("-L", "--library", action="append", type=Path, default=[], help="extra library directory (repeatable)")

    sp = sub.add_parser("check", help="validate harness files")
    common(sp)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("build", help="check and write diagrams, wire lists, BOMs and drawings")
    common(sp)
    sp.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help=f"output directory (default: {DEFAULT_OUTPUT}/)")
    sp.add_argument("-f", "--formats", nargs="+", default=["svg", "png"], choices=["svg", "png", "gv"], help="diagram formats")
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("clean", help="remove the output directory")
    sp.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    sp.set_defaults(func=cmd_clean)

    sp = sub.add_parser("library", help="list library connectors and wires")
    sp.add_argument("name", nargs="?", help="show the entries of one library in detail")
    common(sp, inputs=False)
    sp.set_defaults(func=cmd_library)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HarnessError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
