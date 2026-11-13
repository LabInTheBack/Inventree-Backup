# Warehouse and part entry

Workspace: `/home/den/server-data/inventree`. The live InvenTree database is
authoritative for identities, units, categories, stock, locations and mappings.
The [category/location index](inventree-category-locations.md) is a dated reference.
Use the [addon guide](wled-locator-plus.md) for locator development and the
[maintenance guide](inventree-maintenance.md) for infrastructure work.

## Working rules

- Perform only the requested task. Analysis/proposals are read-only. Inventory
  work does not authorize code, Docker, location-name or WLED mapping changes.
- Query relevant records instead of repeating a full audit. Reuse existing parts,
  companies, templates, choices and images; resolve live IDs before writing.
- Use supplied product information directly. Never infer specifications,
  manufacturer identity or compatibility from a similar item or its appearance.
- Present data for review when requested. Bulk keyword proposals need approval
  category by category. Preserve existing keywords unless removal is approved.
- Keep progress and completion messages concise; identify any remaining approved
  work. After creating a part, provide a short distinguishing item label.

## Entry workflow

1. Identify the exact part and check for duplicates. Use the actual part number as
   name/IPN when known; IPN matches the name unless instructed otherwise. Generic
   items use a concise functional name and useful specifications.
2. Select the actual component family, independently of physical storage. Keep
   bearings, rollers, couplings and rope hardware in their proper mechanical
   categories. Distinguish mechanical switches from magnetic reed devices.
3. Set a concise factual description, manufacturer/MPN and supplier/SPN when
   known. Reuse canonical companies such as `Onsemi`, `Diodes Inc`,
   `Murata Electronics` and `Vishay`; do not create equivalent division names.
4. Add only requested/relevant parameters, useful keywords and available media.
   Leave missing values unset. Record packaging/lifecycle only when supplied.
5. Enter the user's EUR price breaks, if provided. Add physical stock/location
   only when requested, preserving supplier relationships and existing quantities.
6. Verify identity, category, units, media, prices and links; check that unrelated
   records, names and mappings were preserved and no duplicates were created.

Keywords are short generic search terms/synonyms, without manufacturer/seller
names or redundant parametric values. Append without duplicates. Include `THT`
or `SMD` when applicable. Boards/modules need practical object and purpose words
such as `module`, `board`, `breakout`, `carrier`, `evaluation board` or
`sensor module`, even when those words appear in the description. Use generic
cable names with specifications, not an application/vehicle-specific name.

## Supplier sources, images and datasheets

- For DigiKey.de/.com links, use the corresponding DigiKey.com product page for
  identity and attributes, but retain the user's exact supplier URL in InvenTree.
  Use Mouser as the source/supplier when the user explicitly provides Mouser.
- Technical sources outside the supplied product data/page require an explicit
  request. Do not use mirrors, search snippets or similar parts to fill gaps.
- Use `SPN` for the supplier identifier, without a duplicate `DigiKey Part Number`
  field. Select the purchased packaging SKU, e.g. Cut Tape. Link the supplier part
  to the correct manufacturer part and inventory part only when identity is clear.
- Check local images for an exact match first. Every DigiKey source needs an
  exact product-image check on DigiKey.com; follow the page's exposed image URL
  (normally `mm.digikey.com`). Validate the downloaded image and set the visible
  part image; an attachment alone is insufficient.
- Image reuse requires matching package/construction. Modules require the exact
  board, not its bare IC. A family image is acceptable only if it includes the
  exact package variant; identify it as a family image in the attachment comment.
- Attach the file exposed by the supplier's `Datasheet` link. Do not open, parse
  or scan the PDF for technical values. A supplied manufacturer/product URL goes
  in `Part Details → Link`; attachments do not replace that field.
- Allow at most two quick image attempts and two quick datasheet attempts.
  Then continue without the missing asset. Do not guess URLs or search other
  sites for missing images/datasheets; the user can attach them manually.

## Prices and stock

- Use only user-provided quantity/unit-price breaks in EUR, preserving precision.
  Do not scrape prices, convert USD or infer missing price breaks.
