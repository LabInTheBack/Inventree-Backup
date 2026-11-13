"""Unit/notation boundary regressions without Django, inventory or network."""

import importlib.util
import re
import sys
import unittest
from decimal import Decimal

from support import PLUGIN_DIR

spec = importlib.util.spec_from_file_location("finder_value_terms_test", PLUGIN_DIR / "search_terms.py")
terms = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = terms
spec.loader.exec_module(terms)


class ComponentValueTests(unittest.TestCase):
    def test_equivalent_resistance_notations_and_spoken_units(self):
        for query in ("10kΩ", "10 kΩ", "10 k Ω", "10 kiloohm", "10 kilohm", "10 kilo ohms", "10000 ohms", "resistor 10k", "10K resistor", "10k0 resistor"):
            with self.subTest(query=query):
                value = terms.parse_value_search(query)
                self.assertIsNotNone(value)
                self.assertEqual(value.value, Decimal(10000))
                self.assertEqual(value.kind, "resistance")
                self.assertEqual(value.display, "10 kΩ")

    def test_component_families_and_prefix_case_remain_distinct(self):
        for query, kind, amount in (("1MΩ", "resistance", "1000000"), ("1 megohm", "resistance", "1000000"), ("1mΩ", "resistance", "0.001"),
                ("1 mOhm", "resistance", "0.001"), ("1 MOhm", "resistance", "1000000"),
                ("4k7 resistor", "resistance", "4700"), ("4R7 resistor", "resistance", "4.7"),
                ("100nF capacitor", "capacitance", "0.0000001"), ("0.1 µF", "capacitance", "0.0000001"),
                ("100 nanofarads", "capacitance", "0.0000001"), ("1 micro farad", "capacitance", "0.000001"),
                ("10uH inductor", "inductance", "0.00001"), ("10 microhenries", "inductance", "0.00001"),
                ("0R resistor", "resistance", "0")):
            with self.subTest(query=query):
                value = terms.parse_value_search(query)
                self.assertIsNotNone(value)
                self.assertEqual((value.kind, value.value), (kind, Decimal(amount)))

    def test_ambiguous_identifiers_ranges_and_conflicting_types_stay_literal(self):
        for query in ("10k", "10 k", "NE555", "R-10K-AX", "10k film", "10 resistors", "10kΩ capacitor",
                      "resistor capacitor 10k", "10kΩ 20kΩ", "resistor -10k", "-10kΩ", "10-20kΩ", "25V capacitor"):
            with self.subTest(query=query):
                self.assertIsNone(terms.parse_value_search(query))

    def test_numeric_and_unit_boundaries_prevent_wrong_values(self):
        value = terms.parse_value_search("10kΩ")
        explicit, bare = value.patterns()
        for text in ("10kΩ", "10 kΩ", "10000 ohms", "0.01MΩ", "10.000kΩ", "10 kilo ohms"):
            with self.subTest(text=text): self.assertRegex(text, explicit)
        for text in ("110kΩ", "10kΩExtra", "10kF", "10kH", "110k", "ABC10kΩ", "0.01mΩ", "0.01mOhm"):
            with self.subTest(text=text): self.assertIsNone(re.search(explicit, text))
        for text in ("Resistor 10k", "Resistor 10k0", "Resistor 10000R"):
            with self.subTest(text=text): self.assertRegex(text, bare)
        for text in ("Resistor 110k", "Resistor 10k2", "ModelX10k", "Resistor 10kΩ"):
            with self.subTest(text=text): self.assertIsNone(re.search(bare, text))

    def test_extra_constraints_are_preserved_and_type_is_explicit(self):
        value = terms.parse_value_search("metal film resistor 10 kiloohms 1%")
        self.assertEqual(value.terms, ("metal", "film", "1%"))
        self.assertTrue(value.require_family)
        self.assertFalse(terms.parse_value_search("10kΩ").require_family)
        self.assertIsNone(re.search(value.family_pattern, "capacitor", re.IGNORECASE))
