"""Check query behavior using real Django/MPTT and a disposable memory database."""

from __future__ import annotations

import importlib.util
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import FakePlugin, PLUGIN_DIR, module, modules


@unittest.skipUnless(importlib.util.find_spec("django"), "Django is available in the InvenTree container")
class DatabaseQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import django
        from django.conf import settings
        if not settings.configured:
            settings.configure(
                INSTALLED_APPS=[], DEFAULT_CHARSET="utf-8", USE_I18N=False, SECRET_KEY="offline-test-secret",
                DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            )
        # Never use an existing application's configured database for tests.
        if settings.DATABASES["default"].get("NAME") != ":memory:":
            raise unittest.SkipTest("Query tests require a disposable in-memory database")
        django.setup()
        from django.db import connection, models
        from mptt.models import MPTTModel, TreeForeignKey
        from stdimage.models import StdImageField

        class TestLocation(MPTTModel):
            name = models.CharField(max_length=100)
            pathstring = models.CharField(max_length=200)
            metadata = models.JSONField(default=dict)
            parent = TreeForeignKey("self", on_delete=models.CASCADE, null=True)

            class Meta:
                app_label = "wled_query_tests"

            def get_metadata(self, key, backup_value=None):
                return self.metadata.get(key, backup_value)

        class TestCategory(models.Model):
            name = models.CharField(max_length=100)
            pathstring = models.CharField(max_length=200)
            class Meta:
                app_label = "wled_query_tests"

        class TestModelType(models.Model):
            app_label = models.CharField(max_length=100)
            model = models.CharField(max_length=100)
            class Meta:
                app_label = "wled_query_tests"

        class TestTemplate(models.Model):
            name = models.CharField(max_length=100)
            units = models.CharField(max_length=100)
            class Meta:
                app_label = "wled_query_tests"

        class TestParameter(models.Model):
            model_id = models.PositiveIntegerField()
            model_type = models.ForeignKey(TestModelType, on_delete=models.CASCADE)
            template = models.ForeignKey(TestTemplate, on_delete=models.CASCADE)
            data_numeric = models.FloatField(null=True)
            class Meta:
                app_label = "wled_query_tests"

        class TestPart(models.Model):
            name = models.CharField(max_length=100)
            category = models.ForeignKey(TestCategory, on_delete=models.SET_NULL, null=True)
            IPN = models.CharField(max_length=100, blank=True, default="")
            description = models.CharField(max_length=250, blank=True, default="")
            keywords = models.CharField(max_length=250, blank=True, default="")
            active = models.BooleanField(default=True)
            virtual = models.BooleanField(default=False)
            image = StdImageField(blank=True, null=True, variations={"thumbnail": (128, 128)}, render_variations=False)

            class Meta:
                app_label = "wled_query_tests"

            @property
            def full_name(self):
                return self.name

            def __str__(self):
                return self.name

        class TestStock(models.Model):
            part = models.ForeignKey(TestPart, on_delete=models.CASCADE)
            location = models.ForeignKey(TestLocation, on_delete=models.CASCADE, null=True)
            quantity = models.DecimalField(max_digits=15, decimal_places=5, default=1)
            available = models.BooleanField(default=True)
            IN_STOCK_FILTER = models.Q(quantity__gt=0, available=True)

            class Meta:
                app_label = "wled_query_tests"

            @property
            def in_stock(self):
                return self.quantity > 0 and self.available

        class TestManufacturerPart(models.Model):
            part = models.ForeignKey(TestPart, on_delete=models.CASCADE)
            MPN = models.CharField(max_length=100)

            class Meta:
                app_label = "wled_query_tests"

        cls.Location, cls.Part, cls.Stock = TestLocation, TestPart, TestStock
        cls.Category, cls.Parameter, cls.Template, cls.ModelType = TestCategory, TestParameter, TestTemplate, TestModelType
        cls.schema_models = (cls.Location, cls.Category, cls.ModelType, cls.Template, cls.Parameter, cls.Part, cls.Stock, TestManufacturerPart)
        cls.ManufacturerPart = TestManufacturerPart
        cls.connection = connection
        with connection.schema_editor() as editor:
            for model in cls.schema_models:
                editor.create_model(model)
        dependencies = {
            "finder_query_test": module("finder_query_test", __path__=[str(PLUGIN_DIR)]),
            "finder_query_test.locator": modules.locator,
            "finder_query_test.planning": modules.planning,
            "company.models": module("company.models", ManufacturerPart=cls.ManufacturerPart),
            "part.models": module("part.models", Part=cls.Part),
            "stock.models": module("stock.models", StockItem=cls.Stock),
            "common.models": module("common.models", Parameter=cls.Parameter),
        }
        with patch.dict(sys.modules, dependencies):
            cls.finder_module = importlib.import_module("finder_query_test.finder")

    @classmethod
    def tearDownClass(cls):
        with cls.connection.schema_editor() as editor:
            for model in reversed(cls.schema_models):
                editor.delete_model(model)

    def setUp(self):
        # Delete only the disposable tables created above.
        with self.connection.cursor() as cursor:
            for model in reversed(self.schema_models):
                cursor.execute(f'DELETE FROM "{model._meta.db_table}"')
        self.plugin = FakePlugin()
        self.root = self.Location.objects.create(name="Root", pathstring="Root")
        self.part = self.Part.objects.create(name="NE555")
        self.first = self.Location.objects.create(
            name="Drawer 1", pathstring="Root / Drawer 1", parent=self.root,
            metadata={"wled_indicator": {"controller": "A", "led": 147, "leds": [147, 148]}},
        )
        self.Stock.objects.bulk_create([self.Stock(part=self.part, location=self.first) for _ in range(25)])
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        lock = patch.object(modules.locking, "lock_path", return_value=Path(temporary.name) / "hardware.lock")
        lock.start()
        self.addCleanup(lock.stop)

    def finder(self):
        return self.finder_module.FinderService(self.plugin)

    def dashboard_models(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(modules.dashboard, "StockLocation", self.Location))
        stack.enter_context(patch.object(modules.dashboard, "StockItem", self.Stock))
        return stack

    def test_dashboard_batches_stock_counts_and_paginates_locations(self):
        from django.test.utils import CaptureQueriesContext
        with self.dashboard_models():
            with CaptureQueriesContext(self.connection) as initial_queries:
                initial = modules.dashboard.build_dashboard(self.plugin, {})
            self.assertEqual(initial["rows"][0]["stock_items"], 25)
            self.assertEqual(initial["rows"][0]["part_count"], 1)
            for index in range(30):
                self.Location.objects.create(name=f"Drawer {index+2}", pathstring=f"Root / Drawer {index+2}", parent=self.root)
            with CaptureQueriesContext(self.connection) as expanded_queries:
                expanded = modules.dashboard.build_dashboard(self.plugin, {})
            second = modules.dashboard.build_dashboard(self.plugin, {"page": "2"})
        self.assertEqual(len(initial_queries), 3)
        self.assertEqual(len(expanded_queries), 3)
        self.assertEqual(len(expanded["rows"]), 25)
        self.assertEqual(len(second["rows"]), 6)
        self.assertEqual(expanded["total"], 31)
        self.assertIsNone(expanded["led_map"])
        self.assertFalse(set(row["id"] for row in second["rows"]) & set(row["id"] for row in expanded["rows"]))
        self.assertEqual(self.plugin.client.requests, [])

    def test_dashboard_counts_only_native_in_stock_records_and_distinct_part_ids(self):
        same_name = self.Part.objects.create(name="NE555")
        self.Stock.objects.create(part=same_name, location=self.first, quantity=100)
        self.Stock.objects.create(part=self.part, location=self.first, quantity=0)
        self.Stock.objects.create(part=self.part, location=self.first, quantity=10, available=False)
        with self.dashboard_models():
            result = modules.dashboard.build_dashboard(self.plugin, {})
        row = result["rows"][0]
        self.assertEqual(row["part_count"], 2)
        self.assertEqual(row["stock_items"], 26)
        self.assertEqual(row["part_names"], ["NE555", "NE555"])

    def test_dashboard_sharing_is_valid_and_led_grid_is_bounded_to_selected_controller(self):
        other = self.Location.objects.create(name="Other", pathstring="Root / Other", parent=self.root,
            metadata={"wled_indicator": {"controller": "A", "leds": [147]}})
        with self.dashboard_models():
            result = modules.dashboard.build_dashboard(self.plugin, {"controller": "A", "led": "148"})
            tools = modules.dashboard.build_dashboard(self.plugin, {"view": "tools", "controller": "A", "led_page": "2"})
            search = modules.dashboard.build_dashboard(self.plugin, {"q": "ne555", "root": str(self.root.pk)})
        self.assertEqual({row["id"] for row in result["rows"]}, {self.first.pk, other.pk})
        self.assertTrue(all(row["state"] == "shared" for row in result["rows"]))
        self.assertEqual(result["summary"]["mapped"], 2)
        self.assertEqual(tools["led_map"]["cells"][0]["led"], 129)
        self.assertEqual(len(tools["led_map"]["cells"]), 72)
        self.assertEqual(len(tools["led_map"]["cells"][19]["locations"]), 2)
        self.assertEqual([row["id"] for row in search["rows"]], [self.first.pk])
        self.assertEqual(self.plugin.client.requests, [])

    def test_dashboard_mapping_review_and_atomic_save_preserve_other_metadata(self):
        self.first.metadata["keep"] = {"nested": True}
        self.first.save()
        other = self.Location.objects.create(name="Other", pathstring="Root / Other", parent=self.root)
        self.plugin.locator = lambda: modules.locator.LocatorService(self.plugin)
        payload = {"location_ids": [other.pk, self.first.pk], "mode": "sequential", "controller": "B", "leds": [1]}
        with self.dashboard_models():
            review, _ = modules.dashboard.preview_mapping(self.plugin, payload)
            self.first.refresh_from_db()
            self.assertEqual(self.first.metadata["wled_indicator"]["controller"], "A")
            saved = modules.dashboard.save_mapping(self.plugin, {**payload, "revision": review["revision"]})
        self.first.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(saved["saved"], 2)
        self.assertEqual(other.metadata["wled_indicator"]["leds"], [0])
        self.assertEqual(self.first.metadata["wled_indicator"]["leds"], [1])
        self.assertEqual(self.first.metadata["keep"], {"nested": True})
        self.assertEqual(self.plugin.client.requests, [])

    def test_dashboard_stale_review_and_late_validation_never_partially_save(self):
        other = self.Location.objects.create(name="Other", pathstring="Root / Other", parent=self.root)
        payload = {"location_ids": [self.first.pk, other.pk], "mode": "sequential", "controller": "B", "leds": [59]}
        with self.dashboard_models():
            review, _ = modules.dashboard.preview_mapping(self.plugin, payload)
            self.first.metadata["wled_indicator"]["leds"] = [1]
            self.first.save()
            with self.assertRaises(modules.dashboard.DashboardConflict):
                modules.dashboard.save_mapping(self.plugin, {**payload, "revision": review["revision"]})
            other.refresh_from_db()
            self.assertNotIn("wled_indicator", other.metadata)
            with self.assertRaises(ValueError):
                modules.dashboard.preview_mapping(self.plugin, {**payload, "leds": [60]})
            review, _ = modules.dashboard.preview_mapping(self.plugin, payload)
            original_save = self.Location.save
            def fail_second(location, *args, **kwargs):
                if location.pk == other.pk:
                    raise RuntimeError("Simulated second-row failure")
                return original_save(location, *args, **kwargs)
            with patch.object(self.Location, "save", fail_second), self.assertRaises(RuntimeError):
                modules.dashboard.save_mapping(self.plugin, {**payload, "revision": review["revision"]})
        self.first.refresh_from_db()
        self.assertEqual(self.first.metadata["wled_indicator"]["controller"], "A")
        self.assertEqual(self.first.metadata["wled_indicator"]["leds"], [1])

    def test_dashboard_review_reports_shared_targets_and_removal(self):
        other = self.Location.objects.create(name="Other", pathstring="Root / Other", parent=self.root)
        with self.dashboard_models():
            review, _ = modules.dashboard.preview_mapping(self.plugin, {
                "location_ids": [other.pk], "mode": "same", "controller": "A", "leds": [148],
            })
            self.assertEqual(review["shared_with"][0]["id"], self.first.pk)
            removal = {"location_ids": [self.first.pk], "mode": "remove"}
            review, _ = modules.dashboard.preview_mapping(self.plugin, removal)
            modules.dashboard.save_mapping(self.plugin, {**removal, "revision": review["revision"]})
        self.first.refresh_from_db()
        self.assertNotIn("wled_indicator", self.first.metadata)

    def test_dashboard_locate_validates_entire_selection_before_clearing(self):
        other = self.Location.objects.create(name="Other", pathstring="Root / Other", parent=self.root)
        with self.dashboard_models():
            with self.assertRaises(modules.dashboard.DashboardConflict):
                modules.dashboard.locate_dashboard_locations(self.plugin, {"location_ids": [self.first.pk, other.pk]})
            with self.assertRaises(modules.dashboard.DashboardConflict):
                modules.dashboard.locate_dashboard_locations(self.plugin, {"location_ids": [self.first.pk, 99999]})
            self.assertEqual(self.plugin.client.requests, [])
            other.metadata = {"wled_indicator": {"controller": "A", "leds": [147]}}
            other.save()
            result = modules.dashboard.locate_dashboard_locations(self.plugin, {"location_ids": [self.first.pk, other.pk]})
        self.assertEqual(result["located"], 2)
        self.assertEqual([request[3] for request in self.plugin.client.requests if request[1] == "POST"][-1], {"seg": [{"id": 0, "i": [147, "FF0000", 148, "FF0000"]}]})

    def test_dashboard_filters_and_mapping_validation_are_bounded(self):
        with self.dashboard_models():
            for params in ({"page": "0"}, {"page": "1.5"}, {"q": "x" * 201}, {"root": "9999"}, {"state": "broken"}, {"view": "unknown"}, {"led": "-1"}):
                with self.subTest(params=params), self.assertRaises(ValueError):
                    modules.dashboard.build_dashboard(self.plugin, params)
            base = {"location_ids": [self.first.pk], "controller": "B", "mode": "same", "leds": [1]}
            for update in ({"location_ids": [self.root.pk]}, {"location_ids": [9999]}, {"leds": [True]}, {"leds": [1.5]}, {"leds": [0]}, {"leds": [61]}, {"mode": "unknown"}, {"controller": "missing"}):
                with self.subTest(update=update), self.assertRaises(ValueError):
                    modules.dashboard.preview_mapping(self.plugin, {**base, **update})
        self.assertEqual(self.plugin.client.requests, [])

    def test_dashboard_without_saved_controller_count_never_discovers_hardware(self):
        self.plugin.settings["WLED_CONTROLLERS"] = '[{"label":"A","address":"http://a.invalid"}]'
        self.plugin.client.invalidate_configuration()
        with self.dashboard_models():
            result = modules.dashboard.build_dashboard(self.plugin, {"view": "tools"})
            self.assertEqual(result["led_map"]["cells"], [])
            self.assertEqual(result["controllers"][0]["max_leds"], 0)
            self.assertEqual(result["summary"]["invalid"], 1)
        self.assertEqual(self.plugin.client.requests, [])

    def test_part_preview_reuses_a_parent_plan_across_stock_records(self):
        from django.test.utils import CaptureQueriesContext
        self.Stock.objects.all().update(location=self.root)
        service = modules.locator.LocatorService(self.plugin)
        with patch.object(modules.locator, "StockItem", self.Stock):
            with CaptureQueriesContext(self.connection) as queries:
                result = service.preview_part_object(self.part)
        self.assertEqual(result["summary"]["lit_items"], 25)
        self.assertEqual(result["controller_leds"], {"A": [147, 148]})
        self.assertEqual(len(queries), 2)  # Stock with joins, then descendants once.
        self.assertEqual(self.plugin.client.requests, [])

    def test_search_separates_queries_and_ranks_exact_identifiers(self):
        exact = self.Part.objects.create(name="Timer chip", IPN="NE555", keywords="timer")
        self.Part.objects.create(name="NE555 board", keywords="timer")
        self.Part.objects.create(name="NE555 inactive", active=False)
        self.Part.objects.create(name="NE555 virtual", virtual=True)
        result = self.finder().search(["NE555", "nothing-here"])
        self.assertEqual(result["results"][0]["match_status"], "multiple")
        self.assertEqual(result["results"][0]["matches"][0]["part"]["id"], exact.pk)
        self.assertEqual(len(result["results"][0]["matches"]), 3)
        self.assertEqual(result["results"][1]["match_status"], "no_match")
        self.assertEqual(self.plugin.client.requests, [])

    def test_search_mpn_keywords_and_description_require_all_terms(self):
        resistor = self.Part.objects.create(name="Resistor", keywords="10k axial", description="metal film")
        self.ManufacturerPart.objects.create(part=resistor, MPN="R-10K-AX")
        self.ManufacturerPart.objects.create(part=resistor, MPN="R-10K-AX")
        result = self.finder().search(["10k film", "R-10K-AX", "10k ceramic"])
        self.assertEqual([row["matches"][0]["part"]["id"] for row in result["results"][:2]], [resistor.pk, resistor.pk])
        self.assertEqual(len(result["results"][1]["matches"]), 1)  # Duplicate MPNs do not duplicate parts.
        self.assertEqual(result["results"][2]["matches"], [])

    def test_search_reuses_native_image_urls_without_generating_files_or_extra_queries(self):
        from django.test import override_settings
        from django.test.utils import CaptureQueriesContext
        from stdimage.models import StdImageFieldFile
        self.Part.objects.filter(pk=self.part.pk).update(image="parts/NE555.png")
        missing_image = self.Part.objects.create(name="NE555 board")
        with override_settings(MEDIA_URL="/media/"), patch.object(
            StdImageFieldFile, "render_variation", side_effect=AssertionError("Search must not generate thumbnails"),
        ), patch.object(self.Part._meta.get_field("image").storage, "open", side_effect=AssertionError("Search must not read image files")):
            with CaptureQueriesContext(self.connection) as queries:
                matches = self.finder().search(["NE555"])["results"][0]["matches"]
        self.assertEqual(len(queries), 2)
        parts = {match["part"]["id"]: match["part"] for match in matches}
        self.assertEqual(parts[self.part.pk]["thumbnail_url"], "/media/parts/NE555.thumbnail.png")
        self.assertEqual(parts[self.part.pk]["image_url"], "/media/parts/NE555.png")
        self.assertIsNone(parts[missing_image.pk]["thumbnail_url"])
        self.assertIsNone(parts[missing_image.pk]["image_url"])

    def test_truncated_search_is_still_ambiguous_and_batches_availability(self):
        from django.test.utils import CaptureQueriesContext
        self.Part.objects.create(name="NE555 board")
        finder = self.finder()
        with CaptureQueriesContext(self.connection) as queries:
            result = finder.search(["NE555", " NE555  "], limit=1)
        self.assertTrue(result["results"][0]["has_more"])
        self.assertEqual(result["results"][0]["match_status"], "multiple")
        self.assertEqual(len(queries), 2)  # One distinct query, one stock query.

    def test_finder_pages_by_rank_name_and_id_without_duplicates(self):
        parts = [self.Part.objects.create(name="Timer") for _ in range(13)]
        found, cursor, page_count = [], None, 0
        while True:
            result = self.finder().search(["Timer"], cursor=cursor)["results"][0]
            found.extend(match["part"]["id"] for match in result["matches"])
            page_count += 1
            self.assertEqual(result["match_status"], "multiple")
            if not result["has_more"]:
                self.assertIsNone(result["next_cursor"])
                break
            cursor = result["next_cursor"]
            self.assertLess(page_count, 10)
        self.assertEqual(found, [part.pk for part in parts])
        self.assertEqual(len(set(found)), 13)
        self.assertEqual(page_count, 3)
        self.assertEqual(self.plugin.client.requests, [])

    def test_finder_cursor_crosses_rank_boundaries_and_survives_deleted_anchor(self):
        exact_ipn = self.Part.objects.create(name="A widget", IPN="widget")
        exact_name = self.Part.objects.create(name="widget")
        exact_mpn = self.Part.objects.create(name="B widget")
        self.ManufacturerPart.objects.create(part=exact_mpn, MPN="widget")
        tail = self.Part.objects.create(name="widget board")
        first = self.finder().search(["widget"], limit=1)["results"][0]
        self.assertEqual(first["matches"][0]["part"]["id"], exact_ipn.pk)
        cursor = first["next_cursor"]
        # Removing the anchor does not shift an OFFSET or require an anchor lookup.
        exact_ipn.delete()
        self.Part.objects.create(name="000 widget", IPN="widget")
        found = []
        while cursor:
            page = self.finder().search(["widget"], limit=1, cursor=cursor)["results"][0]
            found.extend(match["part"]["id"] for match in page["matches"])
            cursor = page["next_cursor"]
        self.assertEqual(found, [exact_name.pk, exact_mpn.pk, tail.pk])

    def test_finder_cursor_is_signed_query_bound_validated_and_expiring(self):
        from django.core import signing
        from time import time
        self.Part.objects.create(name="NE555 board")
        cursor = self.finder().search(["NE555"], limit=1)["results"][0]["next_cursor"]
        for query, invalid in ((["NE555"], "bad"), (["NE555"], True), (["other"], cursor), (["NE555", "other"], cursor), (["NE555"], "x"*4097)):
            with self.subTest(query=query, cursor=str(invalid)[:15]), self.assertRaises(ValueError):
                self.finder().search(query, cursor=invalid)
        with patch("django.core.signing.time.time", return_value=time()+3601), self.assertRaises(ValueError):
            self.finder().search(["NE555"], cursor=cursor)
        malformed = signing.dumps({"query": "NE555", "rank": True, "name": "NE555", "id": 1}, salt=self.finder_module.CURSOR_SALT)
        with self.assertRaises(ValueError):
            self.finder().search(["NE555"], cursor=malformed)

    def value_part(self, name, family, template, units, value):
        category = self.Category.objects.create(name=family, pathstring=f"Electronics / Passives / {family}")
        part = self.Part.objects.create(name=name, category=category)
        kind, _ = self.ModelType.objects.get_or_create(app_label="part", model="part")
        parameter = self.Template.objects.create(name=template, units=units)
        self.Parameter.objects.create(model_type=kind, model_id=part.pk, template=parameter, data_numeric=value)
        return part

    def test_unit_search_combines_text_category_and_si_parameters_without_cross_unit_matches(self):
        from django.test.utils import CaptureQueriesContext
        structured = self.value_part("MFR25", "Resistors", "Resistance", "ohms", 10000)
        named = self.Part.objects.create(name="Resistor 10k metal film")
        explicit = self.Part.objects.create(name="Precision 10000 ohms")
        wrong_number = self.Part.objects.create(name="Resistor 110kΩ")
        wrong_unit = self.Part.objects.create(name="Capacitor 10kF")
        wrong_family = self.Part.objects.create(name="Capacitor 10k")
        self.value_part("Generic capacitor", "Capacitors", "Capacitance", "nF", 10000)
        for text in ("10kΩ", "10 kΩ", "10 kiloohm", "10000 ohms"):
            with self.subTest(text=text), CaptureQueriesContext(self.connection) as queries:
                result = self.finder().search([text])["results"][0]
            ids = {match["part"]["id"] for match in result["matches"]}
            self.assertEqual(ids, {structured.pk, named.pk, explicit.pk})
            self.assertNotIn(wrong_number.pk, ids)
            self.assertNotIn(wrong_unit.pk, ids)
            self.assertNotIn(wrong_family.pk, ids)
            self.assertEqual(result["value_match"]["display"], "10 kΩ")
            self.assertEqual(len(queries), 2)  # Correlated parameter lookup; batched stock query.
        result = self.finder().search(["resistor 10k metal film"])["results"][0]
        self.assertEqual([row["part"]["id"] for row in result["matches"]], [named.pk])
        result = self.finder().search(["resistor 10 kiloohms"])["results"][0]
        self.assertEqual({row["part"]["id"] for row in result["matches"]}, {structured.pk, named.pk})

    def test_unit_search_preserves_mega_milli_and_does_not_match_identifier_fragments(self):
        mega = self.Part.objects.create(name="Resistor 1MΩ")
        milli = self.Part.objects.create(name="Resistor 1mΩ")
        self.Part.objects.create(name="Resistor 11MΩ")
        self.Part.objects.create(name="Resistor mystery", IPN="ABC-1M-X")
        for text, expected in (("1MΩ", mega.pk), ("1mΩ", milli.pk), ("resistor 1M", mega.pk), ("resistor 1m", milli.pk)):
            with self.subTest(text=text):
                result = self.finder().search([text])["results"][0]
                self.assertEqual([match["part"]["id"] for match in result["matches"]], [expected])

    def test_unit_search_uses_capacitance_and_inductance_parameters_with_roundoff_only(self):
        capacitor = self.value_part("Ceramic generic", "Capacitors", "Capacitance", "µF", .00000010000000000001)
        inductor = self.value_part("Shielded generic", "Inductors", "Inductance", "mH", .00001)
        self.value_part("Wrong cap", "Capacitors", "Capacitance", "µF", .000001)
        self.value_part("No unit", "Capacitors", "Capacitance", "", .0000001)
        self.value_part("ESR only", "Capacitors", "ESR Max", "ohm", 10000)
        for text, expected in (("100nF", capacitor.pk), ("0.1uF capacitor", capacitor.pk), ("100 nanofarads", capacitor.pk),
                               ("10uH", inductor.pk), ("10 microhenry inductor", inductor.pk)):
            with self.subTest(text=text):
                result = self.finder().search([text])["results"][0]
                self.assertEqual([match["part"]["id"] for match in result["matches"]], [expected])
        self.assertEqual(self.plugin.client.requests, [])

    def test_availability_excludes_unavailable_and_zero_stock_and_keeps_unmapped_stock(self):
        self.Stock.objects.create(part=self.part, location=self.first, quantity=10, available=False)
        self.Stock.objects.create(part=self.part, location=self.first, quantity=0)
        self.Stock.objects.create(part=self.part, location=None, quantity="2.5")
        result = self.finder().search(["NE555"])["results"][0]["matches"][0]["availability"]
        self.assertEqual(result["in_stock_quantity"], "27.5")
        self.assertEqual(result["stock_items"], 26)
        self.assertEqual(result["locations"][1]["in_stock_quantity"], "2.5")
        self.assertFalse(result["locations"][1]["can_locate"])

    def test_selection_batches_stock_and_combines_targets_preserving_part_order(self):
        from django.test.utils import CaptureQueriesContext
        other = self.Part.objects.create(name="Resistor")
        self.Stock.objects.create(part=other, location=self.first)
        with CaptureQueriesContext(self.connection) as queries:
            result = self.finder().preview([other.pk, self.part.pk, other.pk])
        self.assertEqual(len(queries), 2)
        self.assertEqual(result["part_ids"], [other.pk, self.part.pk])
        self.assertEqual(result["summary"]["selected_parts"], 2)
        self.assertEqual(result["controller_leds"], {"A": [147, 148]})
        self.assertTrue(result["can_locate"])
        self.assertEqual(self.plugin.client.requests, [])

    def test_selection_uses_native_filter_annotation_without_lazy_availability_reads(self):
        from django.test.utils import CaptureQueriesContext
        from unittest.mock import PropertyMock
        self.Stock.objects.create(part=self.part, location=self.first, quantity=5, available=False)
        with patch.object(self.Stock, "in_stock", new_callable=PropertyMock, side_effect=AssertionError("Unexpected lazy availability read")):
            with CaptureQueriesContext(self.connection) as queries:
                result = self.finder().preview([self.part.pk])
        self.assertEqual(len(queries), 2)
        self.assertEqual(result["parts"][0]["summary"]["skipped_items"], 1)
        self.assertEqual(result["parts"][0]["availability"]["in_stock_quantity"], "25")

    def test_selection_locate_clears_once_and_lights_the_union(self):
        other = self.Part.objects.create(name="Resistor")
        second = self.Location.objects.create(
            name="Drawer 2", pathstring="Root / Drawer 2", parent=self.root,
            metadata={"wled_indicator": {"controller": "B", "led": 1}},
        )
        self.Stock.objects.create(part=other, location=second)
        result = self.finder().locate([self.part.pk, other.pk])
        self.assertEqual(result["controller_leds"], {"A": [147, 148], "B": [1]})
        posts = [row for row in self.plugin.client.requests if row[1] == "POST"]
        self.assertEqual(len(posts), 4)  # Two clear POSTs, then two set POSTs.
        self.assertEqual(posts[-1][3], {"seg": [{"id": 0, "i": [1, "FF0000"]}]})

    def test_selection_refuses_missing_or_unlocatable_parts_without_clearing(self):
        other = self.Part.objects.create(name="No stock")
        for ids in ([self.part.pk, 999999], [self.part.pk, other.pk]):
            with self.subTest(ids=ids):
                with self.assertRaises(self.finder_module.SelectionNotLocatable) as caught:
                    self.finder().locate(ids)
                self.assertFalse(caught.exception.plan["can_locate"])
        self.assertEqual(self.plugin.client.requests, [])

    def test_search_and_preview_never_discover_unsaved_controller_counts(self):
        import json
        self.plugin.settings["WLED_CONTROLLERS"] = json.dumps([{"label": "A", "address": "a.invalid"}])
        finder = self.finder()
        result = finder.search(["NE555"])
        location = result["results"][0]["matches"][0]["availability"]["locations"][0]
        self.assertFalse(location["can_locate"])
        self.assertIn("no saved LED count", location["reason"])
        self.assertFalse(finder.preview([self.part.pk])["can_locate"])
        self.assertEqual(self.plugin.client.requests, [])

    def test_locate_resolves_again_after_a_previous_preview(self):
        finder = self.finder()
        self.assertTrue(finder.preview([self.part.pk])["can_locate"])
        self.Stock.objects.all().update(quantity=0)
        with self.assertRaises(self.finder_module.SelectionNotLocatable):
            finder.locate([self.part.pk])
        self.assertEqual(self.plugin.client.requests, [])

    def test_locate_refreshes_mapping_metadata_after_a_preview(self):
        finder = self.finder()
        finder.preview([self.part.pk])
        self.Location.objects.filter(pk=self.first.pk).update(metadata={"wled_indicator": {"controller": "A", "led": 4}})
        result = finder.locate([self.part.pk])
        self.assertEqual(result["controller_leds"], {"A": [4]})


if __name__ == "__main__":
    unittest.main()
