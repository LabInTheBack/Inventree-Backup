"""Small, deterministic English request interpreter; no inventory or network.

Vocabulary is intentionally finite. Unknown text and unsupported constraints stay
visible for review instead of broadening a search by guessing missing details.
"""

import re
import unicodedata

from .search_terms import parse_value_search


MAX_TEXT_LENGTH = 8192
MAX_REQUESTS = 20
INTERPRETER_VERSION = 3

FAMILIES = {
    "resistor": "resistor|resistors",
    "capacitor": "capacitor|capacitors",
    "inductor": "inductor|inductors|choke|chokes",
    "potentiometer": "potentiometer|potentiometers",
    "MOSFET": "MOSFET|MOSFETs",
    "transistor": "transistor|transistors",
    "diode": "diode|diodes",
    "LED": "LED|LEDs",
    "DC motor": "DC motor|DC motors",
    "motor": "motor|motors",
    "O-ring": "O-ring|O-rings|O ring|O rings|oring|orings",
    "tape": "tape|tapes",
    "adhesive tape": "adhesive tape|adhesive tapes",
    "screw": "screw|screws",
    "nut": "nut|nuts",
    "washer": "washer|washers",
    "connector": "connector|connectors",
    "relay": "relay|relays",
    "fuse": "fuse|fuses",
    "bearing": "bearing|bearings",
    "ball bearing": "ball bearing|ball bearings",
    "battery": "battery|batteries",
    "magnet": "magnet|magnets",
}


def alias_table(groups):
    lookup = {alias.casefold(): canonical for canonical, aliases in groups.items() for alias in aliases.split("|")}
    pattern = "|".join(re.escape(alias) for alias in sorted(lookup, key=len, reverse=True))
    return lookup, pattern


FAMILY_LOOKUP, FAMILY_ALIASES = alias_table(FAMILIES)
FAMILY_PATTERN = re.compile(rf"(?<!\w)(?:{FAMILY_ALIASES})(?!\w)", re.I)
CANONICAL_FAMILY = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in sorted(FAMILIES, key=len, reverse=True)) + r")(?!\w)", re.I)

UNIT_GROUPS = {
    "kΩ": "kilo ohm|kilo ohms|kilo-ohm|kilo-ohms|kiloohm|kiloohms|kilohm|kilohms|kOhm|kOhms",
    "MΩ": "mega ohm|mega ohms|megaohm|megaohms|megohm|megohms",
    "mΩ": "milli ohm|milli ohms|milliohm|milliohms",
    "Ω": "ohm|ohms",
    "uF": "micro farad|micro farads|micro-farad|micro-farads|microfarad|microfarads",
    "nF": "nano farad|nano farads|nanofarad|nanofarads",
    "pF": "pico farad|pico farads|picofarad|picofarads",
    "mF": "milli farad|milli farads|millifarad|millifarads",
    "F": "farad|farads",
    "uH": "micro henry|micro henries|microhenry|microhenries",
    "nH": "nano henry|nano henries|nanohenry|nanohenries",
    "mH": "milli henry|milli henries|millihenry|millihenries",
    "H": "henry|henries",
    "V": "volt|volts",
    "A": "ampere|amperes|amp|amps",
    "W": "watt|watts",
    "mm": "millimeter|millimeters|millimetre|millimetres",
    "Nm": "newton meter|newton meters|newton metre|newton metres",
}
UNIT_LOOKUP, UNIT_ALIASES = alias_table(UNIT_GROUPS)
# Unit words may follow a digit (10microfarad); they must not occur inside words.
UNIT_PATTERN = re.compile(rf"(?<![^\W\d_])(?:{UNIT_ALIASES})(?!\w)", re.I)
UNIT_START = re.compile(r"^(?:[pnumkKMµμ]?[ΩFH]|mm|Nm|[VAW%])(?=$|\W)")

WORDS = {
    "around": "around|about|approximately",
}
WORD_LOOKUP, WORD_ALIASES = alias_table(WORDS)
WORD_PATTERN = re.compile(rf"(?<!\w)(?:{WORD_ALIASES})(?!\w)", re.I)

