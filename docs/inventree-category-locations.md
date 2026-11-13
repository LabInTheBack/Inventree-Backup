# InvenTree Categories and Storage Locations

Snapshot generated from the live InvenTree database on 2026-11-09. The entries
were not refreshed during documentation consolidation on 2026-11-11.

This snapshot maps each category to locations where its parts currently have positive on-hand stock. Catalog default locations are shown separately. Categories with no directly assigned parts remain listed. Physical labels are included from location descriptions when recorded; the InvenTree location path remains the location identifier.

Use [warehouse.md](warehouse.md) for entry and storage rules and
[the documentation index](../README.md) for the other guides. This is a dated
reference, not current operating instructions or a substitute for checking live
stock and physical capacity. If regenerated, query the database read-only and
update the snapshot date; do not hand-edit counts to imply a database refresh.

## Category-to-location index

| Category path | Catalog parts | Stocked parts / stock lines | On-hand stock location(s) | Default location(s) |
|---|---:|---:|---|---|
| `Electronics` | 0 | 0 / 0 | — | — |
| `Electronics/Actuators` | 0 | 0 / 0 | — | — |
| `Electronics/Actuators/Solenoids` | 3 | 3 / 3 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-05` | — |
| `Electronics/Audio` | 0 | 0 / 0 | — | — |
| `Electronics/Audio/Microphones` | 0 | 0 / 0 | — | — |
| `Electronics/Audio/Microphones/MEMS Microphones` | 4 | 0 / 0 | — | — |
| `Electronics/Connectors` | 0 | 0 / 0 | — | — |
| `Electronics/Connectors/Circular Connector Adapters` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-06` — Physical box label: Industrial Connectors | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-06` — Physical box label: Industrial Connectors |
| `Electronics/Connectors/Circular Connectors` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-06` — Physical box label: Industrial Connectors | — |
| `Electronics/Connectors/D-Sub Adapters` | 2 | 2 / 2 | `Berlin Home/Cabinet-01/Row-06/Drawer-02` | `Berlin Home/Cabinet-01/Row-06/Drawer-02` |
| `Electronics/Connectors/D-Sub Connectors` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-06/Drawer-02` | `Berlin Home/Cabinet-01/Row-06/Drawer-02` |
| `Electronics/Connectors/FFC FPC` | 0 | 0 / 0 | — | — |
| `Electronics/Connectors/JST` | 0 | 0 / 0 | — | — |
| `Electronics/Connectors/Jumpers` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-02/Drawer-05` | — |
| `Electronics/Connectors/Pin Headers` | 2 | 2 / 2 | `Berlin Home/Cabinet-01/Row-01/Drawer-05`<br>`Berlin Home/Cabinet-01/Row-02/Drawer-01` | — |
| `Electronics/Connectors/RF` | 0 | 0 / 0 | — | — |
| `Electronics/Connectors/Terminal Blocks` | 8 | 8 / 8 | `Berlin Home/Cabinet-01/Row-02/Drawer-05`<br>`Berlin Home/Cabinet-01/Row-05/Drawer-04`<br>`Berlin Home/Cabinet-01/Row-10/Drawer-04` | — |
| `Electronics/Connectors/Test Probes` | 3 | 3 / 3 | `Berlin Home/Cabinet-01/Row-06/Drawer-01` | — |
| `Electronics/Connectors/USB` | 2 | 2 / 2 | `Berlin Home/Cabinet-01/Row-03/Drawer-01` | — |
| `Electronics/Connectors/Wire Ferrules` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-05/Drawer-04` | — |
| `Electronics/Diodes` | 0 | 0 / 0 | — | — |
| `Electronics/Diodes/Bridge Rectifiers` | 0 | 0 / 0 | — | — |
| `Electronics/Diodes/LEDs` | 0 | 0 / 0 | — | — |
| `Electronics/Diodes/LEDs/Infrared LEDs` | 4 | 4 / 4 | `Berlin Home/Cabinet-02/Row-06/Drawer-04` | — |
| `Electronics/Diodes/LEDs/Visible LEDs` | 5 | 5 / 5 | `Berlin Home/Cabinet-01/Row-03/Drawer-02`<br>`Berlin Home/Cabinet-01/Row-05/Drawer-05` | — |
| `Electronics/Diodes/Rectifier Diodes` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-10/Drawer-02` | — |
| `Electronics/Diodes/Schottky` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-10/Drawer-02` | — |
| `Electronics/Diodes/Signal` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-10/Drawer-02` | — |
| `Electronics/Diodes/Zener` | 4 | 4 / 4 | `Berlin Home/Cabinet-01/Row-10/Drawer-01` | — |
| `Electronics/Frequency Control` | 0 | 0 / 0 | — | — |
| `Electronics/Frequency Control/Crystals & Resonators` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-05/Drawer-02` | — |
| `Electronics/ICs` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/ADCs` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-05/Drawer-01` | — |
| `Electronics/ICs/Analog Switches` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-06/Drawer-01` | — |
| `Electronics/ICs/Comparators` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-03/Drawer-03` | — |
| `Electronics/ICs/Interface ICs` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/I/O Expanders` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-06/Drawer-01` | — |
| `Electronics/ICs/Isolation` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/Isolation/Isolated Amplifiers` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-05/Drawer-03` | — |
| `Electronics/ICs/Isolation/Optocouplers` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-05/Drawer-03` | — |
| `Electronics/ICs/Isolation/Transformer Drivers` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-05/Drawer-03` | — |
| `Electronics/ICs/Logic ICs` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-03/Drawer-04` | — |
| `Electronics/ICs/Memory` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/Microcontrollers` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/Motor Drivers` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-04/Drawer-04` | — |
| `Electronics/ICs/Op Amps` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-03/Drawer-01`<br>`Berlin Home/Cabinet-02/Row-03/Drawer-02` | — |
| `Electronics/ICs/Power Management (PMIC)` | 0 | 0 / 0 | — | — |
| `Electronics/ICs/Power Management (PMIC)/Battery Chargers` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-04/Drawer-05` | — |
| `Electronics/ICs/Power Management (PMIC)/Battery Monitors & Fuel Gauges` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-04/Drawer-05` | — |
| `Electronics/ICs/Power Management (PMIC)/DC-DC Converters` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-04/Drawer-02` | — |
| `Electronics/ICs/Power Management (PMIC)/Gate Drivers` | 4 | 4 / 4 | `Berlin Home/Cabinet-02/Row-03/Drawer-05` | — |
| `Electronics/ICs/Power Management (PMIC)/Power Switches & Load Drivers` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-05/Drawer-04` | — |
| `Electronics/ICs/Power Management (PMIC)/USB PD Controllers` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-05/Drawer-05` | — |
| `Electronics/ICs/Power Management (PMIC)/Voltage Regulators` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-04/Drawer-01` | — |
| `Electronics/ICs/Timers` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-05/Drawer-02` | — |
| `Electronics/Magnetic Reed Switches` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-01` | — |
| `Electronics/Mechanical Switches` | 0 | 0 / 0 | — | — |
| `Electronics/Mechanical Switches/DIP` | 0 | 0 / 0 | — | — |
| `Electronics/Mechanical Switches/Limit Switches` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02` | — |
| `Electronics/Mechanical Switches/Push Button` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02` | — |
| `Electronics/Mechanical Switches/Rotary` | 0 | 0 / 0 | — | — |
| `Electronics/Mechanical Switches/Slide` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-02/Drawer-04` | — |
| `Electronics/Mechanical Switches/Tactile` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-02/Drawer-03` | — |
| `Electronics/Mechanical Switches/Toggle` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02` | — |
| `Electronics/Modules` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Actuator Driver Modules` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Audio Modules` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Audio Modules/Audio Amplifier Modules` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-08/Drawer-02` | — |
| `Electronics/Modules/Audio Modules/Buzzer Modules` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-08/Drawer-02` | — |
| `Electronics/Modules/Audio Modules/Microphone Modules` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-08/Drawer-02` | — |
| `Electronics/Modules/Development Boards` | 10 | 10 / 10 | `Berlin Home/Cabinet-02/Row-09/Drawer-03` | — |
| `Electronics/Modules/Display Modules` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-09/Drawer-01` | — |
| `Electronics/Modules/Expansion Boards` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-01/Drawer-02` | — |
| `Electronics/Modules/Motor Driver Modules` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-04/Drawer-04` | — |
| `Electronics/Modules/Power Modules` | 10 | 10 / 10 | `Berlin Home/Cabinet-02/Row-04/Drawer-03`<br>`Berlin Home/Cabinet-02/Row-09/Drawer-02` | — |
| `Electronics/Modules/PWM Controller Modules` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-08/Drawer-04`<br>`Berlin Home/Shelves for S-Boxes/Shelf-03/Box-03` | — |
| `Electronics/Modules/Radio Modules` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-08/Drawer-05` | — |
| `Electronics/Modules/Sensor Modules` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Sensor Modules/Environmental` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Sensor Modules/Environmental/Air Quality & Gas` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-07/Drawer-04` | — |
| `Electronics/Modules/Sensor Modules/Environmental/Humidity & Temperature` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-07/Drawer-04` | — |
| `Electronics/Modules/Sensor Modules/Environmental/Pressure & Altitude` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-04` | — |
| `Electronics/Modules/Sensor Modules/Magnetic & Hall` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-01` | — |
| `Electronics/Modules/Sensor Modules/Motion` | 0 | 0 / 0 | — | — |
| `Electronics/Modules/Sensor Modules/Motion/Accelerometers` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-07/Drawer-05` | — |
| `Electronics/Modules/Sensor Modules/Motion/IMUs` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-05` | — |
| `Electronics/Modules/Sensor Modules/Motion/Microwave Radar` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-08/Drawer-01` | — |
| `Electronics/Modules/Sensor Modules/Optical & Proximity` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-08/Drawer-01` | — |
| `Electronics/Motors` | 0 | 0 / 0 | — | — |
| `Electronics/Motors/Brushed DC Motors` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-02` | — |
| `Electronics/Motors/DC Gear Motors` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-02` | — |
| `Electronics/Motors/DC Motors` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-02` | — |
| `Electronics/Motors/Servo Motors` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-04` | — |
| `Electronics/Motors/Stepper Motors` | 7 | 7 / 8 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-01` | — |
| `Electronics/Passives` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Capacitors` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Capacitors/Ceramic` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Capacitors/Electrolytic` | 16 | 16 / 16 | `Berlin Home/Cabinet-01/Row-09/Drawer-01` | — |
| `Electronics/Passives/Capacitors/Film` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Capacitors/Supercapacitors` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-09/Drawer-01` | — |
| `Electronics/Passives/Capacitors/Tantalum` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Inductors` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Inductors/Chokes` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Inductors/Ferrite Beads` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Inductors/Power Inductors` | 15 | 15 / 15 | `Berlin Home/Cabinet-01/Row-05/Drawer-01` | — |
| `Electronics/Passives/Resistors` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Resistors/Arrays` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Resistors/Chassis Mount Resistors` | 2 | 2 / 2 | `Berlin Home/Cabinet-01/Row-04/Drawer-04` | — |
| `Electronics/Passives/Resistors/Fixed` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-05/Drawer-03` | — |
| `Electronics/Passives/Resistors/Shunts` | 0 | 0 / 0 | — | — |
| `Electronics/Passives/Resistors/Variable` | 7 | 7 / 7 | `Berlin Home/Cabinet-01/Row-04/Drawer-05`<br>`Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02` | — |
| `Electronics/PCB` | 7 | 7 / 7 | `Berlin Home/Cabinet-01/Row-05/Drawer-02` | — |
| `Electronics/PCBA` | 0 | 0 / 0 | — | — |
| `Electronics/Protection` | 0 | 0 / 0 | — | — |
| `Electronics/Protection/ESD Protection` | 0 | 0 / 0 | — | — |
| `Electronics/Protection/Fuses` | 3 | 3 / 3 | `Berlin Home/Cabinet-01/Row-03/Drawer-03` | — |
| `Electronics/Protection/Inrush Current Limiters` | 3 | 3 / 3 | `Berlin Home/Cabinet-01/Row-03/Drawer-04` | — |
| `Electronics/Protection/PTC Resettable` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-03/Drawer-03` | — |
| `Electronics/Protection/TVS Diodes` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-10/Drawer-01` | — |
| `Electronics/Protection/Varistors` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Accessories` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Accessories/Sensor Filter Caps` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-03` | — |
| `Electronics/Sensors/Accessories/Sensor Lenses` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-06/Drawer-05` | — |
| `Electronics/Sensors/Current Voltage` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Gas` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Humidity` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-07/Drawer-03` | — |
| `Electronics/Sensors/Light Optical` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Light Optical/Ambient Light Sensors` | 2 | 1 / 1 | `Berlin Home/Cabinet-02/Row-06/Drawer-02` | — |
| `Electronics/Sensors/Light Optical/IR Receivers` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-06/Drawer-03` | — |
| `Electronics/Sensors/Light Optical/Photodiodes` | 5 | 5 / 5 | `Berlin Home/Cabinet-02/Row-06/Drawer-02`<br>`Berlin Home/Cabinet-02/Row-06/Drawer-03` | — |
| `Electronics/Sensors/Light Optical/Phototransistors` | 3 | 3 / 3 | `Berlin Home/Cabinet-02/Row-06/Drawer-02` | — |
| `Electronics/Sensors/Motion Sensors` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Motion Sensors/IMU` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Motion Sensors/PIR Sensors` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-06/Drawer-05` | — |
| `Electronics/Sensors/Position, Proximity & Touch` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Position, Proximity & Touch/Capacitive` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Position, Proximity & Touch/Distance Proximity` | 0 | 0 / 0 | — | — |
| `Electronics/Sensors/Position, Proximity & Touch/Inductive` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-01` | — |
| `Electronics/Sensors/Position, Proximity & Touch/Magnetic Hall` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-01` | — |
| `Electronics/Sensors/Pressure` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-03` | — |
| `Electronics/Sensors/Temperature` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-03` | — |
| `Electronics/Storage Media` | 0 | 0 / 0 | — | — |
| `Electronics/Storage Media/Card Adapters` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-01/Drawer-01` | — |
| `Electronics/Storage Media/Memory Cards` | 7 | 7 / 7 | `Berlin Home/Cabinet-01/Row-01/Drawer-01` | — |
| `Electronics/Thermal Interface Materials` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` |
| `Electronics/Transducers` | 0 | 0 / 0 | — | — |
| `Electronics/Transducers/Beepers & Buzzers` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-10/Drawer-03` | `Berlin Home/Cabinet-01/Row-10/Drawer-03` |
| `Electronics/Transducers/Load Cells` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-04/Drawer-02` | — |
| `Electronics/Transducers/Piezo Drivers` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-05/Box-02` — Physical box label: Humidifier Components | `Berlin Home/Shelves for S-Boxes/Shelf-05/Box-02` — Physical box label: Humidifier Components |
| `Electronics/Transducers/Piezoelectric Elements` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-07/Drawer-02` | — |
| `Electronics/Transducers/Speakers` | 5 | 5 / 5 | `Berlin Home/Cabinet-01/Row-04/Drawer-03`<br>`Berlin Home/Cabinet-01/Row-10/Drawer-03` | `Berlin Home/Cabinet-01/Row-10/Drawer-03` |
| `Electronics/Transducers/Thermoelectric Modules` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-04/Drawer-01` | — |
| `Electronics/Transducers/Vibration Motors` | 2 | 2 / 2 | `Berlin Home/Cabinet-01/Row-03/Drawer-05` | — |
| `Electronics/Transformers` | 0 | 0 / 0 | — | — |
| `Electronics/Transformers/SMPS Transformers` | 1 | 1 / 1 | `Berlin Home/Cabinet-02/Row-05/Drawer-03` | — |
| `Electronics/Transistors` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/BJT` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/BJT/NPN` | 8 | 8 / 8 | `Berlin Home/Cabinet-02/Row-01/Drawer-01`<br>`Berlin Home/Cabinet-02/Row-01/Drawer-02`<br>`Berlin Home/Cabinet-02/Row-01/Drawer-04` | `Berlin Home/Cabinet-02/Row-01/Drawer-01`<br>`Berlin Home/Cabinet-02/Row-01/Drawer-02` |
| `Electronics/Transistors/BJT/PNP` | 6 | 6 / 6 | `Berlin Home/Cabinet-02/Row-01/Drawer-03`<br>`Berlin Home/Cabinet-02/Row-01/Drawer-05` | `Berlin Home/Cabinet-02/Row-01/Drawer-03` |
| `Electronics/Transistors/IGBT` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/JFET` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/JFET/N-Channel` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/JFET/P-Channel` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/MOSFET` | 0 | 0 / 0 | — | — |
| `Electronics/Transistors/MOSFET/N-Channel` | 7 | 7 / 7 | `Berlin Home/Cabinet-02/Row-02/Drawer-01`<br>`Berlin Home/Cabinet-02/Row-02/Drawer-03`<br>`Berlin Home/Cabinet-02/Row-02/Drawer-05` | — |
| `Electronics/Transistors/MOSFET/P-Channel` | 2 | 2 / 2 | `Berlin Home/Cabinet-02/Row-02/Drawer-02`<br>`Berlin Home/Cabinet-02/Row-02/Drawer-04` | — |
| `Electronics/Wire` | 0 | 0 / 0 | — | — |
| `Manufactured - Wood` | 0 | 0 / 0 | — | — |
| `Mechanical` | 0 | 0 / 0 | — | — |
| `Mechanical/3D Printer Parts & Accessories` | 0 | 0 / 0 | — | — |
| `Mechanical/3D Printer Parts & Accessories/Hotend Parts` | 3 | 3 / 3 | `Berlin Home/Cabinet-01/Row-01/Drawer-02`<br>`Berlin Home/Cabinet-01/Row-01/Drawer-03` | — |
| `Mechanical/3D Printer Parts & Accessories/Maintenance Tools` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-01/Drawer-03` | — |
| `Mechanical/3D Printer Parts & Accessories/Nozzles` | 5 | 5 / 5 | `Berlin Home/Cabinet-01/Row-01/Drawer-02`<br>`Berlin Home/Cabinet-01/Row-01/Drawer-03` | — |
| `Mechanical/3D Printer Parts & Accessories/Printer Hardware` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-01/Drawer-02` | — |
| `Mechanical/Bearings` | 9 | 9 / 9 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-02`<br>`Berlin Home/Shelves for S-Boxes/Shelf-01/Box-03` | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02`<br>`Berlin Home/Shelves for S-Boxes/Shelf-02/Box-03` |
| `Mechanical/Board Spacers & Standoffs` | 7 | 7 / 7 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-07` | — |
| `Mechanical/Cable Management` | 0 | 0 / 0 | — | — |
| `Mechanical/Cable Management/Heat Shrink Tubing` | 1 | 1 / 1 | `Berlin Home/Cabinet-01/Row-01/Drawer-04` | — |
| `Mechanical/Cables` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-05` | — |
| `Mechanical/Cams & Eccentrics` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-06` | — |
| `Mechanical/Fasteners` | 0 | 0 / 0 | — | — |
| `Mechanical/Fasteners/Hex Nuts` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-07` | — |
| `Mechanical/Fasteners/Screw Hooks` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-05` | — |
| `Mechanical/Fasteners/Screws` | 3 | 3 / 3 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-07` | — |
| `Mechanical/Fasteners/Screws/Set Screws` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-07` | — |
| `Mechanical/Fasteners/Screws/Thumb Screws` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-07` | — |
| `Mechanical/Fasteners/Thread Inserts` | 5 | 5 / 7 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-04` | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-04` |
| `Mechanical/Knobs` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-02` | — |
| `Mechanical/Magnets` | 4 | 4 / 4 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-03` | — |
| `Mechanical/O-Rings` | 12 | 12 / 12 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-01` | — |
| `Mechanical/Pins & Dowels` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-04` | — |
| `Mechanical/Pulleys` | 6 | 6 / 6 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-05` | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-05` |
| `Mechanical/Pumps` | 0 | 0 / 0 | — | — |
| `Mechanical/Pumps/Diaphragm Pumps` | 4 | 4 / 4 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-03` | — |
| `Mechanical/Pumps/Peristaltic Pumps` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-03` | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-03` |
| `Mechanical/Rods & Bars` | 5 | 5 / 5 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-04`<br>`Berlin Home/Shelves for S-Boxes/Shelf-01/OS-Obj` | — |
| `Mechanical/Rollers` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-01` | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-01` |
| `Mechanical/Shaft Collars` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-06` | — |
| `Mechanical/Shaft Couplings` | 3 | 3 / 3 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-06` | — |
| `Mechanical/Springs` | 0 | 0 / 0 | — | — |
| `Mechanical/Springs/Compression Springs` | 8 | 8 / 8 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-07` | — |
| `Mechanical/Timing Belts` | 3 | 3 / 3 | `Berlin Home/Shelves for S-Boxes/Shelf-01/Box-05` | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-05` |
| `Mechanical/Tools & Consumables` | 0 | 0 / 0 | — | — |
| `Mechanical/Tools & Consumables/Adhesive Applicators` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-02` | — |
| `Mechanical/Tools & Consumables/Adhesive Tapes` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals |
| `Mechanical/Tools & Consumables/Adhesives` | 7 | 7 / 7 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-02`<br>`Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` |
| `Mechanical/Tools & Consumables/Coatings & Varnishes` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-04` |
| `Mechanical/Tools & Consumables/Electrical Insulation Tapes` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals |
| `Mechanical/Tools & Consumables/Humidifier Wicks` | 5 | 5 / 5 | `Berlin Home/Shelves for S-Boxes/Shelf-05/Box-02` — Physical box label: Humidifier Components | `Berlin Home/Shelves for S-Boxes/Shelf-05/Box-02` — Physical box label: Humidifier Components |
| `Mechanical/Tools & Consumables/Lubricants` | 5 | 5 / 5 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-03` | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-03` |
| `Mechanical/Tools & Consumables/Resins` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-02` | — |
| `Mechanical/Tools & Consumables/Sealing Plugs` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals |
| `Mechanical/Tools & Consumables/Sealing Strips` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals |
| `Mechanical/Tools & Consumables/Soldering Accessories` | 3 | 3 / 3 | `Berlin Home/Cabinet-01/Row-02/Drawer-02`<br>`Berlin Home/Shelves for S-Boxes/Shelf-04/Box-05` — Physical box label: Soldering | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-05` — Physical box label: Soldering |
| `Mechanical/Tools & Consumables/Thread Seal Tapes` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-07` — Physical box label: Tapes & Seals |
| `Mechanical/Wire Rope Fittings` | 6 | 6 / 6 | `Berlin Home/Shelves for S-Boxes/Shelf-02/Box-05` | `Berlin Home/Shelves for S-Boxes/Shelf-03/Box-05` |
| `Medical & Laboratory Supplies` | 0 | 0 / 0 | — | — |
| `Medical & Laboratory Supplies/ECG Electrodes` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-01` | — |
| `Medical & Laboratory Supplies/Needles` | 1 | 1 / 1 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-01` | — |
| `Medical & Laboratory Supplies/Syringes` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-04/Box-01` | — |
| `Unsorted Salvage` | 2 | 2 / 2 | `Berlin Home/Shelves for S-Boxes/Shelf-05/Box-01` — Physical box label: Unsorted Salvage | — |

## Reading this index

- Counts are for direct assignments to that exact category; parent categories do not inherit child counts.
- “Stocked parts / stock lines” counts distinct parts and positive-quantity stock records, not the total quantity across unlike units.
- An on-hand location marked `Unlocated` means the stock record has no location assigned.
- A default location is a part-level fallback and may differ from the location of existing stock.

