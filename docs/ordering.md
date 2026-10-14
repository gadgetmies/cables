# Ordering cables from a manufacturer

This page explains what cable assembly houses ask for, which standards they
quote against, and how the outputs of `cables build` map to an RFQ (request
for quote) package.

## What goes into an RFQ package

Assembly houses publish similar checklists: a dimensioned drawing, a BOM
with manufacturer part numbers, a from-to wire list, wire specifications,
and test, labelling and compliance requirements. They warn that a generic
description such as "4-pin connector" cannot be quoted, and that tight
tolerances on non-critical lengths raise cost.

| Item | Why it is needed | Where it comes from |
|---|---|---|
| Assembly part number and revision | Traceability. Every reorder refers to it | `metadata.pn`, `metadata.revision` (check M001) |
| Drawing with item callouts | Shows what is built | `<name>.html`: diagram, title block and notes. Print it to PDF (A3 landscape) |
| BOM with manufacturer part numbers | Lets the manufacturer buy exactly your parts | `<name>.bom.csv`. Housings, contacts and wire, with quantities per assembly (check M004) |
| From-to wire list | The manufacturer builds and tests from it | `<name>.wirelist.csv`: wire, colour, gauge, length, from pin and to pin, with signal names |
| Netlist | Programs the continuity tester | `<name>.netlist.csv`: one row per net with every contact in it |
| Wire specification | Gauge, insulation (UL style), colour | Cable `type`, `gauge`, `colors`, `mpn` (checks G002, M006, M007) |
| Lengths and tolerances, and where lengths are measured | Avoids disputes over "too short" | Cable `length`, `manufacturing.length_tolerance`, `length_reference` (checks M003, M005) |
| Workmanship standard and class | Defines what counts as a good crimp or solder joint | `manufacturing.ipc_class` (check M002) |
| Twisting, labels, tests, compliance | Requirements that are not visible in a schematic | `manufacturing.twist_rate`, `labels`, `tests`, `compliance`, `notes` |
| Quantity and lead time | Price breaks | Put these in the RFQ email, not in the drawing |

Before you send it out:

```sh
cables check --strict harnesses/drone/telem_sik_radio.yml
cables build harnesses/drone/telem_sik_radio.yml
```

Then send the drawing as a PDF together with the CSV files.

## Standards worth naming

- **IPC/WHMA-A-620**, Requirements and Acceptance for Cable and Wire Harness
  Assemblies. Most assembly houses build and inspect to it. Name it with a
  product class:
  - **Class 1**, general electronic products.
  - **Class 2**, dedicated service. A reasonable default for hobby and
    commercial drones.
  - **Class 3**, high performance or harsh environment.

  Higher classes cost more and need more inspection. The standard also has a
  default cable length tolerance table. If you leave `length_tolerance` out,
  the manufacturer will apply that table or its own house rule (check M003).
  Revisions of the standard are not listed here; ask the manufacturer which
  revision they build to.
- **Wire sizes**: AWG per ASTM B258, metric cross sections per IEC 60228.
  `cables` converts between them with the ASTM formula (see
  `src/cables/gauge.py`). Contact datasheets usually give AWG ranges.
- **Wire insulation**: name a UL AWM style (e.g. UL1007, UL1571, UL10064)
  or an MPN. Silicone "high-strand" wire usually has no UL style, so name the
  supplier's part number instead.
- **Colours**: WireViz uses IEC 60757 two-letter colour codes (`RD`, `BK`,
  `WHBU`, ...). The `DIN` colour code is DIN 47100. Ethernet uses TIA-568
  (`T568A` and `T568B`).
- **Connector pinouts**: for UAV avionics, the **Pixhawk Connector Standard
  (DS-009)**. It uses JST GH 1.25 mm for peripheral ports and JST SH 1.0 mm
  for debug, puts a red wire on pin 1 and black on the others, and wires
  serial cables 1:1 with the peripheral crossing TX/RX. It also asks for
  twisted CAN wires. All of this is encoded in the `pixhawk` library and the
  checks. Vendors do not always follow it; one module's documentation, for
  example, swaps TX and RX against the standard. Always compare with the
  datasheet of the actual device.
- **RoHS and REACH**: list them in `manufacturing.compliance` if you need
  them.

## Workflow

1. Describe the cable in YAML, using library parts where possible.
2. Run `cables check`. Fix errors and review warnings.
3. Build one by hand, or order a prototype, using the HTML drawing and wire
   list.
4. Fill in what is missing for ordering: MPNs, tolerance and IPC class. Run
   `cables check --strict` until it is clean.
5. Bump `metadata.revision` for every change after the first order.

## Other tools

- **WireViz** draws the diagrams and BOM, and its YAML syntax is the
  foundation of this project. It does not check signals, wire ranges or
  manufacturing completeness, and it does not output a wire list or netlist
  (this project adds those).
- **Commercial harness CAD** (e.g. Zuken E3.series, Capital Harness, Harness
  Expert, RapidHarness) covers the full flow including formboards. These
  tools are much heavier than needed for small drone cables.
- **KiCad** can draw cables as schematics, but has no harness BOM or wire
  list.

## Sources

- [Pixhawk Connector Standard DS-009](https://github.com/pixhawk/Pixhawk-Standards)
- [Epec: Best practices for custom cable assembly drawings](https://www.epectec.com/articles/best-practice-custom-cable-assembly-drawing.html)
- [Epec: What to specify in a BOM for cable assembly manufacturing](https://blog.epectec.com/what-to-specify-in-a-bom-needed-for-cable-assembly-manufacturing)
- [TeleWire: Custom cable assembly design checklist](https://www.telewiretech.com/blogs/technical-resources/the-ultimate-custom-cable-assembly-design-checklist)
- [TeleWire: Best practices for cable assembly drawings](https://www.telewiretech.com/blogs/technical-resources/best-practices-for-creating-custom-cable-assembly-drawings)
- [East West Manufacturing RFQ checklist](https://info.ewmfg.com/hubfs/East_West_Manufacturing_RFQ_Checklist.pdf)
- [Assembly Magazine: IPC/WHMA-A-620 gets an update](https://www.assemblymag.com/articles/93783-ipc-whma-a-620-gets-an-update)
- [JST GH contact SSHL-002T-P0.2 (30–26 AWG), distributor listing](https://www.ac-solutions.be/de/produkte/gh-sshl-002t-p0-2/jld9K)
- [JST SH contact SSH-003T-P0.2 (32–28 AWG), Future Electronics](https://futureelectronics.com/p/interconnect--pin-and-socket-connectors--crimp-terminals/ssh-003t-p0-2-jst-1062067)
- [ARK Electronics: connectors and wiring](https://docs.arkelectron.com/knowledge-base/knowledge-base/connectors-and-wiring)
- [WireViz](https://github.com/wireviz/WireViz)
