"""Component intent recognition: no inventory, network or hardware."""

import importlib
import unittest

from test_voice_requests import voice


types = importlib.import_module(voice.__package__ + ".component_types")


class ComponentTypeTests(unittest.TestCase):
    def test_known_families_use_complete_category_paths(self):
        for query, expected, remaining in (
            ("small magnet", "magnet", "small"),
            ("silicone O-ring", "O-ring", "silicone"),
            ("DC motor 12V", "DC motor", "12V"),
            ("M3 nut", "nut", "M3"),
            ("red LEDs", "LED", "red"),
            ("10k resistor", "resistor", "10k"),
            ("ball bearing", "ball bearing", "ball"),
        ):
            with self.subTest(query=query):
                scope = types.component_type(query)
                self.assertEqual((scope.name, scope.remaining), (expected, remaining))
                self.assertTrue(all("/" in path for path in scope.paths))

    def test_missing_catalogue_family_stays_scoped(self):
        self.assertEqual(types.component_type("battery").paths, ("Electronics/Batteries",))

    def test_polarity_categories_are_distinct(self):
        for polarity in ("PNP", "NPN"):
            scope = types.component_type(polarity + " transistor SMD")
            self.assertEqual(scope.paths, ("Electronics/Transistors/BJT/" + polarity,))
            self.assertEqual(scope.remaining, "SMD")

    def test_identifiers_unsupported_families_and_compound_objects_stay_literal(self):
        for query in ("NE555", "10uF", "ABC-MOSFET-12", "motor driver", "motor drivers",
                      "battery charger", "battery monitor", "magnet holder", "resistor for LED",
                      "capacitor tester board", "potentiometer", "magnetic reed switch", "resistor capacitor"):
            with self.subTest(query=query):
                self.assertIsNone(types.component_type(query))
