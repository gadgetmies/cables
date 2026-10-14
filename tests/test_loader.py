import textwrap

import pytest

from cables.loader import HarnessError, load


def y(text):
    return textwrap.dedent(text)


def test_use_merges_library_and_overrides():
    h = load(y("""
        connectors:
          A: {use: pixhawk.telem, notes: mine}
          B: {use: power.xt60_male, pinlabels: [BAT+, BAT-]}
        cables:
          W: {use: wire.ul1571_28awg, colors: [RD]}
        connections: []
        """))
    a = h.data["connectors"]["A"]
    assert a["mpn"] == "GHR-06V-S" and a["notes"] == "mine" and a["pinlabels"][1] == "TX (OUT)"
    assert "use" not in a and "wire_awg" not in a and "source" not in a
    assert h.extras.connectors["A"].wire_awg == [30, 26]
    assert "DS-009" in h.extras.connectors["A"].source
    assert h.data["connectors"]["B"]["pinlabels"] == ["BAT+", "BAT-"]
    assert h.data["cables"]["W"]["gauge"] == "28 AWG"


def test_project_library_shadows_builtin(tmp_path):
    (tmp_path / "library").mkdir()
    (tmp_path / "library" / "pixhawk.yml").write_text("connectors:\n  telem: {pincount: 2, mpn: LOCAL}\n")
    f = tmp_path / "h.yml"
    f.write_text("connectors:\n  A: {use: pixhawk.telem}\n")
    assert load(f).data["connectors"]["A"]["mpn"] == "LOCAL"


@pytest.mark.parametrize("text, msg", [
    ("connectors: {A: {use: nope.x}}", 'library "nope" not found'),
    ("connectors: {A: {use: pixhawk.nope}}", "is not in the connectors"),
    ("connectors: {A: {use: telem}}", "library.entry"),
    ("connectors: {A: {pincount: 1, wire_awg: 26}}", "wire_awg must be"),
    ("cables: {W: {wirecount: 2, twisted: [1, 2]}}", "twisted must be"),
    ("- just a list", "top level"),
])
def test_errors(text, msg):
    with pytest.raises(HarnessError, match=msg):
        load(text)


def test_instance_templates():
    h = load(y("""
        connectors:
          F: {style: simple, type: Ferrule}
          X: {pincount: 2}
        cables:
          W: {wirecount: 2}
        connections:
          - [F., W: [1-2], X.left: [1-2]]
        """))
    assert h.instance_templates == {"__F_1": "F", "__F_2": "F", "W": "W", "left": "X"}