EN_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
NUMBERS = {word: value for value, word in enumerate(EN_ONES)}
NUMBERS.update(dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10))))
SCALES = {"hundred": 100, "hundreds": 100, "thousand": 1000, "thousands": 1000, "million": 1000000, "millions": 1000000}
DECIMAL_MARKERS = {"point", "dot"}
NUMBER_JOINERS = {"and"}
WORD_TOKEN = re.compile(r"[^\W\d_]+", re.U)


def number_word(word):
    return NUMBERS.get(word)


def parse_number(words):
    total = current = 0
    fraction = None
    previous = None
    for word in words:
        if word in NUMBER_JOINERS:
            continue
        if word in DECIMAL_MARKERS:
            if fraction is not None:
                return None
            fraction = ""
            continue
        value = number_word(word)
        if fraction is not None:
            if value is None or not 0 <= value <= 9:
                return None
            fraction += str(value)
        elif word in SCALES:
            scale = SCALES[word]
            if scale == 100:
                current = (current or 1) * scale
            else:
                total += (current or 1) * scale
                current = 0
            previous = None
        elif value is not None:
            if previous is not None:
                valid = (20 <= previous < 100 and previous % 10 == 0 and 0 < value < 10
                         or previous >= 100 and previous % 100 == 0 and value < (1000 if previous % 1000 == 0 else 100))
                if not valid:
                    return None
            current += value
            previous = value
        else:
            return None
    if fraction == "":
        return None
    return str(total + current) + ("." + fraction if fraction is not None else "")


def normalize_numbers(text):
    """Convert number words only beside a known unit or component family."""
    words = list(WORD_TOKEN.finditer(text))
    replacements = []
    index = 0
    while index < len(words):
        first = words[index]
        word = first.group().casefold()
        if (first.start() and text[first.start() - 1].isalnum()) or number_word(word) is None and word not in SCALES and word not in DECIMAL_MARKERS:
            index += 1
            continue
        end = index
        sequence = [word]
        while end + 1 < len(words):
            following = words[end + 1]
            gap = text[words[end].end():following.start()]
            next_word = following.group().casefold()
            if not re.fullmatch(r"[\s-]+", gap) or not (number_word(next_word) is not None or next_word in SCALES or next_word in DECIMAL_MARKERS or next_word in NUMBER_JOINERS):
                break
            sequence.append(next_word)
            end += 1
        while sequence and sequence[-1] in NUMBER_JOINERS:
            sequence.pop()
            end -= 1
        tail = text[words[end].end():].lstrip(" -")
        value = parse_number(sequence)
        if value is not None and (UNIT_START.match(tail) or part_phrase(tail)
                                  or re.match(r"\d", tail) and has_part(tail)):
            replacements.append((first.start(), words[end].end(), value))
        index = max(index + 1, end + 1) if value is not None else index + 1
    for start, stop, value in reversed(replacements):
        text = text[:start] + value + text[stop:]
    return text


PREFIX = re.compile(
    r"^(?:please\b|can you\b|could you\b|would you\b|find\b|show me\b|me\b|i also need\b|i need\b|i want\b|i would like\b|i'd like\b|i am looking for\b|i'm looking for\b|for me\b|and lastly\b|lastly\b|also\b|as well as\b|and\b)[\s,:]*", re.I)
SUFFIX = re.compile(r"(?:[,\s]+)(?:please|for me|whatever we have)[.!?\s]*$", re.I)
GRAMMAR = re.compile(r"(?<!\w)(?:a|an|the|of|with)(?!\w)", re.I)
QUANTITY = re.compile(r"^(?:(?:a\s+)?(?:few|several)|(?P<number>\d+))\s+", re.I)
CONNECTOR = re.compile(r"\s+(?:as well as|and|plus)\s+|,\s+", re.I)
IDENTIFIER = re.compile(r"(?<!\w)(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{3,}(?!\w)")


