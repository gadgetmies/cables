import textwrap

from cables.build import discover
from cables.checks import ERROR, run_checks
from cables.loader import load
from cables.model import build_model


def findings(text, strict=False):
    return run_checks(build_model(load(textwrap.dedent(text))), strict=strict)


def codes(fs, severity=None):
    return sorted({f.code for f in fs if severity is None or f.severity == severity})


GOOD_META = """
metadata: {title: T, pn: P-1, revision: A}
manufacturing: {ipc_class: 2, length_tolerance: ±5 mm}
"""


def test_examples_have_no_errors(root):
    for path, _ in discover([root / "harnesses"]):
        fs = run_checks(build_model(load(path)))
        assert not [f for f in fs if f.severity == ERROR], (path, fs)


def test_drone_examples_are_order_ready(root):
    for path, _ in discover([root / "harnesses" / "drone"]):
        fs = run_checks(build_model(load(path)), strict=True)
        assert not [f for f in fs if f.severity == ERROR], (path, fs)


def test_crossed_serial_is_clean_and_straight_is_not():
    base = GOOD_META + textwrap.dedent("""
    connectors:
      FC: {use: pixhawk.telem}
      R: {use: pixhawk.%s}
    cables:
      W: {use: wire.ul1571_28awg, length: 100 mm, colors: [RD, BK, BK, BK, BK, BK]}
    connections:
      - [FC: [1-6], W: [1-6], R: [1-6]]
    """)
    assert codes(findings(base % "telem_peripheral"), ERROR) == []
    assert codes(findings(base % "telem"), ERROR) == ["S010"]


def test_gauge_does_not_fit_contact():
    fs = findings("""
    connectors:
      A: {use: jst.gh2}
      B: {use: jst.gh2}
    cables:
      W: {use: wire.ul1007_22awg, colors: [RD, BK]}
    connections:
      - [A: [1-2], W: [1-2], B: [1-2]]
    """)
    g = [f for f in fs if f.code == "G001"]
    assert len(g) == 2 and "accept 30–26 AWG" in g[0].message


def test_metric_gauge_is_converted():
    fs = findings("""
    connectors:
      A: {use: jst.gh2}
    cables:
      W: {gauge: 0.08 mm2, colors: [RD, BK]}
    connections:
      - [A: [1-2], W: [1-2]]
    """)
    assert "G001" not in codes(fs)


def test_supply_short_and_swaps():
    fs = findings("""
    connectors:
      A: {use: pixhawk.i2c}
      B: {use: pixhawk.i2c}
      C: {use: pixhawk.can}
      D: {use: pixhawk.can}
    cables:
      W: {wirecount: 4}
      V: {wirecount: 4}
    connections:
      - [A: [1-4], W: [1-4], B: [4, 3, 2, 1]]
      - [C: [1-4], V: [1-4], D: [1, 3, 2, 4]]
    """)
    assert {"S001", "S011"} <= set(codes(fs, ERROR))


def test_different_rails():
    fs = findings("""
    connectors:
      A: {pinlabels: [+5V]}
      B: {pinlabels: [VDD_3V3]}
    cables:
      W: {wirecount: 1}
    connections:
      - [A: [1], W: [1], B: [1]]
    """)
    assert "S002" in codes(fs, ERROR)


def test_can_twist_warning():
    text = """
    connectors:
      A: {use: pixhawk.can}
      B: {use: pixhawk.can}
    cables:
      W: {wirecount: 4%s}
    connections:
      - [A: [1-4], W: [1-4], B: [1-4]]
    """
    assert "T002" in codes(findings(text % ""))
    assert "T002" not in codes(findings(text % ", twisted: [[2, 3]]"))
    assert "T001" in codes(findings(text % ", twisted: [[2, 9]]"))


def test_manufacturing_and_strict_and_ignore():
    text = """
    manufacturing: {ignore: [M002]}
    connectors:
      A: {pincount: 1}
    cables:
      W: {wirecount: 1}
    connections:
      - [A: [1], W: [1]]
    """
    fs = findings(text)
    assert {"M001", "M003", "M004", "M005", "M006", "M007"} <= set(codes(fs))
    assert "M002" not in codes(fs)
    assert "M001" in codes(findings(text, strict=True), ERROR)


def test_unused_and_unterminated():
    fs = findings("""
    connectors:
      A: {pincount: 2}
      UNUSED: {pincount: 1}
    cables:
      W: {wirecount: 3}
    connections:
      - [A: [1], W: [1]]
    """)
    assert {"C002", "C011", "C012"} <= set(codes(fs))
