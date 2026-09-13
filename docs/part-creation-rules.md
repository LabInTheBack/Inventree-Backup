# InvenTree Part Creation Rules

Use this checklist before creating or updating parts in InvenTree.

## Scope And Efficiency

- For a new conversation, read `docs/inventree-handoff.md` and this file's core rules, then only the relevant component-family section.
- The live database is authoritative for existing parts, templates, companies and locations. Query the relevant records; do not dump or audit the whole database for routine entry.
- Only perform the requested database task. Do not change code, plugins, Docker configuration or WLED mappings without explicit authorization.
- A request for analysis or a proposal is read-only. Present proposed keyword additions category-wise for approval before a bulk update.
- Preserve existing keywords unless removal is explicitly approved; append useful factual synonyms without duplicate tokens or phrases.
- Never infer electrical specifications, manufacturer identity or compatibility from a similar part or package.
- Keep updates and final responses concise. After each task, list remaining approved TODOs, or state that none remain.

## Source Rules

- When the user provides a DigiKey.de or DigiKey.com link, use the corresponding DigiKey.com product page as the source for all part identity, manufacturer, supplier-part, description, lifecycle, packaging, and parameter data.
- Keep the exact supplier URL provided by the user as the InvenTree supplier link, even when the corresponding DigiKey.com page is used for analysis.
- When the user explicitly provides a Mouser link instead, use that Mouser product page as the supplier source.
- Do not supplement supplier data with manufacturer sites, distributor mirrors, or general web searches unless the user explicitly asks.
- Copy the file directly from the supplier page's `Datasheet` link into the corresponding part's `Attachments`.
- Do not open, parse, scan, or extract technical values from the datasheet. The supplier product page is the source for entered attributes.
- If the supplier has no datasheet link or the linked file cannot be retrieved within two quick attempts, leave the datasheet unattached. The user will attach it manually.
- Every provided DigiKey.de or DigiKey.com part link requires an exact DigiKey product-image check.
- For image retrieval, use the corresponding DigiKey.com product page even when the provided supplier link uses DigiKey.de.
- Follow the product image linked by DigiKey, normally hosted on `mm.digikey.com`; do not use a search-engine result or an unrelated distributor image.
- Make at most two quick DigiKey image-retrieval attempts. If the exact image remains inaccessible, skip it without guessed URLs, alternate sites, or additional searches.
- Make at most two quick retrieval attempts for the supplier-linked datasheet. If it remains inaccessible, skip it.
- Do not invent missing values.
- Do not use distributor mirrors or unrelated third-party pages to fill missing technical values.
- Do not fill fields the user did not ask for.
- If a required value is missing, leave it blank instead of guessing.
- Before creating the part, present the extracted data for review when requested.

## Core Part Fields

- Part name should be the actual part number.
- IPN must match the part name / part number unless explicitly told otherwise.
- Description should be concise and taken from the supplier page.
- Category must match the actual component family.
- Add useful keywords, but keep them factual and concise. Always reuse the existing ones.
- For modules and boards, include practical finder keywords for the physical object and purpose.
  - Examples: `module`, `board`, `eval`, `evaluation board`, `breakout`, `carrier`, `power module`, `sensor module`, `display module`.
  - Include these even if similar words already appear in the description, because keyword search should work independently of fields shown in the table.
- Check existing InvenTree images for an exact product image before downloading another copy.
- For every part created from a DigiKey link, copy the exact DigiKey product image when it is accessible.
- A DigiKey.de link must be mapped to the corresponding DigiKey.com product page for the image check while the provided DigiKey.de URL remains the supplier link.
- Download the exact image URL exposed by the DigiKey product page, normally from `mm.digikey.com`.
- Validate that the response is an actual decodable image before saving it.
- Reuse an existing package or product-family image only when the package and visible construction match.
- For modules and evaluation boards, reuse an image only for the exact board, not merely the same utilized IC or a similar board.
- Set the visible part image field; adding only an image attachment is not sufficient.
- Attach the exact file exposed by the supplier page's `Datasheet` field without inspecting or parsing its contents.
- Put the manufacturer/product page in `Part Details -> Link` when the user provides one.
- Do not use an attachment as a substitute for the part link field.

## Manufacturer And Supplier

- Manufacturer must be the real manufacturer from the supplier page. (If possible use provided supplier list in Inventree)
- Check for existing equivalent manufacturer names before creating a new company.
  - Example: `Diodes Inc` and `Diodes Incorporated` should not both exist.
  - Example: Murata divisions should use the existing consolidated `Murata Electronics` manufacturer.
  - Existing canonical names also include `Onsemi`, `Diodes Inc`, and `Vishay`; reuse the appropriate record instead of recreating supplier division names.
- Manufacturer part number must be the actual MPN.
- Supplier should be `DigiKey` for DigiKey pages.
- Supplier should be `Mouser` only when the user explicitly provides a Mouser product link.
- Use only `SPN` for the supplier part number.
- Do not create both `DigiKey Part Number` and `SPN`; they are the same supplier-part identifier.
- Supplier link should point to the exact supplier product page.
- If multiple DigiKey SKUs exist and the user says they bought Cut Tape, use the Cut Tape SPN.
- Link the supplier part to the matching manufacturer-part record as well as the inventory part. Check actual identity; do not guess ambiguous links.

