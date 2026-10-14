# Markup reference

A harness file is a [WireViz](https://github.com/wireviz/WireViz) YAML file
(WireViz 0.4 syntax) with a few optional additions. Any valid WireViz file is
a valid harness file, so the [WireViz syntax description](https://github.com/wireviz/WireViz/blob/v0.4.1/docs/syntax.md)
applies in full. This page covers the parts you use most and everything this
project adds.

```yaml
metadata:            # WireViz: free-form; these keys are used in the drawing
  title: TELEM1 to SiK telemetry radio
  pn: CBL-UAV-001    # your part number for the assembly
  revision: A
  date: 2026-10-14
  author: Gadgetmies
  description: 6-way JST GH, 1:1, 150 mm.

manufacturing:       # added by this project, see below
  ipc_class: 2
  length_tolerance: ±5 mm

connectors:
  FC:
    use: pixhawk.telem           # added: start from a library entry
    notes: Autopilot TELEM1      # any WireViz connector attribute overrides it
  RADIO:
    use: pixhawk.telem_peripheral

cables:
  W1:
    use: wire.ul1571_28awg
    length: 150 mm
    colors: [RD, BK, BK, BK, BK, BK]

connections:
  - - FC: [1-6]       # pins (numbers or pin labels), ranges allowed
    - W1: [1-6]       # wires
    - RADIO: [1-6]
```

## Connectors

The WireViz attributes that matter most for documentation and ordering:

| Attribute | Meaning |
|---|---|
| `type`, `subtype` | Family and variant, e.g. `JST GH`, `1.25 mm pitch, female housing` |
| `manufacturer`, `mpn` | Manufacturer and its part number. Needed for ordering |
| `supplier`, `spn` | Distributor and its part number (optional) |
| `pn` | Your own internal part number (optional) |
| `pincount`, `pins` | Number of positions, or explicit pin names when not 1..n |
| `pinlabels` | Signal name on each pin, in pin order. The checks read these |
| `pincolors` | Colour markers per pin (optional) |
| `loops` | Jumpers inside the connector, e.g. `[[1, 2]]` |
| `additional_components` | Crimp contacts, backshells, seals. Use `qty_multiplier: populated` for one contact per used pin |
| `style: simple` | A one-pin item such as a ferrule, ring terminal or tinned end |
| `notes`, `image` | Free text and a picture in the diagram |

Additions:

| Attribute | Meaning |
|---|---|
| `use: library.entry` | Start from a library entry. Your own attributes override it, and lists are replaced, not merged |
| `wire_awg: [30, 26]` | The wire range the contacts accept, in AWG, either order. Wires outside it fail check `G001`. Library entries set it from the contact datasheet |
| `source` | Where the pinout comes from. Shown under the pinout table. Library entries fill it in |

## Cables and wires

| Attribute | Meaning |
|---|---|
| `wirecount` + `color_code` or `colors` | Number of wires and their colours. `color_code` is one of `DIN` (DIN 47100), `IEC` (resistor colour-code order, starting at brown), `TEL`, `TELALT`, `T568A`, `T568B`, `BW` |
| `colors` | Colours per wire as IEC 60757 two-letter codes: `BK BN RD OG YE GN BU VT GY WH PK TQ`. Stripes are concatenated: `WHBU` is white with a blue stripe |
| `gauge` | `28 AWG` or `0.25 mm2`. Add `show_equiv: true` to print the other unit in the diagram |
| `length` | `150 mm`, `0.2 m` or a number in metres |
| `category: bundle` | Loose wires without a common jacket. Each wire is a separate BOM line |
| `shield: true` | Adds a shield wire `s` you can connect like any other wire |
| `type`, `manufacturer`, `mpn` | Wire or cable specification, e.g. `UL1007` or a multicore cable part number |
| `wirelabels` | A name per wire (optional) |

Additions:

| Attribute | Meaning |
|---|---|
| `use: library.entry` | As for connectors. The `wire` library sets type and gauge |
| `twisted: [[2, 3]]` | Wire pairs to twist together. Shown in the wire list and notes. Check `T002` asks for it on CAN and USB pairs |
| `source` | As for connectors |

## Connections

Each connection set alternates connector, cable, connector, ..., and every
entry lists the same number of pins or wires. Ranges like `1-6` expand, and
`[1, 3, 2]` crosses wires. You can start or end on a cable to leave a flying
lead. A connector name with a dot creates an instance from a template: `F.`
creates a new auto-named ferrule for every wire, and `X.left` creates an
instance named `left`. WireViz also supports arrows (`-->`, `==>`) for mated
connectors. The netlist and checks treat mated contacts as connected.

## The `manufacturing` section

Everything here goes into the drawing notes and the title block.

| Key | Example | Notes |
|---|---|---|
| `ipc_class` | `2` | IPC/WHMA-A-620 product class: 1 general, 2 dedicated service, 3 high performance or harsh environment |
| `length_tolerance` | `±5 mm`, `+10/-0 mm` | Without it, the manufacturer applies its own default |
| `length_reference` | `from the XT60 rear face to the wire end` | Default: connector mating face to connector mating face |
| `twist_rate` | `approx. 1 twist per 10 mm` | Used with `twisted` pairs |
| `tests` | `[100% continuity and short test against the netlist]` | Test requirements |
| `labels` | `[Heat-shrink label "CAN" 20 mm from each connector]` | Marking requirements |
| `compliance` | `[RoHS, REACH]` | Material compliance |
| `notes` | `[Strip 5 mm and pre-tin]` | Anything else, one note per item |
| `ignore` | `[M004]` | Check codes to skip for this harness |

## Libraries

`use: pixhawk.telem` looks for `pixhawk.yml` in these places, in order:

1. directories given with `--library DIR`
2. a `library/` folder next to the harness file, or in any parent folder
3. the built-in library in `src/cables/library/`

Your project's own `library/` folder therefore overrides a built-in library
with the same name. A library file looks like this:

```yaml
library: mylib
description: Connectors used on the Foo airframe
source: Foo ICD rev C            # shown as the pinout source

connectors:
  base:                          # an entry can use another entry,
    type: JST GH                 # in the same library or another one
    wire_awg: [30, 26]
  servo:
    use: jst.gh3
    pinlabels: [SIG, VCC, GND]

cables:
  servo_wire: {type: Silicone, gauge: 26 AWG, category: bundle}
```

Run `cables library` to list every entry and `cables library pixhawk` to show
the details of one library.

### Built-in libraries

| Library | Contents |
|---|---|
| `pixhawk` | Pixhawk Connector Standard DS-009 ports: `telem`, `gps_full`, `gps_basic` (with `*_peripheral` variants), `can`, `i2c`, `spi`, `power_analog`, `debug_full`, `debug_mini` |
| `jst` | JST GH `gh2`..`gh15` and SH `sh2`..`sh15` housings, with their crimp contacts and wire ranges |
| `molex` | Molex KK 254 `kk254_2`..`kk254_6` with crimp terminals |
| `power` | Amass `xt30`, `xt60`, `xt90`, each as `_male` or `_female` |
| `dsub` | DE-9 male and female, and RS-232 DTE pinouts |
| `wire` | UL1571, UL1007 and UL10064 hook-up wire, and silicone wire from 10 to 30 AWG |

The Pixhawk standard wires serial cables 1:1 and crosses TX/RX on the
peripheral's board. The autopilot entries (`telem`) use the autopilot's pin
names. The peripheral entries (`telem_peripheral`) use the peripheral's pin
names, so connecting the right pair gives TX→RX. Connecting two autopilot
ports by mistake fails check `S010`.