- Never fetch or populate supplier availability, or reset an existing value to
  zero as cleanup. Supplier availability is separate from the user's local stock.
- Catalog creation does not imply physical stock creation. Add stock and change
  locations only when requested; never infer quantity. Ask for quantity only
  when stock creation requires it and it is missing.
- Treat a supplied quantity as additional stock unless explicitly stated to be a
  final total. For a bag/order, use the stated full package count unless the user
  specifies another count; an unknown package count remains unknown.
- Preserve `StockItem → SupplierPart → ManufacturerPart` links for purchased
  stock. Missing supplier links can make supplier-part local stock appear zero.

## Parameters and units

Use live category templates/choices as the field catalog. Full template lists are
not duplicated here; the following rules preserve distinctions important to entry.

- Keep useful distinct templates even if unused. Use `Height`, not deleted
  `Hight` or `Package (in)`. Keep `Voltage` and `Voltage Rating` distinct.
- Enter plain numeric values in the template's metric units, e.g.
  `Collector Current Max = 3` with unit `A`. Do not repeat units in values.
  Preserve source conditions separately, e.g. `I_B=375mA, I_C=3A`.
- Preserve typical/minimum/maximum/unqualified meaning. An unqualified value is
  not a maximum. Neutral fields include `Input Offset Voltage` (mV),
  `Input Bias Current` (nA), `Supply Current` (mA), `Quiescent Current` (uA),
  `Rise Time` and `Fall Time`; use qualified variants only when supported.
- Distinguish total, per-channel, operating and quiescent current.
  `Supply Current Typ` uses uA; `Supply Current Max` uses mA.
- Keep `uA`, `mOhm`, `kSPS`, `kVrms` and `dBA` semantics. Do not relabel units or
  recreate aliases merely to repair a numeric index; RMS and A-weighting matter.
- Reuse mounting choice `Module / Board`. `Module Type` supports `Sensor Module`;
  choose the applicable existing value without inventing duplicates.
- Keep category defaults small and relevant, with blank default values. Do not
  add broad Electronics/Sensors/Modules defaults, backfill empty part parameters,
  or create blank records unless requested. Text fields may retain source
  notation where no numeric template applies.

### Family-specific mappings

Apply only fields supported by the source and relevant to the item. Shared
mounting, package, supply and temperature fields come from live templates.

