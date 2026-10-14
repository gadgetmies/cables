# cables

Describe cables, such as drone wiring, in YAML. This repository then:

- **draws** them: wiring diagrams via [WireViz](https://github.com/wireviz/WireViz),
  plus a schematic drawing of each connector's mating face showing which wire
  colour goes in which cavity
- **checks** them: crossed serial lines, VCC shorted to GND, swapped I²C or
  CAN, wire too thick for the crimp contact, untwisted CAN pairs, and missing
  information needed to order
- **documents** them for building and ordering: a printable drawing with a
  title block, notes, pinouts, a from-to wire list, a BOM and a netlist for
  continuity testing

```yaml
metadata: {title: TELEM1 to SiK telemetry radio, pn: CBL-UAV-001, revision: A}
manufacturing: {ipc_class: 2, length_tolerance: ±5 mm}

connectors:
  FC:    {use: pixhawk.telem}              # Pixhawk DS-009 port: JST GH 6-way,
  RADIO: {use: pixhawk.telem_peripheral}   # housing + contact MPNs, pin names

cables:
  W1: {use: wire.ul1571_28awg, length: 150 mm, colors: [RD, BK, BK, BK, BK, BK]}

connections:
  - [FC: [1-6], W1: [1-6], RADIO: [1-6]]
```

## Usage

The tool needs Python 3.8 or newer and [Graphviz](https://graphviz.org/download/)
(`apt install graphviz` or `brew install graphviz`).

```sh
pip install -e .            # installs the `cables` command

cables check                # check every harness under harnesses/
cables check --strict FILE  # also fail on anything a manufacturer would ask about
cables build                # write outputs to build/; open build/index.html
cables library              # list library connectors and wires
cables library pixhawk      # show one library's pinouts and part numbers
cables clean
```

For each `harnesses/<group>/<name>.yml`, `cables build` writes these files to
`build/<group>/`:

| File | Contents |
|---|---|
| `<name>.html` | Manufacturing drawing: title block, diagram, notes, wire list, pinouts with a drawing of each connector face, BOM and check results. Prints on A3 landscape |
| `<name>.svg`, `.png` | Diagram |
| `<name>.wirelist.csv` | From-to list: wire, colour, gauge, length, from and to pins with signal names, twisted pairs |
| `<name>.netlist.csv` | Contacts per net, for continuity testing |
| `<name>.bom.csv`, `.bom.tsv` | BOM with quantities per assembly: housings, crimp contacts and wire length per colour |

CI runs the tests, checks every harness, and uploads `build/` as the
`cable-drawings` artifact.

## Layout

```
harnesses/         cable descriptions, one folder per group
  drone/           Pixhawk TELEM, GPS and CAN cables, battery lead
  generic/
library/           (optional) project-specific connectors; overrides built-ins
src/cables/        the tool; built-in library in src/cables/library/
docs/markup.md     markup reference: WireViz syntax + additions
docs/checks.md     check codes
docs/ordering.md   what to send to a cable manufacturer, standards, sources
```

## Status of the examples

- `harnesses/drone/*` use the pinouts from the Pixhawk Connector Standard
  DS-009 and pass `--strict`. Wire MPNs are not set, since they depend on
  your supplier.
- `harnesses/generic/moza_sony.yml` is a **draft**. Its connectivity is the
  WireViz tutorial example (RS-232 DE-9 to a 3-way Molex KK). Nobody has
  checked it against the Moza Slypod or Sony A7 III documentation.
