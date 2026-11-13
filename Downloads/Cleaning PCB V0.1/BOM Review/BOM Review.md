# Cleaning PCBA V0.1 — proposed catalog and BOM entries

Read-only review, 2026-11-12. All 23 supplied DigiKey SPN/MPN pairs confirmed on DigiKey.com. No InvenTree records or stock changed. Seventeen requested MPNs are new to the catalog; six existing records can be considered for reuse, with SC1176 requiring a variant check.

Quantities and references below come from the earlier BOM CSV, not purchase quantities. Five changed MPNs are proposed substitutions; the supplied part-number list alone does not confirm their PCB placement. Stock means recorded on-hand count, without checking reservations.

| MPN | Manufacturer | DigiKey SPN | Main specifications | References | Per board / recorded stock | Proposed action |
|---|---|---|---|---|---:|---|
| [CC0805KRX5R6BB106](https://www.digikey.com/en/products/detail/yageo/CC0805KRX5R6BB106/7164445) | Yageo | 311-3424-1-ND | 10 µF, 10 V, ±10%, X5R, 0805 | C11, C8, C9 | 3 / 0 | Create |
| [CL10B103KB8NNNC](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL10B103KB8NNNC/3889095) | Samsung Electro-Mechanics | 1276-1009-1-ND | 10 nF, 50 V, ±10%, X7R, 0603 | C12, C2 | 2 / 0 | Create |
| [C0603C104K5RACTU](https://www.digikey.com/en/products/detail/kemet/C0603C104K5RACTU/1465623) | KEMET | 399-C0603C104K5RACTUCT-ND | 100 nF, 50 V, ±10%, X7R, 0603 | C13, C14, C15, C3, C4 | 5 / 0 | Create |
| [LTST-C190KRKT](https://www.digikey.com/en/products/detail/liteon/LTST-C190KRKT/386817) | Lite-On Inc. | 160-1436-1-ND | Red LED; 631 nm; Vf typ 2 V; 99 mcd; 0603 | D3 | 1 / 0 | Create |
| [LTST-C190KGKT](https://www.digikey.com/en/products/detail/liteon/LTST-C190KGKT/386815) | Lite-On Inc. | 160-1435-1-ND | Green LED; 572 nm; Vf typ 2.15 V; 44.5 mcd; 0603 | D4 | 1 / 0 | Create |
| [RC0805FR-0710KL](https://www.digikey.com/en/products/detail/yageo/RC0805FR-0710KL/730482) | Yageo | 311-10.0KCRCT-ND | 10 kΩ, ±1%, 0.125 W, 0805, thick film | R1 | 1 / 0 | Create |
| [RC0603JR-07470RL](https://www.digikey.com/en/products/detail/yageo/RC0603JR-07470RL/726791) | Yageo | 311-470GRCT-ND | 470 Ω, ±5%, 0.1 W, 0603, thick film | R10, R11 | 2 / 0 | Create |
| [RT0603BRD07100KL](https://www.digikey.com/en/products/detail/yageo/RT0603BRD07100KL/1072187) | Yageo | YAG1235CT-ND | 100 kΩ, ±0.1%, 0.1 W, 0603, thin film | R14, R15 | 2 / 0 | Create |
| [RC0603JR-070RL](https://www.digikey.com/en/products/detail/yageo/RC0603JR-070RL/726675) | Yageo | 311-0.0GRCT-ND | 0 Ω jumper, 0.1 W, 0603, thick film | R2, R3, R4, R5 | 4 / 0 | Create |
| [RC0603FR-071KL](https://www.digikey.com/en/products/detail/yageo/RC0603FR-071KL/726843) | Yageo | 311-1.00KHRCT-ND | 1 kΩ, ±1%, 0.1 W, 0603, thick film | R8, R9 | 2 / 0 | Create |
| [KMR621NG LFS](https://www.digikey.com/en/products/detail/c-k/KMR621NG-LFS/6035350) | C&K | CKN10684CT-ND | SPST-NO momentary; 50 mA at 32 VDC; IP67; 200 gf | SW1, SW2 | 2 / 0 | Create |
| [3782](https://www.digikey.com/en/products/detail/pololu/3782/10451209) | Pololu | 2183-3782-ND | 5 V buck module; 5.3–50 V input; 3.2 A listed; 16 W | U1 | 1 / 0 | Reuse |
| [TXU0202DCUR](https://www.digikey.com/en/products/detail/texas-instruments/TXU0202DCUR/16677096) | Texas Instruments | 296-TXU0202DCURCT-ND | 2-channel level translator; VCCA/VCCB 1.08–5.5 V; 200 Mbps; 8-VSSOP | U2 | 1 / 0 | Create |
| [2814](https://www.digikey.com/en/products/detail/pololu/2814/10450362) | Pololu | 2183-2814-ND | MOSFET load-switch board; sparse DigiKey ratings; retain existing Pololu data | U3, U5 | 2 / 1 | Reuse and add DigiKey supplier |
| [173020536](https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/173020536/26762577) | Würth Elektronik | 732-173020536-ND | 5 V, 2 A buck module; 8–36 V input; 10 W; 3-SIP | U4 | 1 / 0 | Create |
| [SC1176](https://www.digikey.com/en/products/detail/raspberry-pi/SC1176/15298147) | Raspberry Pi | 2648-SC1176-ND | Zero 2 W SBC; 1 GHz, 4 cores, 512 MB RAM; header variant needs checking | U6 | 1 / 1 | Verify header variant before supplier link |
| [4035](https://www.digikey.com/en/products/detail/pololu/4035/26714680) | Pololu | 2183-4035-ND | DRV8874 brushed-motor driver board; 4.5–37 V; 2.1 A | U7 | 1 / 1 | Reuse and add DigiKey supplier |
| [74LVC2G14GV,125](https://www.digikey.com/en/products/detail/nexperia-usa-inc/74LVC2G14GV-125/1231582) | Nexperia USA Inc. | 1727-6088-1-ND | Dual Schmitt inverter; 1.65–5.5 V; 6-TSOP | U8 | 1 / 21 | Reuse |
| [UMK325AB7106KMHP](https://www.digikey.com/en/products/detail/taiyo-yuden/UMK325AB7106KMHP/8619563) | Taiyo Yuden | 587-6160-1-ND | 10 µF, 50 V, ±10%, X7R, 1210; AEC-Q200 | C1, C10, C5, C6, C7 | 5 / 0 | Create |
| [B360A-13-F](https://www.digikey.com/en/products/detail/diodes-incorporated/B360A-13-F/724950) | Diodes Inc | B360A-FDICT-ND | Schottky diode; 60 V, 3 A; Vf max 0.7 V at 3 A; SMA | D1, D2 | 2 / 0 | Create |
| [OSTYC022150](https://www.digikey.com/en/products/detail/on-shore-technology-inc/OSTYC022150/1588994) | On Shore Technology Inc. | ED2902-ND | 2-pin screw terminal; 5.08 mm pitch; 10 A, 300 V; THT | J1, J2, J3, J4, J5, J6, J7, J8 | 8 / 28 | Reuse |
| [CRG0603F2K0](https://www.digikey.com/en/products/detail/te-connectivity-passive-product/CRG0603F2K0/2380757) | TE Connectivity | 1712-CRG0603F2K0CT-ND | 2 kΩ, ±1%, 0.1 W, 0603, thick film | R12, R13 | 2 / 0 | Create |
| [CRG0603F10K/10](https://www.digikey.com/en/products/detail/te-connectivity-passive-product/CRG0603F10K-10/2390661) | TE Connectivity | A121523CT-ND | 10 kΩ, ±1%, 0.1 W, 0603, thick film | R6, R7 | 2 / 0 | Create |

## Items to resolve

- The current live BOM also contains Q1, MBT3904DW1T3G x1, added since the initial draft. It is absent from the new 23-item list. Confirm whether it remains required. The bare PCB is also additional to the supplier list.
- Proposed substitutions: CL21A106KPFNNNE → CC0805KRX5R6BB106; CL10B104KB8NNNC → C0603C104K5RACTU; 885012209073 → UMK325AB7106KMHP; RC0603FR-072KL → CRG0603F2K0; RC0603FR-0710KL → CRG0603F10K/10.
- SC1176 header configuration and board identity must be checked against the existing WH record.
- Module 173020536 needs a land-pattern check against the existing footprint.
- Pololu 3782 requires 1 for this BOM and recorded stock is 0. Pololu 2814 requires 2 and recorded stock is 1.

## Proposed InvenTree handling

- Part name/IPN: exact MPN for new parts; keep existing names and identities when reusing catalog entries.
- ManufacturerPart: use canonical companies; create Lite-On Inc., C&K and Taiyo Yuden only if still missing at import time. SupplierPart: DigiKey, exact SPN and verified DigiKey.com URL, linked to ManufacturerPart.
- New catalog parts: component/purchaseable, no stock until receipt; no inferred order quantities, prices, supplier availability, storage or manufacturer facts.
- Reuse existing parameter templates and metric units. Capacitance uses F: 10 µF = 0.00001; 10 nF = 0.00000001; 100 nF = 0.0000001. Resistance uses ohms: 1 kΩ = 1000, 2 kΩ = 2000, 10 kΩ = 10000, 100 kΩ = 100000.
- Capacitor dielectric X5R/X7R needs a text field or notes; never enter it in the numeric ppm/°C temperature-coefficient field. Resistor temperature coefficients are unsigned magnitudes with ± retained in notes.
- Preserve max/typical/test conditions: LED 20 mA is test current; diode temperature is junction temperature; capacitor thickness and seated resistor/LED heights are maxima; regulator output current is conditional.
- Add supported fields lacking suitable templates as narrowly scoped new fields or notes at import; examples are dielectric, dominant wavelength, luminous intensity, test current and mechanical life.
- Images: 23 exact-page image files downloaded and validated; many are supplier representative family/package images. Reuse existing exact images where suitable; flag their representative nature. No specification inferred from appearance.
- Datasheet links are exposed on all pages. Direct HTML retrieval returned HTTP 403, so exact document file addresses were not recovered. No PDFs were opened or parsed. Product images were fetched separately from exposed links. Retain existing useful attachments; retrieve linked PDFs when possible during approved entry.
- Capture all nonempty technical attributes listed below. Blank fields stay unset. Shipping promises, standard lead times, supplier stock and prices are excluded.

## Per-part technical fields

### 1. CC0805KRX5R6BB106

Manufacturer: Yageo. Supplier SPN: 311-3424-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [CC0805KRX5R6BB106 — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/CC0805KRX5R6BB106/7164445).

| Source attribute | Value to preserve |
|---|---|
| Temperature Coefficient | X5R |
| Operating Temperature | -55°C ~ 85°C |
| Series | CC |
| Applications | General Purpose |
| Mounting Type | Surface Mount, MLCC |
| Package / Case | 0805 (2012 Metric) |
| Capacitance | 10 µF |
| Size / Dimension | 0.079" L x 0.049" W (2.00mm x 1.25mm) |
| Tolerance | ±10% |
| Thickness (Max) | 0.057" (1.45mm) |
| Voltage - Rated | 10V |

Review: Proposed replacement for CL21A106KPFNNNE; same nominal value/package, not a confirmed design substitution.

Image: [downloaded product image](images/01.jpg). Datasheet: linked on source page; download pending.

### 2. CL10B103KB8NNNC

Manufacturer: Samsung Electro-Mechanics. Supplier SPN: 1276-1009-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [CL10B103KB8NNNC — DigiKey.com](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL10B103KB8NNNC/3889095).

| Source attribute | Value to preserve |
|---|---|
| Temperature Coefficient | X7R |
| Operating Temperature | -55°C ~ 125°C |
| Series | CL |
| Applications | General Purpose |
| Mounting Type | Surface Mount, MLCC |
| Package / Case | 0603 (1608 Metric) |
| Capacitance | 10000 pF |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | ±10% |
| Thickness (Max) | 0.035" (0.90mm) |
| Voltage - Rated | 50V |

Image: [downloaded product image](images/02.jpg). Datasheet: linked on source page; download pending.

### 3. C0603C104K5RACTU

Manufacturer: KEMET. Supplier SPN: 399-C0603C104K5RACTUCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [C0603C104K5RACTU — DigiKey.com](https://www.digikey.com/en/products/detail/kemet/C0603C104K5RACTU/1465623).

| Source attribute | Value to preserve |
|---|---|
| Temperature Coefficient | X7R |
| Operating Temperature | -55°C ~ 125°C |
| Series | SMD Comm X7R |
| Applications | Bypass, Decoupling |
| Mounting Type | Surface Mount, MLCC |
| Package / Case | 0603 (1608 Metric) |
| Capacitance | 0.1 µF |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | ±10% |
| Thickness (Max) | 0.034" (0.87mm) |
| Voltage - Rated | 50V |

Review: Proposed replacement for CL10B104KB8NNNC; same nominal value/package, not a confirmed design substitution.

Image: [downloaded product image](images/03.jpg). Datasheet: linked on source page; download pending.

### 4. LTST-C190KRKT

Manufacturer: Lite-On Inc.. Supplier SPN: 160-1436-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [LTST-C190KRKT — DigiKey.com](https://www.digikey.com/en/products/detail/liteon/LTST-C190KRKT/386817).

| Source attribute | Value to preserve |
|---|---|
| Voltage - Forward (Vf) (Typ) | 2V |
| Current - Test | 20mA |
| Viewing Angle | 130° |
| Mounting Type | Surface Mount |
| Color | Red |
| Wavelength - Dominant | 631nm |
| Configuration | Standard |
| Wavelength - Peak | 639nm |
| Lens Color | Colorless |
| Package / Case | 0603 (1608 Metric) |
| Lens Transparency | Clear |
| Size / Dimension | 1.60mm L x 0.80mm W |
| Millicandela Rating | 99mcd |
| Height (Max) | 0.90mm |
| Lens Style | Rectangle with Flat Top |
| Lens Size | 1.10mm x 0.80mm |

Review: 20 mA is test current, not a maximum forward-current rating. Dominant and peak wavelengths are different fields.

Image: [downloaded product image](images/04.jpg). Datasheet: linked on source page; download pending.

### 5. LTST-C190KGKT

Manufacturer: Lite-On Inc.. Supplier SPN: 160-1435-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [LTST-C190KGKT — DigiKey.com](https://www.digikey.com/en/products/detail/liteon/LTST-C190KGKT/386815).

| Source attribute | Value to preserve |
|---|---|
| Voltage - Forward (Vf) (Typ) | 2.15V |
| Current - Test | 20mA |
| Viewing Angle | 130° |
| Mounting Type | Surface Mount |
| Color | Green |
| Wavelength - Dominant | 572nm |
| Configuration | Standard |
| Wavelength - Peak | 574nm |
| Lens Color | Colorless |
| Package / Case | 0603 (1608 Metric) |
| Lens Transparency | Clear |
| Size / Dimension | 1.60mm L x 0.80mm W |
| Millicandela Rating | 44.5mcd |
| Height (Max) | 0.90mm |
| Lens Style | Rectangle with Flat Top |
| Lens Size | 1.10mm x 0.80mm |

Review: 20 mA is test current, not a maximum forward-current rating. Dominant and peak wavelengths are different fields.

Image: [downloaded product image](images/05.jpg). Datasheet: linked on source page; download pending.

### 6. RC0805FR-0710KL

Manufacturer: Yageo. Supplier SPN: 311-10.0KCRCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [RC0805FR-0710KL — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/RC0805FR-0710KL/730482).

| Source attribute | Value to preserve |
|---|---|
| Features | Moisture Resistant |
| Temperature Coefficient | ±100ppm/°C |
| Series | RC_L |
| Operating Temperature | -55°C ~ 155°C |
| Package / Case | 0805 (2012 Metric) |
| Supplier Device Package | 0805 |
| Resistance | 10 kOhms |
| Size / Dimension | 0.079" L x 0.049" W (2.00mm x 1.25mm) |
| Tolerance | ±1% |
| Height - Seated (Max) | 0.024" (0.60mm) |
| Power (Watts) | 0.125W, 1/8W |
| Number of Terminations | 2 |
| Composition | Thick Film |

Image: [downloaded product image](images/06.jpg). Datasheet: linked on source page; download pending.

### 7. RC0603JR-07470RL

Manufacturer: Yageo. Supplier SPN: 311-470GRCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [RC0603JR-07470RL — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/RC0603JR-07470RL/726791).

| Source attribute | Value to preserve |
|---|---|
| Features | Moisture Resistant |
| Temperature Coefficient | ±100ppm/°C |
| Series | RC_L |
| Operating Temperature | -55°C ~ 155°C |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Resistance | 470 Ohms |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | ±5% |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Power (Watts) | 0.1W, 1/10W |
| Number of Terminations | 2 |
| Composition | Thick Film |

Image: [downloaded product image](images/07.jpg). Datasheet: linked on source page; download pending.

### 8. RT0603BRD07100KL

Manufacturer: Yageo. Supplier SPN: YAG1235CT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [RT0603BRD07100KL — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/RT0603BRD07100KL/1072187).

| Source attribute | Value to preserve |
|---|---|
| Composition | Thin Film |
| Temperature Coefficient | ±25ppm/°C |
| Series | RT |
| Operating Temperature | -55°C ~ 155°C |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Resistance | 100 kOhms |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | ±0.1% |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Power (Watts) | 0.1W, 1/10W |
| Number of Terminations | 2 |

Image: [downloaded product image](images/08.jpg). Datasheet: linked on source page; download pending.

### 9. RC0603JR-070RL

Manufacturer: Yageo. Supplier SPN: 311-0.0GRCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [RC0603JR-070RL — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/RC0603JR-070RL/726675).

| Source attribute | Value to preserve |
|---|---|
| Composition | Thick Film |
| Features | Moisture Resistant |
| Series | RC_L |
| Operating Temperature | -55°C ~ 155°C |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Resistance | 0 Ohms |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | Jumper |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Power (Watts) | 0.1W, 1/10W |
| Number of Terminations | 2 |

Review: Tolerance is Jumper, not ±5%; do not infer tolerance from the J in the MPN.

Image: [downloaded product image](images/09.jpg). Datasheet: linked on source page; download pending.

### 10. RC0603FR-071KL

Manufacturer: Yageo. Supplier SPN: 311-1.00KHRCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [RC0603FR-071KL — DigiKey.com](https://www.digikey.com/en/products/detail/yageo/RC0603FR-071KL/726843).

| Source attribute | Value to preserve |
|---|---|
| Features | Moisture Resistant |
| Temperature Coefficient | ±100ppm/°C |
| Series | RC_L |
| Operating Temperature | -55°C ~ 155°C |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Resistance | 1 kOhms |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Tolerance | ±1% |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Power (Watts) | 0.1W, 1/10W |
| Number of Terminations | 2 |
| Composition | Thick Film |

Image: [downloaded product image](images/10.jpg). Datasheet: linked on source page; download pending.

### 11. KMR621NG LFS

Manufacturer: C&K. Supplier SPN: CKN10684CT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [KMR621NG LFS — DigiKey.com](https://www.digikey.com/en/products/detail/c-k/KMR621NG-LFS/6035350).

| Source attribute | Value to preserve |
|---|---|
| Actuator Height off PCB, Vertical | 1.90mm |
| Actuator Orientation | Top Actuated |
| Series | KMR6 |
| Termination Style | Gull Wing |
| Outline | 4.20mm x 2.80mm |
| Illumination | Non-Illuminated |
| Circuit | SPST-NO |
| Operating Force | 200gf |
| Switch Function | Off-Mom |
| Ingress Protection | IP67 - Dust Tight, Waterproof |
| Contact Rating @ Voltage | 0.05A @ 32VDC |
| Operating Temperature | -40°C ~ 85°C |
| Actuator Type | Standard |
| Mechanical Life | 200,000 Cycles |
| Mounting Type | Surface Mount |

Image: [downloaded product image](images/11.jpg). Datasheet: linked on source page; download pending.

### 12. 3782

Manufacturer: Pololu. Supplier SPN: 2183-3782-ND. Packaging: Bulk. Status: Active.

Source: [3782 — DigiKey.com](https://www.digikey.com/en/products/detail/pololu/3782/10451209).

| Source attribute | Value to preserve |
|---|---|
| Voltage - Output 1 | 5V |
| Current - Output (Max) | 3.2A |
| Series | D36V28 |
| Power (Watts) | 16 W |
| Efficiency | 90% |
| Mounting Type | Through Hole |
| Type | Non-Isolated PoL Module |
| Package / Case | 5-SIP Module |
| Number of Outputs | 1 |
| Size / Dimension | 0.80" L x 0.70" W x 0.35" H (20.3mm x 17.8mm x 8.9mm) |
| Voltage - Input (Min) | 5.3V |
| Control Features | Enable, Active Floating |
| Voltage - Input (Max) | 50V |

Review: Keep the existing manufacturer qualification: 3.2 A typical maximum at 36 V input, subject to cooling; not guaranteed throughout the input range. Retain manufacturer dimensions rather than overwriting with rounded distributor dimensions.

Image: [downloaded product image](images/12.jpg). Datasheet: linked on source page; download pending.

### 13. TXU0202DCUR

Manufacturer: Texas Instruments. Supplier SPN: 296-TXU0202DCURCT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [TXU0202DCUR — DigiKey.com](https://www.digikey.com/en/products/detail/texas-instruments/TXU0202DCUR/16677096).

| Source attribute | Value to preserve |
|---|---|
| Voltage - VCCB | 1.08 V ~ 5.5 V |
| Output Type | Tri-State, Non-Inverted |
| Data Rate | 200Mbps |
| Operating Temperature | -40°C ~ 125°C (TA) |
| Translator Type | Voltage Level |
| Mounting Type | Surface Mount |
| Channel Type | Unidirectional |
| Package / Case | 8-VFSOP (0.091", 2.30mm Width) |
| Number of Circuits | 1 |
| Supplier Device Package | 8-VSSOP |
| Channels per Circuit | 2 |
| Voltage - VCCA | 1.08 V ~ 5.5 V |

Review: Both supply domains share the listed 1.08–5.5 V limits. Preserve Unidirectional and Tri-State, Non-Inverted literally; do not infer protocol compatibility.

Image: [downloaded product image](images/13.jpg). Datasheet: linked on source page; download pending.

### 14. 2814

Manufacturer: Pololu. Supplier SPN: 2183-2814-ND. Packaging: Bulk. Status: Active.

Source: [2814 — DigiKey.com](https://www.digikey.com/en/products/detail/pololu/2814/10450362).

| Source attribute | Value to preserve |
|---|---|
| Function | Power Distribution Switch (Load Switch) |
| Embedded | Yes |
| Utilized IC / Part | BA2U12 |
| Contents | Board(s) |
| Type | Power Management |

Review: DigiKey calls this a BA2U12 evaluation board and supplies no electrical limits. Preserve previously entered manufacturer-page data: 4.5–32 V recommended, 40 V absolute, 8 A thermally conditional; do not infer a new IC identity from this listing alone.

Image: [downloaded product image](images/14.jpg). Datasheet: linked on source page; download pending.

### 15. 173020536

Manufacturer: Würth Elektronik. Supplier SPN: 732-173020536-ND. Packaging: Tube. Status: Active.

Source: [173020536 — DigiKey.com](https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/173020536/26762577).

| Source attribute | Value to preserve |
|---|---|
| Voltage - Output 1 | 5V |
| Current - Output (Max) | 2A |
| Series | MagI³C, FDSM |
| Power (Watts) | 10 W |
| Applications | ITE (Commercial) |
| Operating Temperature | -40°C ~ 85°C (With Derating) |
| Type | Non-Isolated PoL Module |
| Efficiency | 91% |
| Number of Outputs | 1 |
| Mounting Type | Through Hole |
| Voltage - Input (Min) | 8V |
| Package / Case | 3-SIP Module |
| Voltage - Input (Max) | 36V |
| Size / Dimension | 0.45" L x 0.35" W x 0.69" H (11.5mm x 9.0mm x 17.5mm) |

Review: Listed 11.5 x 9.0 mm body differs from original footprint name SIP3_11.6x8.5mm_WPME; check actual land pattern before assembly. Temperature range requires derating; efficiency conditions unspecified.

Image: [downloaded product image](images/15.jpg). Datasheet: linked on source page; download pending.

### 16. SC1176

Manufacturer: Raspberry Pi. Supplier SPN: 2648-SC1176-ND. Packaging: Bulk. Status: Active.

Source: [SC1176 — DigiKey.com](https://www.digikey.com/en/products/detail/raspberry-pi/SC1176/15298147).

| Source attribute | Value to preserve |
|---|---|
| Expansion Site/Bus | Bluetooth 4.2, BLE, HAT GPIO, LAN |
| RAM Capacity/Installed | 512MB/512MB |
| Series | Raspberry Pi Zero 2 W |
| Storage Interface | MicroSD |
| Video Outputs | Composite, HDMI |
| USB | USB 2.0 (1) OTG |
| Core Processor | Broadcom BCM2710A1 Arm Cortex-A53 |
| Digital I/O Lines | 40 |
| Speed | 1GHz |
| Operating Temperature | -20°C ~ 70°C |
| Number of Cores | 4 |
| Size / Dimension | 2.600" x 1.180" (66.04mm x 29.97mm) |

Review: Existing record says Zero 2 WH with installed headers; DigiKey says Zero 2 W and representative image has no header. Confirm physical version before attaching this supplier identity. DigiKey dimensions 66.04 x 29.97 mm conflict with existing 65 x 30 mm; do not overwrite automatically. LAN is listed as expansion, not proof of a built-in Ethernet port.

Image: [downloaded product image](images/16.jpg). Datasheet: linked on source page; download pending.

### 17. 4035

Manufacturer: Pololu. Supplier SPN: 2183-4035-ND. Packaging: Bulk. Status: Active.

Source: [4035 — DigiKey.com](https://www.digikey.com/en/products/detail/pololu/4035/26714680).

| Source attribute | Value to preserve |
|---|---|
| Control / Drive Type | Brushed |
| Number of Motors | 1 |
| Series | DRV8874 |
| Voltage - Load | 4.5 ~ 37V |
| Current - Output | 2.1A |
| Voltage - Supply | 4.5 ~ 37V |
| Type | Board |
| Mounting Type | Through Hole |
| Motor Type | Brushed DC |
| Weight | 0.032 oz (0.90g) |

Review: Keep existing manufacturer-sourced current limit, interface and protection data in addition to sparse DigiKey attributes.

Image: [downloaded product image](images/17.jpg). Datasheet: linked on source page; download pending.

### 18. 74LVC2G14GV,125

Manufacturer: Nexperia USA Inc.. Supplier SPN: 1727-6088-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [74LVC2G14GV,125 — DigiKey.com](https://www.digikey.com/en/products/detail/nexperia-usa-inc/74LVC2G14GV-125/1231582).

| Source attribute | Value to preserve |
|---|---|
| Current - Quiescent (Max) | 4 µA |
| Current - Output High, Low | 32mA, 32mA |
| Series | 74LVC |
| Input Logic Level - Low | 0.25V ~ 1.2V |
| Input Logic Level - High | 1.7V ~ 3.8V |
| Max Propagation Delay @ V, Max CL | 4.7ns @ 5V, 50pF |
| Logic Type | Inverter |
| Operating Temperature | -40°C ~ 125°C (TA) |
| Number of Circuits | 2 |
| Mounting Type | Surface Mount |
| Number of Inputs | 2 |
| Supplier Device Package | 6-TSOP |
| Features | Schmitt Trigger |
| Package / Case | SC-74, SOT-457 |
| Voltage - Supply | 1.65V ~ 5.5V |

Image: [downloaded product image](images/18.jpg). Datasheet: linked on source page; download pending.

### 19. UMK325AB7106KMHP

Manufacturer: Taiyo Yuden. Supplier SPN: 587-6160-1-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [UMK325AB7106KMHP — DigiKey.com](https://www.digikey.com/en/products/detail/taiyo-yuden/UMK325AB7106KMHP/8619563).

| Source attribute | Value to preserve |
|---|---|
| Operating Temperature | -55°C ~ 125°C |
| Series | M |
| Applications | Automotive, SMPS Filtering |
| Mounting Type | Surface Mount, MLCC |
| Package / Case | 1210 (3225 Metric) |
| Capacitance | 10 µF |
| Size / Dimension | 0.126" L x 0.098" W (3.20mm x 2.50mm) |
| Tolerance | ±10% |
| Thickness (Max) | 0.110" (2.80mm) |
| Voltage - Rated | 50V |
| Temperature Coefficient | X7R |

Review: Proposed replacement for 885012209073; same nominal value/package, not a confirmed design substitution.

Image: [downloaded product image](images/19.jpg). Datasheet: linked on source page; download pending.

### 20. B360A-13-F

Manufacturer: Diodes Inc. Supplier SPN: B360A-FDICT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [B360A-13-F — DigiKey.com](https://www.digikey.com/en/products/detail/diodes-incorporated/B360A-13-F/724950).

| Source attribute | Value to preserve |
|---|---|
| Current - Reverse Leakage @ Vr | 500 µA @ 60 V |
| Capacitance @ Vr, F | 200pF @ 4V, 1MHz |
| Grade | Automotive |
| Qualification | AEC-Q101 |
| Technology | Schottky |
| Mounting Type | Surface Mount |
| Voltage - DC Reverse (Vr) (Max) | 60 V |
| Package / Case | DO-214AC, SMA |
| Current - Average Rectified (Io) | 3A |
| Supplier Device Package | SMA |
| Voltage - Forward (Vf) (Max) @ If | 700 mV @ 3 A |
| Operating Temperature - Junction | -55°C ~ 150°C |
| Speed | Fast Recovery =< 500ns, > 200mA (Io) |

Review: Temperature is junction temperature. Leakage conditions 500 µA at 60 V; capacitance 200 pF at 4 V, 1 MHz. Do not relabel these as unconditional values.

Image: [downloaded product image](images/20.jpg). Datasheet: linked on source page; download pending.

### 21. OSTYC022150

Manufacturer: On Shore Technology Inc.. Supplier SPN: ED2902-ND. Packaging: Bulk. Status: Active.

Source: [OSTYC022150 — DigiKey.com](https://www.digikey.com/en/products/detail/on-shore-technology-inc/OSTYC022150/1588994).

| Source attribute | Value to preserve |
|---|---|
| Mounting Type | Through Hole |
| Wire Termination | Screw - Rising Cage Clamp |
| Series | OSTYC |
| Features | Interlocking (Side) |
| Color | Green |
| Operating Temperature | -30°C ~ 105°C |
| Number of Levels | 1 |
| Housing Material | Thermoplastic |
| Positions Per Level | 2 |
| Contact Material - Plating | Brass |
| Pitch | 0.200" (5.08mm) |
| Clamp Material - Plating | Brass |
| Mating Orientation | Horizontal with Board |
| Screw Material - Plating | Steel - Zinc Plated |
| Current | 10 A |
| Torque - Screw | 0.4 Nm (3.5 Lb-In) |
| Voltage | 300 V |
| Screw Thread | M2.5 |
| Wire Gauge | 16-26 AWG |

Image: [downloaded product image](images/21.jpg). Datasheet: linked on source page; download pending.

### 22. CRG0603F2K0

Manufacturer: TE Connectivity. Supplier SPN: 1712-CRG0603F2K0CT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [CRG0603F2K0 — DigiKey.com](https://www.digikey.com/en/products/detail/te-connectivity-passive-product/CRG0603F2K0/2380757).

| Source attribute | Value to preserve |
|---|---|
| Temperature Coefficient | ±100ppm/°C |
| Operating Temperature | -55°C ~ 155°C |
| Series | CRG, Neohm |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Resistance | 2 kOhms |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Tolerance | ±1% |
| Number of Terminations | 2 |
| Power (Watts) | 0.1W, 1/10W |
| Composition | Thick Film |

Review: Proposed replacement for RC0603FR-072KL; same nominal value/package, not a confirmed design substitution.

Image: [downloaded product image](images/22.jpg). Datasheet: linked on source page; download pending.

### 23. CRG0603F10K/10

Manufacturer: TE Connectivity. Supplier SPN: A121523CT-ND. Packaging: Cut Tape (CT). Status: Active.

Source: [CRG0603F10K/10 — DigiKey.com](https://www.digikey.com/en/products/detail/te-connectivity-passive-product/CRG0603F10K-10/2390661).

| Source attribute | Value to preserve |
|---|---|
| Temperature Coefficient | ±100ppm/°C |
| Operating Temperature | -55°C ~ 155°C |
| Series | CRG, Neohm |
| Package / Case | 0603 (1608 Metric) |
| Supplier Device Package | 0603 |
| Size / Dimension | 0.063" L x 0.031" W (1.60mm x 0.80mm) |
| Resistance | 10 kOhms |
| Height - Seated (Max) | 0.022" (0.55mm) |
| Tolerance | ±1% |
| Number of Terminations | 2 |
| Power (Watts) | 0.1W, 1/10W |
| Composition | Thick Film |

Review: Proposed replacement for RC0603FR-0710KL; same nominal value/package, not a confirmed design substitution.

Image: [downloaded product image](images/23.jpg). Datasheet: linked on source page; download pending.
