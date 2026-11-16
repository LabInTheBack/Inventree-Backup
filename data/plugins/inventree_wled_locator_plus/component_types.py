"""Reviewed component-family scopes, independent of database IDs and hardware.

Paths reflect the warehouse taxonomy. Match exact paths and descendants only;
missing categories produce no matches rather than a broader keyword search.
"""

import re
from dataclasses import dataclass

from .voice_requests import FAMILY_LOOKUP, FAMILY_PATTERN


CATEGORY_PATHS = {
    "resistor": ("Electronics/Passives/Resistors",),
    "capacitor": ("Electronics/Passives/Capacitors",),
    "inductor": ("Electronics/Passives/Inductors",),
    "MOSFET": ("Electronics/Transistors/MOSFET",),
    "transistor": ("Electronics/Transistors",),
    "diode": ("Electronics/Diodes", "Electronics/Protection/TVS Diodes"),
    "LED": ("Electronics/Diodes/LEDs",),
    "DC motor": ("Electronics/Motors/Brushed DC Motors", "Electronics/Motors/DC Gear Motors",
                 "Electronics/Motors/DC Motors", "Electronics/Transducers/Vibration Motors"),
    "motor": ("Electronics/Motors", "Electronics/Transducers/Vibration Motors"),
    "O-ring": ("Mechanical/O-Rings",),
    "tape": ("Mechanical/Tools & Consumables/Adhesive Tapes",
             "Mechanical/Tools & Consumables/Electrical Insulation Tapes",
             "Mechanical/Tools & Consumables/Thread Seal Tapes"),
    "adhesive tape": ("Mechanical/Tools & Consumables/Adhesive Tapes",),
    "screw": ("Mechanical/Fasteners/Screws",),
    "nut": ("Mechanical/Fasteners/Hex Nuts",),
    "connector": ("Electronics/Connectors",),
    "fuse": ("Electronics/Protection/Fuses",),
    "bearing": ("Mechanical/Bearings",),
    "ball bearing": ("Mechanical/Bearings",),
    "magnet": ("Mechanical/Magnets",),
    # These families currently have no category. Keep an explicit empty result,
    # including if related charger ICs, relay boards or holders have keywords.
    "battery": ("Electronics/Batteries",),
    "relay": ("Electronics/Relays",),
    "washer": ("Mechanical/Fasteners/Washers",),
}

# Such requests describe a different object or a relationship. Keep the complete
# text and report that no component-family scope could be safely applied.
RELATED_OBJECT = re.compile(
    r"\b(?:for|charging|supplies|accessories|(?:driver|charger|monitor|sensor|holder|tester|kit|adapter|"
    r"socket|mount|controller|module|board|supply|replacement|accessory)s?)\b", re.I)


@dataclass(frozen=True)
class ComponentType:
    name: str
    paths: tuple[str, ...]
    remaining: str
    excluded_paths: tuple[str, ...] = ()

    def public(self):
        return {"name": self.name, "categories": list(self.paths), "excluded_categories": list(self.excluded_paths)}


def component_type(query):
    """Recognize one explicit family; never infer one from a value or identifier."""
    families = list(FAMILY_PATTERN.finditer(query))
    if len(families) != 1 or RELATED_OBJECT.search(query):
        return None
    match = families[0]
    if ((match.start() and query[match.start() - 1] in "-_")
            or (match.end() < len(query) and query[match.end()] in "-_")):
        return None
    family = FAMILY_LOOKUP[match.group().casefold()]
    if family not in CATEGORY_PATHS:
        return None
    remaining = query[:match.start()] + " " + query[match.end():]
    paths = CATEGORY_PATHS[family]
    excluded = ()
    if family == "resistor":
        variable = "Electronics/Passives/Resistors/Variable"
        if re.search(r"\b(?:variable|adjustable)\b", remaining, re.I):
            family, paths = "variable resistor", (variable,)
            remaining = re.sub(r"\b(?:variable|adjustable)\b", " ", remaining, flags=re.I)
        else:
            excluded = (variable,)
    if family == "transistor":
        polarities = set(re.findall(r"\b(?:PNP|NPN)\b", remaining, re.I))
        polarities = {word.upper() for word in polarities}
        if len(polarities) == 1:
            polarity = polarities.pop()
            family = polarity + " transistor"
            paths = ("Electronics/Transistors/BJT/" + polarity,)
            remaining = re.sub(r"\b" + polarity + r"\b", " ", remaining, flags=re.I)
    if family == "ball bearing":
        remaining += " ball"
    return ComponentType(family, paths, " ".join(remaining.split()), excluded)