## Parameters

- Reuse existing templates and choices before creating anything. Keep unused templates when they describe a useful, distinct property.
- Use metric units and the current template's units. Do not recreate deleted `Hight` or `Package (in)` templates; use `Height` where appropriate.
- Keep `Voltage` and `Voltage Rating` distinct. Keep ordinary isolation voltage and RMS `Isolation Rating` distinct.
- Preserve typical, maximum, minimum and unspecified qualifiers. A listed value without a qualifier must not become a maximum by assumption.
- Available neutral templates include `Input Offset Voltage` (mV), `Input Bias Current` (nA), `Supply Current` (mA), and `Quiescent Current` (uA). Use their maximum variants only for explicitly maximum values, and preserve conditions/qualifiers in notes.
- `Supply Current Typ` uses uA; `Supply Current Max` uses mA. Never confuse total, per-channel, quiescent and operating supply current.
- Use `uA` consistently for microamp unit labels. Existing custom units support `mOhm`, `kSPS`, `kVrms` and `dBA`; do not recreate aliases or change labels merely to repair a numeric index.
- Use the existing mounting choice `Module / Board`, not `Module/Board`. `Module Type` supports `Sensor Module`.
- Category defaults now provide small core sets at relevant category levels. Leave default values blank, do not add broad Electronics/Sensors/Modules defaults, and do not backfill existing parts with empty parameter records.
- Only use parameters relevant to the part category.
- Do not create unnecessary extra parameters just because the supplier page lists extra attributes.
- Never put units into a parameter value when the parameter template already has units.
  - Correct: `Collector Current Max = 3` with unit `A`
  - Wrong: `Collector Current Max = 3 A` with unit `A`
- Keep original context in condition parameters, not in numeric parameters.
  - Correct: `V_CE(sat) Max = 1.2`, `V_CE(sat) Conditions = I_B=375mA, I_C=3A`
- Numeric parameters should contain plain numeric values for filtering.
- Text parameters may keep supplier notation when no numeric template exists.
- Do not create blank parameter records unless explicitly requested.
- Use category-specific type names when they avoid ambiguity.
  - Use `BJT Type` for BJT polarity/type values such as `NPN` and `PNP`.
  - Use `Channel Type` for MOSFET channel values such as `N-Channel` and `P-Channel`.

## BJT Parameters

Use these BJT parameters when the DigiKey page provides values:

- `BJT Type`
- `Configuration`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Collector-Emitter Voltage Max` (`V`)
- `Collector Current Max` (`A`)
- `Power Dissipation @ T_C` (`W`)
- `Power Dissipation @ T_A` (`W`)
- `hFE Min`
- `hFE Conditions`
- `V_CE(sat) Max` (`V`)
- `V_CE(sat) Conditions`
- `V_BE(sat) Max` (`V`)
- `V_BE(sat) Conditions`
- `Transition Frequency` (`MHz`)
- `Transition Frequency Conditions`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

## MOSFET Parameters

Use these MOSFET parameters when the DigiKey page provides values:

- `FET Technology`
- `Channel Type`
- `Configuration`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Drain-Source Voltage Max` (`V`)
- `Drain Current Max` (`A`)
- `R_DS(on) Max` (`mOhm`)
- `R_DS(on) Conditions`
- `Gate Threshold Voltage Max` (`V`)
- `Gate Threshold Conditions`
- `Gate-Source Voltage Max` (`V`)
- `Total Gate Charge` (`nC`)
- `Total Gate Charge Conditions`
- `Input Capacitance` (`pF`)
- `Input Capacitance Conditions`
- `Drive Voltage`
- `Power Dissipation @ T_C` (`W`)
- `Power Dissipation @ T_A` (`W`)
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For `R_DS(on) Max`, store milliohms only.

- Correct: `R_DS(on) Max = 22` with unit `mOhm`
- Wrong: `R_DS(on) Max = 0.022` with unit `mOhm`

## Op Amp Parameters

Use these Op Amp parameters when the DigiKey page provides values:

