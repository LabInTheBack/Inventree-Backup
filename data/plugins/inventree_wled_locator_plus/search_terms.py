"""Conservative component-value parsing, independent of Django and inventory."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext

# Prefix case is significant: M is mega, m is milli. Words may use any case.
PREFIXES = {"": 0, "p": -12, "n": -9, "u": -6, "µ": -6, "μ": -6, "m": -3, "k": 3, "K": 3, "M": 6}
SPECS = {
    "resistance": {"symbol": "Ω", "template": "Resistance", "prefixes": ("m", "", "k", "M"),
                   "word": "ohm", "family": r"resistors?|potentiometers?|rheostats?|thermistors?"},
    "capacitance": {"symbol": "F", "template": "Capacitance", "prefixes": ("p", "n", "u", "m", ""),
                    "word": "farad", "family": r"capacitors?"},
    "inductance": {"symbol": "H", "template": "Inductance", "prefixes": ("n", "u", "m", ""),
                   "word": "henry", "family": r"inductors?|chokes?"},
}
PREFIX_WORDS = {"": "", "p": "pico", "n": "nano", "u": "micro", "m": "milli", "k": "kilo", "M": "mega"}
BOUNDARY_CHARS = "A-Za-z0-9_.µμΩΩ"


def insensitive_word(word):
    return "".join(f"[{char.lower()}{char.upper()}]" if char.isalpha() and char.isascii() else re.escape(char) for char in word)


def unit_aliases(kind, prefix):
    spec = SPECS[kind]
    symbols = {"": [""], "u": ["u", "µ", "μ"], "k": ["k", "K"]}.get(prefix, [prefix])
    suffixes = ["Ω", "Ω", "ω"] if kind == "resistance" else [spec["symbol"], spec["symbol"].lower()]
    aliases = [symbol + suffix for symbol in symbols for suffix in suffixes]
    word = PREFIX_WORDS[prefix] + spec["word"]
    aliases.extend([word, word + ("ies" if word.endswith("henry") else "s")])
    if word.endswith("henry"):
        aliases[-1] = word[:-1] + "ies"
    if kind == "resistance":
        aliases.extend(symbol + "ohm" for symbol in symbols)
        aliases.extend(symbol + "ohms" for symbol in symbols)
        if prefix == "k":
            aliases.extend(["kilohm", "kilohms"])
        if prefix == "M":
            aliases.extend(["megohm", "megohms"])
    return list(dict.fromkeys(aliases))


def unit_pattern(alias):
    short_word = re.fullmatch(r"([mMkK])(ohms?)", alias)
    if short_word:
        marker, word = short_word.groups()
        return ("[kK]" if marker in "kK" else marker) + r"\s*" + insensitive_word(word)
    for prefix in ("pico", "nano", "micro", "milli", "kilo", "mega"):
        if alias.startswith(prefix):
            return insensitive_word(prefix) + r"\s*" + insensitive_word(alias[len(prefix):])
    if len(alias) == 2 and alias[0] in PREFIXES:
        return re.escape(alias[0]) + r"\s*" + re.escape(alias[1])
    return insensitive_word(alias) if len(alias) > 2 and alias.isascii() else re.escape(alias)


UNIT_LOOKUP = {}
for _kind, _spec in SPECS.items():
    for _prefix in _spec["prefixes"]:
        for _alias in unit_aliases(_kind, _prefix):
            UNIT_LOOKUP[_alias] = (_kind, PREFIXES[_prefix])
WORD_LOOKUP = {alias.casefold(): info for alias, info in UNIT_LOOKUP.items() if len(alias) > 2 and alias.isascii() and alias.isalpha() and alias.lower().endswith(("ohm", "ohms", "farad", "farads", "henry", "henries"))}

NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
EMBEDDED = r"(?:\d*[RrKkMm]\d+)"
UNIT_PATTERN = "|".join(unit_pattern(alias) for alias in sorted(UNIT_LOOKUP, key=len, reverse=True))
EXPLICIT = re.compile(rf"(?<![{BOUNDARY_CHARS}+\-])(?P<number>{NUMBER}|{EMBEDDED})\s*(?P<unit>{UNIT_PATTERN})(?![{BOUNDARY_CHARS}+\-])", re.IGNORECASE)
BARE = re.compile(rf"(?<![{BOUNDARY_CHARS}+\-])(?:{EMBEDDED}|{NUMBER}[RrKkMmnuµμp])(?![{BOUNDARY_CHARS}+\-])")


def unit_info(unit):
    # Canonicalize only the unit letter and micro sign; never fold prefix M/m.
    unit = re.sub(r"\s+", "", unit)
    unit = unit.replace("Ω", "Ω").replace("ω", "Ω").replace("µ", "μ")
    if unit.endswith(("f", "h")):
        unit = unit[:-1] + unit[-1].upper()
    if unit in UNIT_LOOKUP:
        return UNIT_LOOKUP[unit]
    abbreviated = re.fullmatch(r"([pnuμmkKM]?)(ohms?|farads?|henry|henries)", unit, re.IGNORECASE)
    if abbreviated:
        prefix, suffix = abbreviated.groups()
        prefix = "u" if prefix == "μ" else "k" if prefix == "K" else prefix
        kind = "resistance" if suffix.lower().startswith("ohm") else "capacitance" if suffix.lower().startswith("farad") else "inductance"
        if prefix in SPECS[kind]["prefixes"]:
            return kind, PREFIXES[prefix]
        return None
    return WORD_LOOKUP.get(unit.casefold())


def number_value(text, kind):
    embedded = re.fullmatch(r"(\d*)([RrKkMm])(\d+)", text)
    if embedded:
        if kind != "resistance":
            raise ValueError("Embedded resistance notation requires a resistor context")
        whole, marker, fraction = embedded.groups()
        exponent = 0 if marker in "Rr" else PREFIXES[marker]
        return Decimal(f"{whole or '0'}.{fraction}") * Decimal(10) ** exponent
    return Decimal(text)


def decimal_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def number_pattern(value):
    text = decimal_text(value)
    if "." in text:
        whole, fraction = text.split(".")
        return ("0*" if whole == "0" else "0*" + whole) + r"\." + fraction + "0*"
    return "0*" + text + r"(?:\.0+)?"


@dataclass(frozen=True)
class ValueSearch:
    kind: str
    value: Decimal
    terms: tuple[str, ...]
    require_family: bool

    @property
    def family_pattern(self):
        return rf"(^|[^A-Za-z0-9_])({SPECS[self.kind]['family']})([^A-Za-z0-9_]|$)"

    @property
    def display(self):
        if self.value:
            for prefix in reversed(SPECS[self.kind]["prefixes"]):
                amount = self.value / Decimal(10) ** PREFIXES[prefix]
                if Decimal(1) <= amount < Decimal(1000):
                    return f"{decimal_text(amount)} {'µ' if prefix == 'u' else prefix}{SPECS[self.kind]['symbol']}"
        return f"{decimal_text(self.value)} {SPECS[self.kind]['symbol']}"

    def patterns(self):
        """Portable PostgreSQL/Python regular expressions with numeric boundaries."""
        explicit, bare = [], []
        for prefix in SPECS[self.kind]["prefixes"]:
            amount = self.value / Decimal(10) ** PREFIXES[prefix]
            text = decimal_text(amount)
            if len(text) > 26:
                continue
            coefficient = number_pattern(amount)
            for alias in unit_aliases(self.kind, prefix):
                suffix = unit_pattern(alias)
                # k/K is interchangeable, while M/m retain their SI meaning.
                explicit.append(coefficient + r"\s*" + suffix)
            if prefix:
                marker = r"[kK]" if prefix == "k" else r"[uµμ]" if prefix == "u" else prefix
                bare.append(coefficient + r"\s*" + marker)
            elif self.kind == "resistance":
                bare.append(coefficient + r"\s*[Rr]")
            # Embedded decimals such as 4k7, 10k0 and 4R7 are resistance only.
            if self.kind == "resistance":
                marker = "[Rr]" if not prefix else "[kK]" if prefix == "k" else prefix
                whole, _, fraction = text.partition(".")
                embedded = "0*" + whole + marker + (fraction + "0*" if fraction else "0+")
                bare.append(embedded)
                explicit.append(embedded + r"\s*(?:Ω|Ω|ω|[oO][hH][mM][sS]?)")
        def bounded(options):
            return rf"(^|[^{BOUNDARY_CHARS}])(?:{'|'.join(options)})([^{BOUNDARY_CHARS}]|$)"
        return bounded(explicit), bounded(bare)


def parse_value_search(query):
    """Normalize one unambiguous passive value; ordinary identifiers stay literal."""
    text = unicodedata.normalize("NFKC", query)
    hints = {kind for kind, spec in SPECS.items() if re.search(rf"\b(?:{spec['family']})\b", text, re.IGNORECASE)}
    if len(hints) > 1:
        return None
    matches = list(EXPLICIT.finditer(text))
    try:
        with localcontext() as context:
            context.prec = 50
            if len(matches) == 1:
                match = matches[0]
                info = unit_info(match["unit"])
                if info is None:
                    return None
                kind, exponent = info
                raw = match["number"]
                if len(raw) > 20 or (re.search("[RrKkMm]", raw) and exponent):
                    return None
                value = number_value(raw, kind) * Decimal(10) ** exponent
            elif not matches and len(hints) == 1:
                kind = next(iter(hints))
                matches = list(BARE.finditer(text))
                if len(matches) != 1:
                    return None
                match = matches[0]
                raw = match.group()
                if len(raw) > 20:
                    return None
                if re.fullmatch(EMBEDDED, raw):
                    value = number_value(raw, kind)
                else:
                    prefix = raw[-1]
                    if prefix in "Rr":
                        if kind != "resistance": return None
                        exponent = 0
                    else:
                        prefix = "u" if prefix in "µμ" else "k" if prefix == "K" else prefix
                        if prefix not in SPECS[kind]["prefixes"]: return None
                        exponent = PREFIXES[prefix]
                    value = Decimal(raw[:-1]) * Decimal(10) ** exponent
            else:
                return None
            if hints and kind not in hints:
                return None
            if not value.is_finite() or value < 0 or value and not Decimal("1e-24") <= value <= Decimal("1e24"):
                return None
            rest = text[:match.start()] + " " + text[match.end():]
            if hints:
                rest = re.sub(rf"\b(?:{SPECS[kind]['family']})\b", " ", rest, flags=re.IGNORECASE)
            return ValueSearch(kind, value, tuple(rest.split()), bool(hints))
    except (InvalidOperation, ValueError):
        return None
