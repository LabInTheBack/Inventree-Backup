# InvenTree Part Creation Rules

Use this checklist before creating or updating parts in InvenTree.

## Source Rules

- Use the provided supplier page as the primary source.
- Do not invent missing values.
- Do not use external sources unless explicitly requested.
- Do not fill fields the user did not ask for.
- If a required value is missing, leave it blank instead of guessing.
- Before creating the part, present the extracted data for review when requested.

## Core Part Fields

- Part name should be the actual part number.
- IPN must match the part name / part number unless explicitly told otherwise.
- Description should be concise and taken from the supplier page.
- Category must match the actual component family.
- Add useful keywords, but keep them factual and concise. Always reuse the existing ones.
- Attach the product image when available, or reuse an existing package image when the package matches.
- Attach the datasheet when available from the supplier page.
- Put the manufacturer/product page in `Part Details -> Link` when the user provides one.
- Do not use an attachment as a substitute for the part link field.

## Manufacturer And Supplier

- Manufacturer must be the real manufacturer from the supplier page. (If possible use provided supplier list in Inventree)
- Check for existing equivalent manufacturer names before creating a new company.
  - Example: `Diodes Inc` and `Diodes Incorporated` should not both exist.
- Manufacturer part number must be the actual MPN.
- Supplier should be `DigiKey` for DigiKey pages.
- Use only `SPN` for the supplier part number.
- Do not create both `DigiKey Part Number` and `SPN`; they are the same supplier-part identifier.
- Supplier link should point to the exact supplier product page.
- If multiple DigiKey SKUs exist and the user says they bought Cut Tape, use the Cut Tape SPN.

## Parameters

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
- `Input Offset Voltage Max` (`mV`)
- `Input Bias Current Max` (`nA`)
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
- Convert `µV` to `mV` for `Input Offset Voltage Max`.
  - Example: `150 µV` -> `0.15`
- Convert `µA` to `mA` for `Supply Current per Channel`.
  - Example: `500µA` -> `0.5`
- Convert `pA` to `nA` for `Input Bias Current Max`.
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
- `Rise Time Max` (`ns`)
- `Fall Time Max` (`ns`)
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
- Split `Rise / Fall Time` into `Rise Time Max` and `Fall Time Max`.

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
- `Quiescent Current Max` (`uA`)
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
- Convert quiescent current to `uA`.
- Store dropout test details in `Dropout Voltage Conditions`.

## DC-DC Converter IC Parameters

Use these DC-DC Converter IC parameters when the DigiKey page or provided manufacturer page gives values:

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

## Price Breaks

- DigiKey.com may be used for technical product attributes when DigiKey.de is blocked.
- For DigiKey pricing, use DigiKey.de EUR price breaks only.
- Do not use distributor mirrors, search snippets, converted currencies, or inferred values for DigiKey pricing.
- Do not import or display USD prices for this workflow.
- Preserve the supplier price precision when storing price breaks.
- Use quantity and unit price only.
- If no EUR price table is provided, leave price breaks empty instead of fetching or guessing.

## Stock And Purchasing

- Do not record supplier availability unless explicitly requested. For this workflow, leave supplier availability at `0`.
- Record packaging if listed.
- Record lifecycle/status notes only when listed.
- Do not create stock items unless explicitly requested.
- Do not change stock locations unless explicitly requested.
- Link created stock items to the matching supplier part when the stock came from that supplier part.
- Supplier-part stock views can show `0` if the stock item is not linked to the supplier part.
- Use `THT` in keywords for through-hole parts and `SMD` for surface-mount parts.
- Reuse package images only when the package is actually the same.
  - Example: reuse a `SOT-23-3` image only for other `SOT-23-3` parts.
  - Current reusable package images include `TO-92-3.webp`, `TO-220-3.png`, `TO-252.png`, `SOT-23-3.png`, `SOT-363.png`, `8-DIP.webp`, and `8-SOIC.webp`.

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
- Datasheet is attached when available.
- Image is attached when available.
- Parameters have no duplicated units.
- EUR price breaks match the supplier page.
- No duplicate part, manufacturer part, supplier part, or parameter records were created.