def strip_request(text):
    text = text.strip(" \t\r\n,.;!?")
    while True:
        changed = PREFIX.sub("", text, count=1).strip()
        if changed == text:
            break
        text = changed
    return SUFFIX.sub("", text).strip(" \t\r\n,.;!?")


def has_part(text):
    identifiers = (match.group() for match in IDENTIFIER.finditer(text))
    return bool(CANONICAL_FAMILY.search(text) or any(
        not re.fullmatch(r"\d+(?:[pnumkKMµμ]?[FHVAW]|mm|Nm|[RrKkM])", item)
        for item in identifiers
    ))


def part_phrase(text):
    """Recognize a quantity before modifiers without crossing a specification."""
    head = CONNECTOR.split(text, maxsplit=1)[0]
    family = CANONICAL_FAMILY.search(head)
    if not family or UNIT_START.match(head):
        return False
    modifiers = head[:family.start()].split()
    if len(modifiers) > 5:
        return False
    return not any(word.casefold() in {"with", "of", "to", "between", "around", "at", "least", "most", "than"} for word in modifiers)


def split_requests(text):
    result = []
    # A full stop between words ends a sentence; decimal points and IPNs stay intact.
    for segment in re.split(r"[;\n]+|(?<=[.!?])\s+", text):
        # '10k and 20k resistors' can share an explicitly stated family, but
        # voltage, tolerance or extra qualifiers must never become new parts.
        chunks = [strip_request(chunk) for chunk in CONNECTOR.split(segment)]
        families = list(CANONICAL_FAMILY.finditer(segment))
        if len(chunks) > 1 and len(families) == 1:
            family = families[0].group()
            expanded = [chunk if CANONICAL_FAMILY.search(chunk) else chunk + " " + family for chunk in chunks]
            values = [parse_value_search(" ".join(GRAMMAR.sub(" ", chunk).split())) for chunk in expanded]
            if all(value is not None and not value.terms for value in values) and len({value.kind for value in values}) == 1:
                result.extend(expanded)
                continue
        start = 0
        for match in CONNECTOR.finditer(segment):
            left = segment[start:match.start()]
            right = CONNECTOR.split(segment[match.end():], maxsplit=1)[0]
            # Don't split 'red and green LED' or a component's compound attributes.
            if has_part(left) and has_part(right):
                result.append(left)
                start = match.end()
        result.append(segment[start:])
    return [segment for segment in result if strip_request(segment)]


