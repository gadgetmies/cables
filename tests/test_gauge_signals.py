import pytest

from cables import gauge as g
from cables import signals as s


@pytest.mark.parametrize("awg, mm2", [(28, 0.0810), (26, 0.129), (22, 0.326), (12, 3.31), (0, 53.5)])
def test_awg_to_mm2(awg, mm2):
    assert g.awg_to_mm2(awg) == pytest.approx(mm2, rel=0.01)


def test_round_trip_and_nearest():
    assert g.mm2_to_awg(g.awg_to_mm2(24)) == pytest.approx(24)
    assert g.nearest_awg(0.25) == 23
    assert g.nearest_metric(g.awg_to_mm2(18)) == 0.75


def test_parse_awg():
    assert g.parse_awg("4/0") == -3
    assert g.parse_awg("00") == -1
    assert g.parse_awg("28 AWG") == 28
    assert g.format_awg(-3) == "4/0"


def test_normalise_units():
    assert g.normalise("28", "AWG")[0] == 28
    awg, mm2 = g.normalise(0.5, "mm²")
    assert mm2 == 0.5 and round(awg) == 20
    assert g.normalise(1, "kcmil") == (None, None)


def test_awg_in_range_any_order():
    assert g.awg_in_range(28, [30, 26])
    assert g.awg_in_range(28, [26, 30])
    assert not g.awg_in_range(22, [30, 26])


@pytest.mark.parametrize("label, role", [
    ("VCC", s.POWER), ("+5V", s.POWER), ("VDD_3V3", s.POWER), ("BAT+", s.POWER), ("TARGET VOLTAGE", s.POWER),
    ("GND", s.GROUND), ("BAT-", s.GROUND), ("-", s.GROUND),
    ("TX (OUT)", s.TX), ("UART1_RX", s.RX), ("CONSOLE TX (OUT)", s.TX), ("RXD", s.RX),
    ("CTS (IN)", s.CTS), ("I2C1 SCL", s.SCL), ("SDA", s.SDA),
    ("CAN_H", s.CAN_H), ("CANL", s.CAN_L), ("SPI_EXT_MISO", s.MISO), ("D+", s.DIFF_P), ("USB_DM", s.DIFF_N),
    ("VOLTAGE", None), ("CURRENT", None), ("BUZZER", None), ("", None),
])
def test_classify(label, role):
    assert s.classify(label) == role


def test_voltage():
    assert s.voltage("VDD_3V3") == 3.3
    assert s.voltage("+5V") == 5
    assert s.voltage("+5.3V") == 5.3
    assert s.voltage("VCC") is None