| Family | Distinctions and source mapping |
|---|---|
| BJT / arrays | Use `BJT Type` for NPN/PNP and `Configuration` for single/dual. Arrays stay in the polarity category unless asked otherwise. Keep hFE, saturation and transition-frequency test conditions; distinguish power at T_C and T_A. |
| MOSFET | Use `Channel Type` and `FET Technology`. `R_DS(on) Max` is in mOhm: 22 mOhm is `22`, not `0.022`. Preserve resistance, gate-threshold, gate-charge and input-capacitance conditions; distinguish T_C/T_A power. |
| Op amp | `Number of Circuits`, not an inferred package count. Convert GBW kHz→MHz, offset µV→mV, bias pA→nA and per-channel supply µA→mA. `Standard (General Purpose)` maps to `General Purpose`. Source output Rail-to-Rail means `Rail-to-Rail = Output` unless both sides are explicit. |
| Comparator | Response time ns→us; preserve offset, bias, response-time and current qualifiers/conditions. Apply op-amp unit conversions where the same templates are used. |
| Logic | A logic series such as 74AHC maps to `Logic Family`; explicit Schmitt Trigger features set `Schmitt Trigger`. Split high/low output currents and retain propagation-delay conditions. |
| Gate driver | Driven Configuration→`Gate Driver Configuration`; Gate Type→`Driven Device Type`; Number of Drivers→`Number of Circuits`. Split VIL/VIH and peak source/sink current. Typical rise/fall times use neutral fields with the qualifier retained. |
| ADC | Bits→`Resolution`; A/D Converters→`Number of Circuits`; Input Type→`Analog Input Type`; sampling rate→kSPS. Share supply-voltage fields when analog/digital ranges agree; separate them only when needed for selection. |
| Linear regulator | Output Type→`Regulator Output Type`; Output Configuration→`Output Polarity`. Fixed output uses `Output Voltage`; adjustable uses min/max. Quiescent current→uA with its qualifier; keep dropout conditions. |
| DC-DC converter IC | Use PMIC/DC-DC Converters, topology and output-polarity/type fields; switching frequency→kHz. Unqualified frequency uses a neutral field/notes, not invented min/max. Automotive qualification must be explicit. Use manufacturer values only when requested. |
| Power module | Use Modules/Power Modules for self-contained supplies. `Module Type` distinguishes isolated/non-isolated supplies, not breakout/evaluation boards. Output current→A and ordinary isolation voltage→kV. |
| Motor-driver IC | Use ICs/Motor Drivers. Map purpose→`Motor Driver Type`, motor type→`Motor Type`, Interface→`Data Interface`; fully integrated control/power stage→`Integrated Power Stage = true`. Preserve text step resolution such as `1/256`. |
| Motor-driver module | Use Modules/Motor Driver Modules for complete boards/carriers. Distinguish Haptic/Stepper/etc. with `Motor Driver Type`; exact IC→`Utilized IC`, ecosystem→`Module Platform`. Do not split subcategories or infer board ratings unnecessarily. |
| Battery charger | Use PMIC/Battery Chargers. Charge Current Max→`Output Current Max`; Battery Pack Voltage→`Output Voltage`; Supply Max→`Supply Voltage Max`; Current-Charging→`Charging Profile`; Fault Protection→`Protection Features`. Only real buses belong in `Data Interface`. |
| USB PD controller | Use PMIC/USB PD Controllers. Distinguish `USB Controller Type` and Sink/Source/DRP `USB PD Role`. Unqualified supply current→`Supply Current` in mA. Applications=USB does not establish a control interface. |
| Analog switch | Multiplexer/Demultiplexer Circuit→`Mux/Demux Ratio`. Split Ton/Toff; leakage→nA (100 pA→0.1). Preserve crosstalk test frequency. |
| I/O expander | Interface→`Data Interface`; clock→`Clock Frequency`. When explicitly shared, put the source/sink rating into both high/low output-current fields. Interrupt and internal pull-ups require explicit support. |
| Crystal / oscillator | Use Frequency Control/Crystals & Resonators or Oscillators. Shared `Frequency` is MHz; tolerance/stability are unsigned ppm magnitudes; dimensions→mm. Leave unknown load capacitance, ESR and stability unset. |
| Timer IC | Use ICs/Timers. Type→`Timer Type`; explicit Single/Dual→`Number of Circuits`; unqualified supply current→neutral mA field. Obsolete ICs are not purchaseable unless a purchasable supplier record is explicitly provided. |
| Photodiode / phototransistor | Use Sensors/Light Optical subcategories. Put typical/maximum meaning at the start of `Dark Current Conditions`. Photocurrent→mA (30 µA→0.03); retain irradiance/bias/wavelength conditions. Do not infer responsivity or maximum reverse voltage from typical breakdown. PD204-6C's recorded reverse-voltage correction is 32 V; 170 V was typical breakdown. |
| Optical timing | Use `Photo Response Time` for one generic response value, `Rise Time`/`Fall Time` only when separately supplied. Do not create `Orientation` solely for Top View. |
| Optocoupler | Use ICs/Isolation/Optocouplers. Keep DC/AC input type and actual output type. Explicit RMS isolation→`Isolation Rating` in kVrms (5000 Vrms→5); output current→A. Preserve CTR/saturation conditions; typical timings must not become maxima. |
| PIR sensor | Use Sensors/Motion Sensors/PIR Sensors. Sensitivity remains text; split field of view X/Y only when identified. No redundant generic Sensor Type; do not infer optics or package details from appearance. |
| Sensor lens | Use Sensors/Accessories/Sensor Lenses. Link only known compatible sensors; distinguish physical material/colour variants. Do not infer optical specifications. |
| Environmental sensor | Use Humidity, Temperature or Pressure as appropriate. Preserve current/range/accuracy conditions and template units, including %RH and kPa. I2C/SPI belong in `Data Interface`, not duplicate Output Type. Filter caps are accessories. |
| Sensor module | Modules/Sensor Modules is a grouping category, not a direct part category. Classify by primary function: Environmental, Motion, Optical & Proximity, or another relevant existing child. Keep bare sensors and housed/breakout assemblies separate; link only an exact known `Utilized IC`, without creating a bare IC solely for that link. |
| Generic cable | Use generic functional naming plus specifications. Store Length and Thickness/Cross Section as numeric values in the existing template's units; do not confuse diameter and cross-sectional area. |

