"""English request boundaries, numbers and conservative constraint handling."""

import importlib
import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path


package = types.ModuleType("voice_requests_offline")
package.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules[package.__name__] = package
voice = importlib.import_module(package.__name__ + ".voice_requests")
terms = importlib.import_module(package.__name__ + ".search_terms")


class VoiceRequestTests(unittest.TestCase):
    def result(self, text):
        return voice.interpret_requests(text)["requests"]

    def values(self, text):
        rows = self.result(text)
        self.assertTrue(all(not row["warnings"] for row in rows), rows)
        values = [terms.parse_value_search(row["query"]) for row in rows]
        self.assertTrue(all(values), rows)
        return [(value.kind, value.value) for value in values]

    def test_screenshot_sentence_becomes_two_searches(self):
        rows = self.result("find a 10k resistor and a 10 microfarad capacitor.")
        self.assertEqual([row["query"] for row in rows], ["10k resistor", "10uF capacitor"])
        self.assertTrue(all(not row["warnings"] for row in rows))

    def test_prompt4_list_separates_parts_and_preserves_quantity_notes(self):
        text = "Batteries, two silicone O-rings, 3 magnets, two magnets, PNP transistors"
        result = voice.interpret_requests(text)
        self.assertEqual(result["version"], voice.INTERPRETER_VERSION)
        rows = result["requests"]
        self.assertEqual([row["query"] for row in rows], ["battery", "silicone O-ring", "magnet", "magnet", "PNP transistor"])
        self.assertTrue(all(not row["needs_edit"] and not row["warnings"] for row in rows), rows)
        for index, quantity in ((1, "2"), (2, "3"), (3, "2")):
            self.assertTrue(any("quantity: " + quantity in note for note in rows[index]["notes"]))

    def test_o_ring_and_dc_motor_smoke_request_is_two_queries(self):
        rows = self.result("Find O-rings and a DC motor.")
        self.assertEqual([row["query"] for row in rows], ["O-ring", "DC motor"])
        self.assertTrue(all(not row["needs_edit"] for row in rows))

    def test_common_o_ring_and_spelled_initialism_variants(self):
        for text in ("Find orings and a D.C. motor.", "Find O  rings and a D C motor."):
            self.assertEqual([row["query"] for row in self.result(text)], ["O-ring", "DC motor"])
        self.assertEqual([row["query"] for row in self.result("P N P transistors and N.P.N. transistors")], ["PNP transistor", "NPN transistor"])

    def test_quantities_before_modifiers_are_separate_from_values(self):
        rows = self.result("Find two silicone O-rings and three small magnets and two 10k resistors.")
        self.assertEqual([row["query"] for row in rows], ["silicone O-ring", "small magnet", "10k resistor"])
        self.assertTrue(all(row["notes"] and not row["needs_edit"] for row in rows))
        rows = self.result("Find a twenty four volt DC motor and a three millimeter O-ring.")
        self.assertIn("24V", rows[0]["query"])
        self.assertIn("3mm", rows[1]["query"])
        self.assertTrue(all(not row["notes"] for row in rows), rows)

    def test_unresolved_lists_and_known_mishearings_need_an_edit(self):
        for text in ("clips, spacers", "Find orderings and a motor", "resistor one two kilo ohms"):
            self.assertTrue(any(row["needs_edit"] for row in self.result(text)), text)
        rows = self.result("Find a resistor with 10kΩ, 50V and a capacitor.")
        self.assertEqual(len(rows), 2)
        self.assertIn("50V", rows[0]["query"])
        self.assertTrue(rows[0]["needs_edit"])

    def test_spoken_units_produce_resistance_and_capacitance(self):
        expected = [("resistance", Decimal("10000")), ("capacitance", Decimal("0.00001"))]
        self.assertEqual(self.values("Please find a ten kilo ohm resistor and a ten microfarad capacitor."), expected)

    def test_decimal_words(self):
        for text in ("a zero point one microfarad capacitor", "a point one microfarad capacitor"):
            with self.subTest(text=text):
                self.assertEqual(self.values(text), [("capacitance", Decimal("0.0000001"))])

    def test_hundreds_and_thousands(self):
        for text, expected in (
            ("one hundred and ten ohm resistor", "110"),
            ("two hundred twenty five ohm resistor", "225"),
            ("one thousand ohm resistor", "1000"),
            ("1,000 ohm resistor", "1000"),
            ("10,000 ohm resistor", "10000"),
            ("one million ohm resistor", "1000000"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.values(text), [("resistance", Decimal(expected))])

    def test_unknown_comma_numbers_are_not_reinterpreted_as_decimals(self):
        row = self.result("1,5 microfarad capacitor")[0]
        self.assertIn("1,5", row["query"])
        self.assertTrue(any("comma number" in warning for warning in row["warnings"]))
        self.assertEqual(self.result("Find R-1,000")[0]["query"], "R-1,000")

    def test_polite_phrases_do_not_become_catalogue_constraints(self):
        for text in ("I’m looking for a ten kilo ohm resistor please", "Can you please find me a ten kilo ohm resistor?"):
            self.assertEqual(self.values(text), [("resistance", Decimal("10000"))])

    def test_si_prefix_case_and_part_identifiers_survive(self):
        self.assertEqual(self.values("1MΩ resistor; 1mΩ resistor"), [("resistance", Decimal("1000000")), ("resistance", Decimal("0.001"))])
        for part in ("NE555", "LM358N", "R-10K-AX", "GRM188R71H104KA93D", "SOT-23"):
            self.assertEqual(self.result("Find " + part)[0]["query"], part)
        self.assertEqual([row["query"] for row in self.result("Find NE555 and LM358")], ["NE555", "LM358"])

    def test_quantities_are_notes_and_never_stock_filters(self):
        for text, quantity in (("find ten resistors", "10"), ("find three capacitors", "3"), ("a few capacitors of ten microfarads", "unspecified")):
            row = self.result(text)[0]
            self.assertTrue(any(quantity in note for note in row["notes"]), row)
            self.assertTrue(any("does not check" in note for note in row["notes"]))
        self.assertEqual(self.result("10k resistor")[0]["notes"], [])

    def test_attributes_are_not_split_off_as_new_parts(self):
        for constraint in ("1% tolerance", "50V", "3mm"):
            rows = self.result(f"Find a resistor with 10kΩ and {constraint} and a capacitor.")
            self.assertEqual(len(rows), 2, rows)
            self.assertIn(constraint, rows[0]["query"])
            self.assertEqual(rows[1]["query"], "capacitor")
        self.assertEqual(len(self.result("red and green LED")), 1)
        self.assertEqual(len(self.result("red LED and green LED")), 2)

    def test_explicit_shared_family_can_apply_to_a_plain_value_list(self):
        for text in ("10k and 20k resistors", "10k resistor and 20k"):
            self.assertEqual(self.values(text), [("resistance", Decimal("10000")), ("resistance", Decimal("20000"))])
        self.assertEqual(len(self.result("10k and 20k and 30k resistors")), 3)
        for text in ("10k resistor and 50V", "10k resistor and 1% tolerance", "10k resistor and 100nF"):
            rows = self.result(text)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["warnings"], rows)

    def test_ranges_voltage_torque_and_materials_are_preserved_and_flagged(self):
        rows = self.result("Find a MOSFET with drain to source of around 40 volts and a DC motor with torque of three newton meters.")
        self.assertEqual(len(rows), 2)
        self.assertIn("around 40V", rows[0]["query"])
        self.assertIn("3Nm", rows[1]["query"])
        self.assertTrue(all(row["warnings"] for row in rows))
        row = self.result("O-rings with 3 millimeters cross-section made out of silicon")[0]
        self.assertIn("3mm", row["query"])
        self.assertIn("silicon", row["query"])
        self.assertTrue(any("silicone" in warning for warning in row["warnings"]))

    def test_ambiguous_transcriptions_are_not_guessed(self):
        for text in ("a few orderings", "10k 10 micro thread"):
            row = self.result(text)[0]
            self.assertTrue(any("transcription" in warning for warning in row["warnings"]))
            self.assertNotIn("O-ring", row["query"])
            self.assertNotIn("uF", row["query"])

    def test_conflicting_types_and_values_remain_visible(self):
        for text in ("10kΩ capacitor", "10kΩ 20kΩ resistor"):
            row = self.result(text)[0]
            self.assertTrue(row["warnings"], row)
            self.assertIn("10kΩ", row["query"])

    def test_plural_families_and_explicit_lines(self):
        rows = self.result("Find screws; nuts\nwashers; LEDs; adhesive tapes; O-rings")
        self.assertEqual([row["query"] for row in rows], ["screw", "nut", "washer", "LED", "adhesive tape", "O-ring"])

    def test_unknown_words_are_retained_without_translation(self):
        for text in ("Kondensator", "конденсатор", "unfamiliar-widget"):
            row = self.result(text)[0]
            self.assertEqual(row["query"], text)
            self.assertTrue(row["warnings"])

    def test_long_original_example_keeps_every_component_and_constraint(self):
        text = "Please find a few O-rings for me with cross-section of 3 millimeters made out of silicon. I also need a DC motor with a torque of 3 newton meters, as well as a few capacitors of 10 microfarads. And lastly, I need a few tapes, whatever we have."
        rows = self.result(text)
        self.assertEqual(len(rows), 4, rows)
        self.assertIn("O-ring", rows[0]["query"])
        self.assertIn("3mm", rows[0]["query"])
        self.assertIn("DC motor", rows[1]["query"])
        self.assertIn("3Nm", rows[1]["query"])
        self.assertEqual(rows[2]["query"], "capacitor 10uF")
        self.assertEqual(rows[3]["query"], "tape")

    def test_unknown_words_and_unparsed_numbers_are_not_discarded(self):
        for text in ("unknown-widget special-finish", "resistor one two kilo ohms"):
            row = self.result(text)[0]
            self.assertTrue(row["warnings"])
        self.assertIn("special-finish", self.result("resistor special-finish")[0]["query"])

    def test_limits_and_invalid_inputs(self):
        for text in (None, True, "", " \n", "x" * 8193, "resistor\x00", ";".join(["resistor"] * 21)):
            with self.subTest(text=str(text)[:40]), self.assertRaises(ValueError):
                self.result(text)
        self.assertEqual(len(self.result(";".join(["resistor"] * 20))), 20)
        row = self.result("resistor " + "x" * 300)[0]
        self.assertIn("x" * 300, row["query"])
        self.assertTrue(any("Shorten" in warning for warning in row["warnings"]))


if __name__ == "__main__":
    unittest.main()
