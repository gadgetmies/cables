# Design checks

`cables check` and `cables build` run these checks. Errors give a non-zero
exit code. `--strict` turns warnings into errors, so run it before you send a
drawing out for quotes. To silence a check for one harness, add
`manufacturing: {ignore: [CODE]}`.

Signal checks read the `pinlabels` text, so they only work when pins are
named. The names are matched loosely: `TX (OUT)`, `UART1_TX` and `TXD` all
count as TX, and `+5V`, `VCC` and `VDD_3V3` all count as supplies.

| Code | Severity | What it means |
|---|---|---|
| C001 | warning | WireViz reported a problem, such as an unknown colour name |
| C002 | warning | A connector or cable is defined but never used in `connections` |
| C010 | info | A shield is not terminated at either end |
| C011 | warning | A wire is not connected at either end |
| C012 | info | A wire has one free end (a flying lead) |
| C013 | info | More than one wire ends in the same contact. Check that the contact accepts the combined cross section |
| G001 | error | The wire gauge is outside the range the connector's contacts accept (`wire_awg`) |
| G002 | warning | A cable has no gauge |
| G003 | warning | A cable's gauge unit is neither AWG nor mm² |
| S001 | error | A supply pin is connected to a ground pin |
| S002 | error | Supplies with different voltages are joined, e.g. `+5V` and `VDD_3V3` |
| S003 | error | A supply pin is joined to a signal pin |
| S004 | error | A ground pin is joined to a signal pin |
| S010 | error | TX is joined to TX, RX to RX, CTS to CTS or RTS to RTS. Serial lines must cross |
| S011 | error / warning | Swapped pairs: I²C SCL↔SDA, CAN_H↔CAN_L or D+↔D- are errors. MOSI↔MISO, or TX/RX joined to CTS/RTS, are warnings |
| T001 | error | A `twisted` pair names a wire the cable does not have |
| T002 | warning | A differential pair (CAN_H/CAN_L, D+/D-) runs in one cable but is not declared `twisted` |
| M001 | warning | `metadata.pn` or `metadata.revision` is missing |
| M002 | warning / error | `manufacturing.ipc_class` is missing (warning) or is not 1, 2 or 3 (error) |
| M003 | warning | `manufacturing.length_tolerance` is missing |
| M004 | warning | A connector has no `mpn`. Set `ignore_in_bom: true` on items that are not parts, such as a tinned end |
| M005 | warning | A cable has no length |
| M006 | warning | A cable has no wire colours |
| M007 | warning | A cable has neither `type` nor `mpn` |