- `Amplifier Type`
- `Number of Circuits`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Gain Bandwidth Product` (`MHz`)
- `Slew Rate` (`V/us`)
- `Input Offset Voltage` (`mV`), or `Input Offset Voltage Max` if explicitly maximum
- `Input Bias Current` (`nA`), or `Input Bias Current Max` if explicitly maximum
- `Supply Current per Channel` (`mA`)
- `Output Current per Channel` (`mA`)
- `Rail-to-Rail`
- `Input Type`
- `CMRR Min` (`dB`)
- `PSRR Min` (`dB`)
- `Input Voltage Noise Density` (`nV/sqrtHz`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Op Amp value conversions:

- Convert `kHz` to `MHz` for `Gain Bandwidth Product`.
  - Example: `700 kHz` -> `0.7`
- Convert `µV` to `mV` for the appropriate input-offset template.
  - Example: `150 µV` -> `0.15`
- Convert `µA` to `mA` for `Supply Current per Channel`.
  - Example: `500µA` -> `0.5`
- Convert `pA` to `nA` for the appropriate input-bias template.
  - Example: `1 pA` -> `0.001`
- Map `Standard (General Purpose)` to `Amplifier Type = General Purpose`.
- Map DigiKey `Output Type = Rail-to-Rail` to `Rail-to-Rail = Output` unless the page explicitly says input and output.

## Comparator Parameters

Use these Comparator parameters when the DigiKey page provides values:

- `Comparator Type`
- `Output Type`
- `Input Offset Voltage Max` (`mV`)
- `Input Offset Voltage Conditions`
- `Input Bias Current Max` (`nA`)
- `Input Bias Current Conditions`
- `Response Time Max` (`us`)
- `Response Time Conditions`
- `Hysteresis Voltage` (`mV`)
- `Number of Circuits`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Supply Current per Channel` (`mA`)
- `Output Current per Channel` (`mA`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Comparator value conversions:

- Convert `ns` to `us` for `Response Time Max`.
  - Example: `80 ns` -> `0.08`
- Convert offset, bias, supply current, and output current into the template units exactly as for Op Amps.
- Store test details in condition parameters instead of numeric value parameters.

## Logic Parameters

Use these Logic parameters when the DigiKey page provides values:

- `Logic Family`
- `Logic Type`
- `Number of Circuits`
- `Number of Inputs`
- `Schmitt Trigger`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Quiescent Current Max` (`uA`)
- `Output Current High Max` (`mA`)
- `Output Current Low Max` (`mA`)
- `Propagation Delay Max` (`ns`)
- `Propagation Delay Conditions`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Logic value mapping:

- Map DigiKey `Series` to `Logic Family` when it is a logic family such as `74AHC` or `74LVC`.
- Map DigiKey `Features = Schmitt Trigger` to `Schmitt Trigger = true`.
- Split `Current - Output High, Low` into `Output Current High Max` and `Output Current Low Max`.
- Store propagation-delay test details in `Propagation Delay Conditions`.

## Gate Driver Parameters

Use these Gate Driver parameters when the DigiKey page provides values:

- `Gate Driver Configuration`
- `Driven Device Type`
- `Number of Circuits`
- `Input Polarity`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Input Low Voltage Max` (`V`)
- `Input High Voltage Min` (`V`)
- `Peak Source Current Max` (`A`)
- `Peak Sink Current Max` (`A`)
- `Rise Time` (`ns`), or `Rise Time Max` if explicitly maximum
- `Fall Time` (`ns`), or `Fall Time Max` if explicitly maximum
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Gate Driver value mapping:

- Map DigiKey `Driven Configuration` to `Gate Driver Configuration`.
- Map DigiKey `Gate Type` to `Driven Device Type`.
- Map DigiKey `Number of Drivers` to `Number of Circuits`.
- Split `Logic Voltage - VIL, VIH` into `Input Low Voltage Max` and `Input High Voltage Min`.
- Split `Current - Peak Output (Source, Sink)` into `Peak Source Current Max` and `Peak Sink Current Max`.
- Split typical `Rise / Fall Time` into neutral `Rise Time` and `Fall Time`, noting `Typical`. Use maximum templates only when explicitly maximum.

## ADC Parameters

Use these ADC parameters when the DigiKey page provides values:

- `Resolution` (`bit`)
- `ADC Architecture`
- `Number of Circuits`
- `Number of Inputs`
- `Sampling Rate Max` (`kSPS`)
- `Reference Type`
- `Analog Input Type`
- `Data Interface`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For ADC value mapping:

- Map DigiKey `Number of A/D Converters` to `Number of Circuits`.
- Map DigiKey `Number of Bits` to `Resolution`.
- Map DigiKey `Architecture` to `ADC Architecture`.
- Map DigiKey `Input Type` to `Analog Input Type`.
- Convert sampling rate to `kSPS`.
  - Example: `100k` samples per second -> `100`
- Use shared `Supply Voltage Min` and `Supply Voltage Max` when analog and digital supply ranges are the same.
- Do not create separate analog/digital supply voltage parameters unless the part needs them for selection.

## Linear Regulator Parameters

Use these Linear Regulator parameters when the DigiKey page provides values:

- `Regulator Output Type`
- `Output Polarity`
- `Configuration`
- `Input Voltage Max` (`V`)
- `Output Voltage` (`V`)
- `Output Voltage Min` (`V`)
- `Output Voltage Max` (`V`)
- `Output Current Max` (`A`)
- `Dropout Voltage Max` (`V`)
- `Dropout Voltage Conditions`
- `Quiescent Current` (`uA`), or `Quiescent Current Max` if explicitly maximum
- `PSRR Min` (`dB`)
- `Power Dissipation @ T_C` (`W`)
- `Power Dissipation @ T_A` (`W`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Linear Regulator value mapping:

- Map DigiKey `Output Type` to `Regulator Output Type`.
- Map DigiKey `Output Configuration` to `Output Polarity`.
- Map DigiKey `Number of Regulators` to `Configuration` when useful.
- For fixed regulators, use `Output Voltage`.
- For adjustable regulators, use `Output Voltage Min` and `Output Voltage Max`.
- Convert quiescent current to `uA`; use neutral `Quiescent Current` unless explicitly maximum.
- Store dropout test details in `Dropout Voltage Conditions`.

## DC-DC Converter IC Parameters

Use these DC-DC Converter IC parameters under `Electronics / ICs / Power Management (PMIC) / DC-DC Converters` when the DigiKey page or provided manufacturer page gives values:

- `Converter Topology`
- `Regulator Output Type`
- `Output Polarity`
- `Configuration`
- `Input Voltage Min` (`V`)
- `Input Voltage Max` (`V`)
- `Output Voltage` (`V`)
- `Output Voltage Min` (`V`)
- `Output Voltage Max` (`V`)
- `Output Current Max` (`A`)
- `Switching Frequency Min` (`kHz`)
- `Switching Frequency Max` (`kHz`)
- `Synchronous Rectifier`
- `Quiescent Current Max` (`uA`)
- `Automotive Qualified`
- `Power Dissipation @ T_A` (`W`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For DC-DC Converter IC value mapping:

- Use manufacturer pages for technical values only when the user explicitly asks for them or DigiKey omits key selection data.
- Map topology terms such as buck, boost, buck-boost, flyback, SEPIC, charge pump directly to `Converter Topology`.
- Convert switching frequency to `kHz`.
- Set `Automotive Qualified` only when explicitly listed.

## Power Module Parameters

Use these Power Module parameters for self-contained power modules under `Electronics / Modules / Power Modules`:

- `Module Type`
- `Input Voltage Min` (`V`)
- `Input Voltage Max` (`V`)
- `Output Voltage` (`V`)
- `Output Current Max` (`A`)
- `Output Power` (`W`)
- `Isolation Voltage` (`kV`)
- `Efficiency` (`%`)
- `Number of Outputs`
- `Mounting Type`
- `Package / Case`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Power Module value mapping:

- Use `Module Type` for values such as `Isolated Module` and `Non-Isolated Module`.
- Do not reuse `Module Type` for evaluation boards, breakout boards, or carrier boards.
- Convert output current to `A`.
- Convert isolation voltage to `kV`.

## Motor Driver IC Parameters

Use these Motor Driver IC parameters for IC packages under `Electronics / ICs / Motor Drivers`:

- `Motor Driver Type`
- `Motor Type`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Load Voltage Min` (`V`)
- `Load Voltage Max` (`V`)
- `Output Current Max` (`A`)
- `Output Configuration`
- `Integrated Power Stage`
- `Data Interface`
- `Step Resolution Max`
- `Automotive Qualified`
- `Power Dissipation @ T_A` (`W`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Motor Driver IC value mapping:

- Map DigiKey `Applications` or motor-driver purpose to `Motor Driver Type` when it clearly identifies the class.
  - Examples: `Haptic Feedback` -> `Haptic`, stepper drivers -> `Stepper`.
- Map DigiKey `Motor Type - AC, DC` or `Motor Type - Stepper` to `Motor Type`.
- Map DigiKey `Function = Driver - Fully Integrated, Control and Power Stage` to `Integrated Power Stage = true`.
- Map DigiKey `Interface` to `Data Interface`.
- Use text for `Step Resolution Max` so values such as `1/256` are preserved clearly.
- Keep ICs and modules separate: motor-driver IC packages go under `Electronics / ICs / Motor Drivers`.

## PMIC Category Rules

Use `Electronics / ICs / Power Management (PMIC)` as the grouping category for power-management ICs.

Place these under PMIC:

- `Battery Chargers`
- `Voltage Regulators`
- `DC-DC Converters`
- `Gate Drivers`
- `USB PD Controllers`

Keep these outside PMIC unless explicitly reorganized later:

- `Motor Drivers`

## Battery Charger Parameters

Use these Battery Charger parameters under `Electronics / ICs / Power Management (PMIC) / Battery Chargers`:

- `Battery Chemistry`
- `Number of Cells`
- `Output Current Max` (`A`)
- `Output Voltage` (`V`)
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Data Interface`
- `Charging Profile`
- `Programmable Features`
- `Protection Features`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Battery Charger value mapping:

- Reuse `Output Current Max` for DigiKey `Charge Current - Max`.
- Reuse `Output Voltage` for DigiKey `Battery Pack Voltage`.
- Reuse `Supply Voltage Max` for DigiKey `Voltage - Supply (Max)`.
- Use `Data Interface` only when DigiKey lists a real interface, such as `USB`, `I2C`, or `SPI`.
- Map DigiKey `Current - Charging` to `Charging Profile`.
- Map DigiKey `Programmable Features` directly when listed.
- Map DigiKey `Fault Protection` to `Protection Features`.
- Do not create separate charger current or charger voltage parameters unless the shared fields become ambiguous in practice.

## USB PD Controller Parameters

Use these USB PD Controller parameters under `Electronics / ICs / Power Management (PMIC) / USB PD Controllers`:

- `USB Controller Type`
- `USB PD Role`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Supply Current` (`mA`), or the appropriate qualified supply-current template
- `Automotive Qualified`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For USB PD Controller value mapping:

- Use `USB Controller Type` for values such as `USB PD Sink Controller`, `USB PD Source Controller`, or `USB Type-C Controller`.
- Use `USB PD Role` for `Sink`, `Source`, or `DRP` when clear from the description or page.
- Reuse supply-voltage fields for DigiKey `Voltage - Supply`.
- Map unqualified DigiKey `Current - Supply` to `Supply Current` in mA, not to quiescent current or a maximum.
  - Example: `6mA` -> `6`
- Set `Automotive Qualified` only when DigiKey explicitly lists an automotive grade or qualification such as `AEC-Q100`.
- Do not use `Data Interface` just because DigiKey lists `Applications = USB, Type-C Controller`; only use it when an actual control interface is listed.

## Motor Driver Module Parameters

Use these parameters for breakout boards, carrier boards, and evaluation boards under `Electronics / Modules / Motor Driver Modules`:

- `Motor Driver Type`
- `Motor Type`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Load Voltage Min` (`V`)
- `Load Voltage Max` (`V`)
- `Output Current Max` (`A`)
- `Data Interface`
- `Utilized IC`
- `Module Platform`
- `Module Contents`
- `Number of Motors`
- `Mounting Type`

For Motor Driver Module value mapping:

- Use this category for complete boards/modules, not bare ICs.
- Do not split haptic, stepper, brushed DC, and BLDC modules into separate categories until the category becomes crowded.
- Distinguish module type with `Motor Driver Type`.
  - Example: Adafruit `2305` -> `Haptic`.
  - Example: Pololu `2987` -> `Stepper`.
- Use `Utilized IC` for the main driver IC, such as `DRV2605L` or `DRV8825`.
- Use `Module Platform` for board ecosystem or format, such as `Adafruit Breakout` or `Pololu Carrier`.
- Leave electrical ratings blank when the DigiKey module page does not list them.

## Analog Switch Parameters

Use these Analog Switch parameters for ICs under `Electronics / ICs / Analog Switches`:

- `Switch Circuit`
- `Mux/Demux Ratio`
- `Number of Circuits`
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Quiescent Current Max` (`uA`)
- `On-State Resistance Max` (`ohms`)
- `Switch On Time Max` (`ns`)
- `Switch Off Time Max` (`ns`)
- `Off Leakage Current Max` (`nA`)
- `Charge Injection` (`pC`)
- `Channel Capacitance` (`pF`)
- `Crosstalk` (`dB`)
- `Crosstalk Conditions`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Analog Switch value mapping:

- Map DigiKey `Multiplexer/Demultiplexer Circuit` to `Mux/Demux Ratio`.
- Split `Switch Time (Ton, Toff)` into `Switch On Time Max` and `Switch Off Time Max`.
- Convert leakage current to `nA`.
  - Example: `100pA` -> `0.1`
- Store crosstalk test frequency in `Crosstalk Conditions`.

## I/O Expander Parameters

Use these I/O Expander parameters for ICs under `Electronics / ICs / I/O Expanders`:

- `Number of I/O`
- `Data Interface`
- `Clock Frequency` (`MHz`)
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Output Type`
- `Output Current High Max` (`mA`)
- `Output Current Low Max` (`mA`)
- `Interrupt Output`
- `Internal Pull-Ups`
- `Automotive Qualified`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For I/O Expander value mapping:

- Map DigiKey `Interface` to `Data Interface`.
- Map DigiKey `Clock Frequency` to `Clock Frequency`.
- Split source/sink output current into both output-current parameters when DigiKey gives one shared value.
- Set `Interrupt Output` only when DigiKey explicitly lists interrupt output support.
- Set `Internal Pull-Ups` only when explicitly listed.

## Frequency Control Parameters

Use these categories:

- `Electronics / Frequency Control / Crystals & Resonators`
- `Electronics / Frequency Control / Oscillators`

Use these Crystal / Resonator parameters when the supplier page provides values:

- `Frequency Control Type`
- `Frequency` (`MHz`)
- `Frequency Tolerance` (`ppm`)
- `Frequency Stability` (`ppm`)
- `Load Capacitance` (`pF`)
- `ESR Max` (`ohms`)
- `Operating Mode`
- `Automotive Qualified`
- `Length` (`mm`)
- `Width` (`mm`)
- `Height` (`mm`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

Use these Oscillator parameters when the supplier page provides values:

- `Frequency Control Type`
- `Oscillator Type`
- `Frequency` (`MHz`)
- `Frequency Stability` (`ppm`)
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Output Type`
- `Quiescent Current Max` (`uA`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Frequency Control value mapping:

- Use one shared `Frequency` parameter in `MHz`.
  - Example: `500kHz` -> `0.5`
  - Example: `24 MHz` -> `24`
- Store tolerance and stability as plain ppm numbers without the `±` sign.
  - Example: `±50ppm` -> `50`
- Convert dimensions to `mm` when DigiKey lists both inch and metric values.
- Convert isolation-like or voltage-like values only when the template unit requires it.
- For unknown crystals, create an internal generic part and leave unknown load capacitance, ESR, tolerance, and stability blank.
- Do not copy values from a visually similar supplier part unless it is confirmed to be the same part.

## Timer IC Parameters

Use these Timer IC parameters for ICs under `Electronics / ICs / Timers`:

- `Timer Type`
- `Number of Circuits`
- `Frequency` (`MHz`)
- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Supply Current` (`mA`), or the appropriate qualified supply-current template
- `Output Type`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Timer IC value mapping:

- Map DigiKey `Type` to `Timer Type`.
- Map single/dual timer text to `Number of Circuits`.
  - Example: `555 Type, Timer/Oscillator (Single)` -> `1`
  - Example: `555 Type, Timer/Oscillator (Dual)` -> `2`
- Use shared `Frequency` only when DigiKey lists a frequency.
- Map unqualified `Current - Supply` to `Supply Current` in mA.
  - Example: `10 mA` -> `10`; do not call it quiescent current or maximum.
- Obsolete timer ICs should be `purchaseable = false` unless the user explicitly provides a purchasable supplier record.

## Optical Sensor Parameters

Use these categories for discrete optical detectors:

- `Electronics / Sensors / Light Optical / Photodiodes`
- `Electronics / Sensors / Light Optical / Phototransistors`

Use these shared optical parameters when the supplier product page provides values:

- `Peak Wavelength` (`nm`)
- `Spectral Range Min` (`nm`)
- `Spectral Range Max` (`nm`)
- `Viewing Angle` (`°`)
- `Dark Current` (`nA`)
- `Dark Current Conditions`
- `Photocurrent Min` (`mA`)
- `Photocurrent Typical` (`mA`)
- `Photocurrent Conditions`
- `Responsivity` (`A/W`)
- `Responsivity Conditions`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Power Dissipation @ T_A` (`W`)
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

Use these additional Photodiode parameters:

- `Photodiode Type`
- `Reverse Voltage Max` (`V`)
- `Active Area` (`mm²`)
- `Photo Response Time` (`ns`)

Use these additional Phototransistor parameters:

- `BJT Type`
- `Collector-Emitter Voltage Max` (`V`)
- `Collector Current Max` (`A`)
- `V_CE(sat) Max` (`V`)
- `V_CE(sat) Conditions`
- `Rise Time` (`ns`)
- `Fall Time` (`ns`)

For Optical Sensor value mapping:

- `Dark Current` is a generic numeric field. Preserve whether the source value is typical or maximum at the start of `Dark Current Conditions`.
  - Example: `Dark Current = 100`, `Dark Current Conditions = Maximum; V_CE=20V, E_e=0mW/cm²`.
  - Example: `Dark Current = 10`, `Dark Current Conditions = Typical; V_R=10V, E_e=0mW/cm²`.
- Preserve the supplier page's typical/maximum classification unless the user provides a correction.
- Store `Photocurrent Min` and `Photocurrent Typical` in `mA`.
  - Example: `30uA` -> `0.03`.
  - Example: `3.5uA` -> `0.0035`.
- Store irradiance, bias voltage, and wavelength in the relevant condition field.
- Use `Photo Response Time` when DigiKey provides one generic optical response-time value. Use `Rise Time` and `Fall Time` only when the source lists them separately.
- Do not reinterpret a typical breakdown voltage as an absolute maximum reverse voltage.
  - Known correction: PD204-6C uses `32`, while `170V` is its typical reverse breakdown voltage.
- Do not infer responsivity from photocurrent and irradiance. Leave it blank unless the source explicitly specifies responsivity.
- Do not create an `Orientation` parameter solely for `Top View`; package and description normally provide enough physical context.

## Optocoupler Parameters

Use these Optocoupler parameters for ICs under `Electronics / ICs / Isolation / Optocouplers`:

- `Number of Circuits`
- `Optocoupler Input Type`
- `Output Type`
- `Isolation Rating` (`kVrms`) for explicitly RMS ratings
- `Forward Voltage Typical` (`V`)
- `Forward Current Max` (`mA`)
- `Output Voltage Max` (`V`)
- `Output Current Max` (`A`)
- `CTR Min` (`%`)
- `CTR Max` (`%`)
- `CTR Conditions`
- `V_CE(sat) Max` (`V`)
- `V_CE(sat) Conditions`
- `Switch On Time Max` (`ns`)
- `Switch Off Time Max` (`ns`)
- `Rise Time` (`ns`)
- `Fall Time` (`ns`)
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For Optocoupler value mapping:

- Use `Optocoupler Input Type = DC` or `AC` only when the input type is clear.
- Reuse `Output Type`; do not create a separate optocoupler output-type parameter.
- For explicitly RMS isolation values, use `Isolation Rating` in kVrms.
  - Example: `5000Vrms` -> `5` kVrms. Do not erase the RMS distinction.
- Typical turn-on/off times must not be placed in maximum-only templates. Preserve the source timing in notes if no suitable existing template exists; do not create extra templates automatically.
- Convert output current to `A`.
  - Example: `50mA` -> `0.05`
- Store CTR test details in `CTR Conditions`.
- Use `V_CE(sat)` fields only for phototransistor optocouplers where they are listed.

## PIR Sensor Parameters

Use these PIR sensor parameters for parts under `Electronics / Sensors / Motion Sensors / PIR Sensors`:

- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Output Type`
- `Sensitivity`
- `Field of View X` (`°`)
- `Field of View Y` (`°`)
- `Detection Pattern`
- `Trigger Type`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For PIR sensor value mapping:

- Reuse the shared supply-voltage, output, mounting, package, and temperature templates.
- Keep `Sensitivity` as text because manufacturers specify PIR sensitivity using different methods and conditions.
- Store horizontal and vertical field of view separately only when the source explicitly identifies each axis.
- Do not infer field of view, sensitivity, mounting type, or supplier package from the physical appearance.
- Use the `PIR Sensors` category itself to identify the sensor technology; do not add a redundant generic `Sensor Type` parameter.
- Leave unavailable fields unset rather than copying values from another member of the sensor family.

## Sensor Lens Parameters

Use these parameters for passive sensor optics under `Electronics / Sensors / Accessories / Sensor Lenses`:

- `Field of View X` (`°`)
- `Field of View Y` (`°`)
- `Detection Distance Max` (`m`)
- `Lens Color`
- `Material`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For sensor lens records:

- Relate the lens to the compatible sensor part when compatibility is explicitly known.
- Treat color or material variants as separate parts when they are physically distinct stock items.
- Do not infer optical values from a visually similar lens.

## Environmental Sensor Parameters

Use the existing category matching the measured quantity, including:

- `Electronics / Sensors / Humidity`
- `Electronics / Sensors / Temperature`
- `Electronics / Sensors / Pressure`

Use these shared environmental parameters when listed:

- `Supply Voltage Min` (`V`)
- `Supply Voltage Max` (`V`)
- `Supply Current Typ` (`uA`)
- `Supply Current Max` (`mA`)
- `Supply Current Conditions`
- `Data Interface`
- `Resolution` (`bit`)
- `Automotive Qualified`
- `Mounting Type`
- `Package / Case`
- `Supplier Device Package`
- `Operating Temperature Min` (`°C`)
- `Operating Temperature Max` (`°C`)

For humidity and temperature sensors, use applicable fields from:

- `Humidity Range Min` (`%RH`)
- `Humidity Range Max` (`%RH`)
- `Humidity Accuracy Typ` (`%RH`)
- `Humidity Accuracy Conditions`
- `Humidity Response Time` (`s`)
- `Temperature Accuracy Typ` (`°C`)
- `Temperature Accuracy Conditions`
- `Temperature Response Time` (`s`)
- `Sensing Temperature Min` (`°C`)
- `Sensing Temperature Max` (`°C`)
- `Sensor Protection`

For pressure sensors, use applicable fields from:

- `Pressure Type`
- `Pressure Range Min` (`kPa`)
- `Pressure Range Max` (`kPa`)
- `Overpressure Max` (`kPa`)
- `Pressure Accuracy` (`kPa`)
- `Port Style`

For environmental sensor value mapping:

- Keep component ICs and sensor modules separate even when they use the same sensing element.
- Use `Data Interface` for interfaces such as `I2C` or `SPI`; do not duplicate the same value in `Output Type` unless it describes an electrical output rather than a bus.
- Convert ranges and currents into the template units while preserving conditions in their condition fields.
- Relate a module to its utilized sensor IC only when the exact IC is known.
- Accessories such as filter caps belong under `Electronics / Sensors / Accessories`, not in a sensor component category.

## Sensor Module Categories

Use `Electronics / Modules / Sensor Modules` as a structural grouping category. Do not assign parts directly to it.

Use these practical subcategories:

- `Environmental / Air Quality & Gas`
- `Environmental / Humidity & Temperature`
- `Environmental / Pressure & Altitude`
- `Motion / Accelerometers`
- `Motion / IMUs`
- `Optical & Proximity`

For module classification:

- Classify by the module's primary function, not only by the utilized IC's original DigiKey category.
- A housed or breakout sensor assembly is a module, even when its main device is a normal sensor IC.
- Use `Module Type = Module` or `Board` as appropriate.
- Store the exact main device in `Utilized IC` and create a related-part link when that bare component exists in InvenTree.
- Do not create a bare component solely to support a module relationship unless requested.
- Do not reuse a bare IC image as the module image.

## Current Sensor Drawer Plan

- Cabinet-02 Drawer-27: THT optical sensors and detectors.
- Cabinet-02 Drawer-28: SMD photodiodes and IR receivers.
- Cabinet-02 Drawer-29: IR LED emitters.
- Cabinet-02 Drawer-30: PIR sensors and sensor lenses.
- Cabinet-02 Drawer-31: Position, proximity, and touch sensor components.
- Cabinet-02 Drawer-32: Piezoelectric elements and transducers.
- Cabinet-02 Drawer-33: Environmental sensor components.
- Cabinet-02 Drawer-34: Environmental sensor modules.
- Cabinet-02 Drawer-35: Motion sensor modules.
- Cabinet-02 Drawer-36: Optical and proximity sensor modules.
- Cabinet-02 Drawer-37: Audio modules, including microphone and amplifier boards.

This is a placement reference, not permission to rename or move any location. Check live stock before choosing a drawer.

## Price Breaks

- Use the user-provided price-break table for supplier pricing.
- Do not spend time scraping DigiKey or Mouser pricing; the user will provide the applicable price breaks.
- Do not use distributor mirrors, search snippets, converted currencies, or inferred values for DigiKey pricing.
- Do not import or display USD prices for this workflow.
- Preserve the supplier price precision when storing price breaks.
- Use quantity and unit price only.
- If the user does not provide price breaks, leave them empty instead of guessing or searching for them.

## Stock And Purchasing

- Never fetch, track or populate supplier availability in this workflow. Leave the default alone on creation; do not write `0` to existing records as an unsolicited cleanup.
- Record packaging if listed.
- Record lifecycle/status notes only when listed.
- Do not create stock items unless explicitly requested.
- Do not change stock locations unless explicitly requested.
- Creating a catalog part and adding physical stock are separate operations. Never infer stock quantity.
- If no quantity is supplied, do not create stock; ask for the quantity only when stock creation is required.
- If the part already exists, treat a provided quantity as additional stock to add, not as the final total, unless the user explicitly says it is the total count.
- Link created stock items to the matching supplier part when the stock came from that supplier part.
- Supplier-part stock views can show `0` if the stock item is not linked to the supplier part.
- Supplier-part local stock totals are different from supplier availability. Keep both relationships intact: stock item -> supplier part -> manufacturer part.
- NEVER rename drawers. Warehouse names remain `Drawer-##`; requested names are suggestions for physical printed labels only.
- Resolve `C1Dxx` and `C2Dxx` under the correct cabinet in `Berlin Home`. Do not infer a cabinet from an old conversation default when context is unclear.
- Cabinet-01 Drawer-44 was subdivided into Drawer-44 through Drawer-47. Preserve the existing assignments, including the intentional shared LED 147; do not repair or renumber them.
- Drawer-41 through Drawer-43 are larger than Drawer-01 through Drawer-40. Consider physical fit when suggesting locations; Cabinet-01's former large Drawer-44 is now subdivided.
- Use `THT` in keywords for through-hole parts and `SMD` for surface-mount parts.
- Reuse package images only when the package is actually the same.
  - Example: reuse a `SOT-23-3` image only for other `SOT-23-3` parts.
  - Current reusable package images include `TO-92-3.webp`, `TO-220-3.png`, `TO-252.png`, `SOT-23-3.png`, `SOT-363.png`, `6TSOP.webp`, `8-DIP.webp`, `14-DIP.webp`, `8-SOIC.webp`, and `24-WFQFN_Exposed_Pad.webp`.
  - Set the visible part image field, not only an attachment, when reusing an image.
- Check local InvenTree images first for an exact product image. Otherwise, use the exact image linked from DigiKey.com before considering a generic package image.
- A manufacturer family image is acceptable only when it visibly includes the exact package variant; note that it is a family image in the attachment comment.
- Attach the supplier-linked datasheet as a separate file attachment without reading or scanning its contents.
- Do not search manufacturer sites, search engines, distributor mirrors, or other websites for missing datasheets.
- Do not perform a general web search for assets. For DigiKey parts, use only the exact image and datasheet links exposed by the corresponding DigiKey.com product page.
- Image and datasheet retrieval each have a strict two-quick-attempt limit. After two failed attempts, continue part creation without the missing asset.

## BJT Array Mapping

- For BJT arrays, use the polarity category unless a separate array category is explicitly requested.
- Map `2 NPN (Dual)` to `BJT Type = NPN` and `Configuration = Dual`.
- Map `2 PNP (Dual)` to `BJT Type = PNP` and `Configuration = Dual`.

## Verification

After creating or updating a part, verify:

- Part exists in the correct category.
- IPN equals the part number.
- Manufacturer and MPN are correct.
- Supplier is DigiKey and SPN is correct.
- The file under the supplier page's `Datasheet` link is copied to `Attachments` when accessible; its contents are not scanned.
- For a DigiKey-sourced part, the exact DigiKey product image was checked, copied when accessible, validated, and set as the visible part image.
- Parameters have no duplicated units.
- Price breaks exactly match the user-provided table and remain in EUR.
- Supplier availability was not fetched or changed.
- Stock quantity is additive when requested, and supplier/manufacturer links are correct.
- Existing drawer names, unrelated records and WLED mappings remain unchanged.
- No duplicate part, manufacturer part, supplier part, or parameter records were created.