PMIC groups Battery Chargers, Voltage Regulators, DC-DC Converters, Gate Drivers
and USB PD Controllers. Motor Drivers remain separate unless reorganized by
explicit request. A listed automotive grade such as AEC-Q100 is required before
setting `Automotive Qualified`.

## Physical storage and labels

- Preserve location names, drawer numbering and existing WLED mappings. Resolve
  `C1Dxx`/`C2Dxx` within the correct cabinet under `Berlin Home`; verify the actual
  row/drawer path. Printed labels are descriptions, not renamed database locations.
- Cabinet-01's former Drawer-44 was subdivided into Drawer-44–47. Preserve their
  intentional shared LED 147. Drawer-41–43 are larger than Drawer-01–40; check fit.
- S-Box storage has six shelves; Shelves 01–05 normally have seven Box locations each. Use an
  existing `OS-Obj` location for oversized items when appropriate; shelf LEDs may
  intentionally be shared. Managing shelves does not authorize cabinet remapping.
- Shelf-06 stores DIN rails directly on the shelf. It has no box subdivisions or
  LED mapping yet; it was created for nine `TS35/7.5-150` rail sections.
- Shelf-05 has seven stacks of two boxes: `Box-01A` through `Box-07A` are the
  lower boxes; matching `Box-01B` through `Box-07B` are directly above them.
  Each A/B pair shares the same controller and LED group. Always include the
  suffix when recording or reporting Shelf-05 storage. Other shelves retain
  their existing numbering. This scheme was implemented on 2026-11-12;
  existing Shelf-05 box IDs and contents were retained as A locations.
- Shelf-03 groups motors, pumps, solenoids and related actuators. Its `Box-05`
  is labelled `Solenoids & Valves`; the solenoid valve
  `TP-DD018B020F-024DC` was moved here from Shelf-05 `Box-04B`.
- Physical labels should be short, standardized and free of dot separators.
  Item label example: `D14L25-5x5`; broad box labels can be `Ball Bearing` or
  `Shaft Collar & Coupling`. Check current contents/capacity before placement;
  physical box labels and part default locations can differ from on-hand stock.

The sensor placement plan uses these cabinet-wide drawer references; resolve
them against current row-based location paths before use:

| Cabinet-02 drawers | Planned contents |
|---|---|
| 27 / 28 / 29 | THT optical detectors / SMD photodiodes and IR receivers / IR LEDs. |
| 30 / 31 / 32 | PIR sensors and lenses / position, proximity and touch / piezoelectric transducers. |
| 33 / 34 / 35 | Environmental components / environmental modules / motion modules. |
| 36 / 37 | Optical/proximity modules / audio modules. |

Historical observations about Prusa CHT `obxidian` keywords, mixed SDHC/SDXC terms
and uncertain breadboard-PSU branding do not authorize cleanup. Resolve identity
and get approval before removing those existing keywords.

## Direct database work

Use the running container without restarting for routine entry:

```bash
cd /home/den/server-data/inventree
docker compose exec -T -w /home/inventree/src/backend/InvenTree \
  inventree-server python3 -B manage.py shell
```

Relevant models are Part, PartCategory and PartCategoryParameterTemplate
(`part.models`); Parameter/ParameterTemplate (`common.models`);
Company/ManufacturerPart/SupplierPart/SupplierPriceBreak (`company.models`);
StockItem/StockLocation (`stock.models`). Parameters use a generic relation:
filter by Part content type (`app_label="part", model="part"`) and `model_id`.
Inspect current fields/units before writes, use transactions for related changes,
and verify only intended fields changed. Audits use a read-only transaction;
never print secrets or rely on IDs copied from historical notes.
