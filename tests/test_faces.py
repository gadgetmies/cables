import re

import pytest

from cables.faces import Cavity, draw
from cables.loader import HarnessError, load
from cables.model import build_model


def cavs(n, labels=None, colors=None):
    labels = labels or [""] * n
    colors = colors or [["BK"]] * n
    return [Cavity(pin=i + 1, label=labels[i], colors=colors[i]) for i in range(n)]


def x_of_pin(svg, pin):
    """x of the pin number text in a drawing."""
    m = re.search(rf'<text x="([\d.]+)" y="[\d.]+"[^>]*>{pin}</text>', svg)
    return float(m.group(1))


def test_row_face_shows_pins_labels_and_colours():
    face = draw(cavs(4, ["VCC", "CAN_H", "CAN_L", "GND"], [["RD"], ["BK"], ["BK"], []]), {"style": "row", "latch": True})
    assert "CAN_H" in face.svg and "latch" in face.svg
    assert "#ff0000" in face.svg  # red wire in pin 1
    assert x_of_pin(face.svg, 1) < x_of_pin(face.svg, 4)
    right = draw(cavs(4), {"style": "row", "pin1": "right"})
    assert x_of_pin(right.svg, 1) > x_of_pin(right.svg, 4)


def test_dsub_female_is_mirror_of_male():
    male = draw(cavs(9), {"style": "dsub", "gender": "male"}).svg
    female = draw(cavs(9), {"style": "dsub", "gender": "female"}).svg
    assert x_of_pin(male, 1) < x_of_pin(male, 5)
    assert x_of_pin(female, 1) > x_of_pin(female, 5)


def test_xt_face_and_striped_wire():
    face = draw(cavs(2, ["BAT+", "BAT-"], [["WHRD"], ["BK"]]), {"style": "xt", "gender": "male"})
    assert "linearGradient" in face.svg and "1 (+)" in face.svg
    assert face.data_uri().startswith("data:image/svg+xml;base64,")


def test_no_spec_no_face_and_unknown_style():
    assert draw(cavs(2), None) is None
    with pytest.raises(ValueError):
        draw(cavs(2), {"style": "hexagon"})


def test_model_face_uses_library_spec_and_wire_colours():
    m = build_model(load("""
connectors:
  A: {use: pixhawk.can}
  B: {use: pixhawk.can, face: false}
cables:
  W: {colors: [RD, BK, BK, BK]}
connections:
  - [A: [1-4], W: [1-4], B: [1-4]]
"""))
    assert "CAN_L" in m.face("A").svg
    assert m.face("B") is None


def test_face_must_be_mapping():
    with pytest.raises(HarnessError, match="face must be"):
        load("connectors: {A: {pincount: 1, face: row}}")


def test_usbc_plug_is_mirror_of_receptacle_and_shows_bridges():
    m = build_model(load("""
connectors:
  USB: {use: usb.usbc_plug, loops: [[A3, B3]]}
  J: {use: audio.trs_plug}
cables:
  W: {colors: [WH], shield: true}
connections:
  - [USB: [A3, SHELL], W: [1, s], J: [T, S]]
"""))
    cav = {c.pin: c for c in m.cavities("USB")}
    assert cav["B3"].bridged == ["A3"] and not cav["B3"].populated
    plug = m.face("USB").svg
    assert "grey = bridged" in plug and "shield on shell" in plug
    assert x_of_pin(plug, "A1") > x_of_pin(plug, "A12")  # plug face is mirrored
    receptacle = draw(m.cavities("USB"), {"style": "usbc", "gender": "female"}).svg
    assert x_of_pin(receptacle, "A1") < x_of_pin(receptacle, "A12")
    trs = m.face("J").svg
    assert "TIP" in trs and "SLEEVE" in trs and "n/c" in trs  # ring unused
    assert x_of_pin(trs, "T") > x_of_pin(trs, "S")  # tip at the end, sleeve by the handle