def interpret_requests(text):
    """Return editable queries, warnings and quantity notes; never execute a search."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Enter a transcript of 1–{MAX_TEXT_LENGTH} characters")
    if any(ord(char) < 32 and not char.isspace() for char in text):
        raise ValueError("The transcript must not contain control characters")
    normalized = unicodedata.normalize("NFKC", text).replace("–", "-").replace("−", "-").replace("‑", "-").replace("’", "'")
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    normalized = re.sub(r"\bD[. ]+C\.?(?= motors?\b)", "DC", normalized, flags=re.I)
    for letters in ("PNP", "NPN"):
        pattern = r"\b" + r"[. ]+".join(letters) + r"\.?(?= transistors?\b)"
        normalized = re.sub(pattern, letters, normalized, flags=re.I)
    normalized = re.sub(r"(?<![\w,-])\d{1,3}(?:,\d{3})+(?![\d,])", lambda match: match.group().replace(",", ""), normalized)
    normalized = FAMILY_PATTERN.sub(lambda match: FAMILY_LOOKUP[match.group().casefold()], normalized)
    normalized = UNIT_PATTERN.sub(lambda match: UNIT_LOOKUP[match.group().casefold()], normalized)
    normalized = WORD_PATTERN.sub(lambda match: WORD_LOOKUP[match.group().casefold()], normalized)
    normalized = re.sub(r"(?<=\w)-(?=[pnumkKMµμ]?[ΩFH](?:$|\W))", " ", normalized)
    normalized = re.sub(r"([pnumkKMµμ]?[ΩFH])-(?=[A-Za-z])", r"\1 ", normalized)
    normalized = normalize_numbers(normalized)
    normalized = normalize_numbers(normalized)
    segments = split_requests(normalized)
    if not segments or len(segments) > MAX_REQUESTS:
        raise ValueError(f"Use between 1 and {MAX_REQUESTS} separate part requests")
    requests = []
    for segment in segments:
        query = strip_request(segment)
        warnings, notes = [], []
        if has_part(query):
            query = re.sub(r"^(?:a|an|the)\s+", "", query, flags=re.I)
        quantity = QUANTITY.match(query)
        if quantity and has_part(query[quantity.end():]) and not UNIT_START.match(query[quantity.end():]):
            count = quantity.group("number")
            notes.append(f"Requested quantity: {count or 'unspecified (a few)'}. Search does not check that quantity or reserve stock.")
            query = query[quantity.end():]
        if CANONICAL_FAMILY.search(query):
            query = GRAMMAR.sub(" ", query)
        query = " ".join(query.split()).strip(" ,.;!?")
        value = parse_value_search(query)
        if value:
            query = re.sub(rf"(?<!\w){value.kind}(?!\w)", " ", query, flags=re.I)
        elif re.search(r"\d\s*[pnumkKMµμ]?[ΩFH](?!\w)", query):
            warnings.append("The value or component type is ambiguous. Its text is retained; check the value and part name.")
        query = " ".join(query.split())
        # Display canonical units compactly, retaining case-sensitive SI prefixes.
        query = re.sub(r"(?<=\d)\s+(?=(?:[pnumkKMµμ]?[ΩFH]|mm|Nm|[VAW%])(?:$|\W))", "", query)
        transcription_error = bool(re.search(r"\b(?:orderings?|micro\s+thread)\b", query, re.I))
        if transcription_error:
            warnings.append("Possible transcription error: check 'O-rings' or the spoken unit. No correction was assumed.")
        if re.search(r"(?<!\w)(?:around|between|minimum|maximum|least|most|not|without)(?!\w)|[±~]|\d\s*-\s*\d", query, re.I):
            warnings.append("Ranges, exclusions and tolerances are not interpreted. Their wording is retained; edit the search before using it.")
        if re.search(r"\d\s*(?:[VAW%]|mm|Nm)(?!\w)|\b(?:torque|voltage|cross.section|material)\b", query, re.I):
            warnings.append("Only resistance, capacitance and inductance values have structured matching. Other specifications remain literal search text.")
        if not has_part(query):
            warnings.append("Some wording is outside the supported part vocabulary. It is kept as catalogue text; review the search line.")
        if re.search(r"\d,\d", query):
            warnings.append("Unrecognized comma number retained. Use a decimal point or a standard thousands separator.")
        multiple_types = len({match.group().casefold() for match in CANONICAL_FAMILY.finditer(query)}) > 1
        unresolved_list = bool(re.search(r",\s+", query))
        if multiple_types:
            warnings.append("Several component types remain on one line. Separate them if they are different requested parts.")
        elif CONNECTOR.search(query):
            warnings.append("Several values or attributes remain on this line. Review how they belong together.")
        number_uncertainty = any(number_word(match.group().casefold()) is not None or match.group().casefold() in SCALES for match in WORD_TOKEN.finditer(query))
        if number_uncertainty:
            warnings.append("A spoken number could not be attached to a supported unit or part quantity. Check it before searching.")
        if "O-ring" in query and re.search(r"\bsilicon\b", query, re.I):
            warnings.append("Check silicon versus silicone; the material was not corrected automatically.")
        if not query or len(query) > 200 or len(query.split()) > 12:
            warnings.append("Shorten this line to 1–200 characters and at most 12 words before adding it to search.")
        if unresolved_list:
            warnings.append("A comma-separated phrase could not be safely grouped. Separate parts onto individual lines and retain their specifications.")
        requests.append({"query": query, "warnings": warnings, "notes": notes,
                         "needs_edit": transcription_error or multiple_types or unresolved_list or number_uncertainty})
    return {"version": INTERPRETER_VERSION, "requests": requests}
