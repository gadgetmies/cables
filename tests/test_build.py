import csv
import shutil

import pytest

from cables.cli import main

pytestmark = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")


def test_build_examples(root, tmp_path):
    out = tmp_path / "out"
    assert main(["build", str(root / "harnesses"), "-o", str(out)]) == 0
    assert (out / "index.html").is_file()
    d = out / "drone"
    for suffix in (".html", ".svg", ".png", ".wirelist.csv", ".netlist.csv", ".bom.csv", ".bom.tsv"):
        assert (d / f"telem_sik_radio{suffix}").is_file(), suffix
    rows = list(csv.DictReader(open(d / "telem_sik_radio.wirelist.csv", encoding="utf-8")))
    assert rows[1]["From"] == "FC:2" and rows[1]["To signal"] == "RX (IN)"
    try:
        import cairosvg  # noqa: F401
        svg = (d / "telem_sik_radio.svg").read_text(encoding="utf-8")
        assert svg.count("data:image/svg+xml") == 2  # both connector faces, as vectors
    except (ImportError, OSError):
        pass
    html = (d / "can_extension.html").read_text(encoding="utf-8")
    assert '<figure class="face">' in html
    assert "<svg" in html and "IPC/WHMA-A-620, Class 2" in html and "twist wire pairs 2+3" in html


def test_check_exit_codes(tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("connectors:\n  A: {use: pixhawk.telem}\n  B: {use: pixhawk.telem}\n"
                   "cables:\n  W: {wirecount: 6}\nconnections:\n  - [A: [1-6], W: [1-6], B: [1-6]]\n")
    assert main(["check", str(bad)]) == 1
    assert "S010" in capsys.readouterr().out
    broken = tmp_path / "broken.yml"
    broken.write_text("connectors: {A: {use: nope.x}}\n")
    assert main(["check", str(broken)]) == 1


def test_library_listing(capsys):
    assert main(["library", "pixhawk"]) == 0
    assert "pixhawk.telem" in capsys.readouterr().out


def test_build_without_cairosvg(root, tmp_path, monkeypatch):
    import cables.build

    monkeypatch.setattr(cables.build, "to_png", lambda face, path: False)
    out = tmp_path / "out"
    assert main(["build", str(root / "harnesses" / "drone" / "can_extension.yml"), "-o", str(out)]) == 0
    assert "data:image" not in (out / "drone" / "can_extension.svg").read_text(encoding="utf-8")
    assert '<figure class="face">' in (out / "drone" / "can_extension.html").read_text(encoding="utf-8")


def test_loops_on_named_pins_are_drawn(root, tmp_path):
    out = tmp_path / "out"
    assert main(["build", str(root / "harnesses" / "generic" / "moza_sony.yml"), "-o", str(out), "-f", "svg", "gv"]) == 0
    gv = (out / "generic" / "moza_sony.gv").read_text(encoding="utf-8")
    assert "USB:p3r:e -- USB:p15r:e" in gv and "USB:p10r:e -- USB:p22r:e" in gv  # A3-B3, A10-B10
    html = (out / "generic" / "moza_sony.html").read_text(encoding="utf-8")
    assert "USB:A3 TX1- \u2192 TRS:T TIP" in html
