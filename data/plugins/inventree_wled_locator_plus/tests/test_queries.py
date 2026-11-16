"""Check query behavior using real Django/MPTT and a disposable memory database."""

from __future__ import annotations

import importlib.util
import importlib
import sys
import tempfile
import unittest
from decimal import Decimal
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
            data = models.CharField(max_length=500, blank=True, default="")
            class Meta:
                app_label = "wled_query_tests"

        class TestPart(MPTTModel):
            name = models.CharField(max_length=100)
            category = models.ForeignKey(TestCategory, on_delete=models.SET_NULL, null=True)
            IPN = models.CharField(max_length=100, blank=True, default="")
            description = models.CharField(max_length=250, blank=True, default="")
            keywords = models.CharField(max_length=250, blank=True, default="")
            active = models.BooleanField(default=True)
            virtual = models.BooleanField(default=False)
            assembly = models.BooleanField(default=False)
            consumable = models.BooleanField(default=False)
            variant_of = TreeForeignKey("self", on_delete=models.CASCADE, null=True)
            image = StdImageField(blank=True, null=True, variations={"thumbnail": (128, 128)}, render_variations=False)

            class Meta:
                app_label = "wled_query_tests"

            class MPTTMeta:
                parent_attr = "variant_of"

            def get_bom_item_filter(self):
                from django.db.models import Q
                return Q(part=self) | Q(part__in=self.get_ancestors(), inherited=True)

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

            @staticmethod
            def bulk_allocation_count(items):
                from django.db.models import Sum
                return {r["stock_item_id"]: r["quantity"] for r in TestAllocation.objects.filter(
                    stock_item_id__in=[item.pk for item in items],
                ).values("stock_item_id").annotate(quantity=Sum("quantity"))}

        class TestBom(models.Model):
            part = models.ForeignKey(TestPart, on_delete=models.CASCADE, related_name="bom_items")
            sub_part = models.ForeignKey(TestPart, on_delete=models.CASCADE, related_name="used_in")
            quantity = models.DecimalField(max_digits=15, decimal_places=5, default=1)
            setup_quantity = models.DecimalField(max_digits=15, decimal_places=5, default=0)
            reference = models.CharField(max_length=100, default="")
            optional = models.BooleanField(default=False)
            consumable = models.BooleanField(default=False)
            inherited = models.BooleanField(default=False)
            validated = models.BooleanField(default=True)

            class Meta:
                app_label = "wled_query_tests"

            @property
            def is_consumable(self):
                return self.consumable or self.sub_part.consumable

            def get_required_quantity(self, count):
                return self.quantity * count + self.setup_quantity

        class TestManufacturerPart(models.Model):
            part = models.ForeignKey(TestPart, on_delete=models.CASCADE)
            MPN = models.CharField(max_length=100)

            class Meta:
                app_label = "wled_query_tests"

        class TestBuild(MPTTModel):
            reference = models.CharField(max_length=50)
            title = models.CharField(max_length=100, default="")
            part = models.ForeignKey(TestPart, on_delete=models.CASCADE)
            parent = TreeForeignKey("self", on_delete=models.CASCADE, null=True)
            take_from = models.ForeignKey(TestLocation, on_delete=models.SET_NULL, null=True)
            quantity = models.PositiveIntegerField(default=3)
            completed = models.PositiveIntegerField(default=0)
            status = models.IntegerField(default=10)

            class Meta:
                app_label = "wled_query_tests"

            @property
            def is_active(self):
                return self.status in (10, 20, 25)

        class TestBuildLine(models.Model):
            build = models.ForeignKey(TestBuild, on_delete=models.CASCADE)
            bom_item = models.ForeignKey(TestBom, on_delete=models.CASCADE)
            quantity = models.DecimalField(max_digits=15, decimal_places=5, default=1)
            consumed = models.DecimalField(max_digits=15, decimal_places=5, default=0)

            class Meta:
                app_label = "wled_query_tests"

        class TestAllocation(models.Model):
            build_line = models.ForeignKey(TestBuildLine, on_delete=models.CASCADE)
            stock_item = models.ForeignKey(TestStock, on_delete=models.CASCADE)
            quantity = models.DecimalField(max_digits=15, decimal_places=5, default=1)

            class Meta:
                app_label = "wled_query_tests"

        cls.Location, cls.Part, cls.Stock = TestLocation, TestPart, TestStock
        cls.Category, cls.Parameter, cls.Template, cls.ModelType = TestCategory, TestParameter, TestTemplate, TestModelType
        cls.Bom = TestBom
        cls.Build, cls.BuildLine, cls.Allocation = TestBuild, TestBuildLine, TestAllocation
        cls.schema_models = (cls.Location, cls.Category, cls.ModelType, cls.Template, cls.Parameter, cls.Part, cls.Stock, TestManufacturerPart, cls.Bom, cls.Build, cls.BuildLine, cls.Allocation)
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
            "part.models": module("part.models", Part=cls.Part, BomItem=cls.Bom),
            "stock.models": module("stock.models", StockItem=cls.Stock),
            "common.models": module("common.models", Parameter=cls.Parameter),
            "build.models": module("build.models", Build=cls.Build, BuildLine=cls.BuildLine, BuildItem=cls.Allocation),
        }
        with patch.dict(sys.modules, dependencies):
            cls.finder_module = importlib.import_module("finder_query_test.finder")
            cls.bom_module = importlib.import_module("finder_query_test.bom")
            cls.build_module = importlib.import_module("finder_query_test.build_components")
            cls.picking_module = importlib.import_module("finder_query_test.picking")

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

    def typed_part(self, name, path, **fields):
        category, _ = self.Category.objects.get_or_create(pathstring=path, defaults={"name": path.rsplit("/", 1)[-1]})
        return self.Part.objects.create(name=name, category=category, **fields)

    def test_interpreted_type_excludes_related_keywords_but_preserves_typed_search(self):
        from django.test.utils import CaptureQueriesContext
        magnet = self.typed_part("Disc 10x3", "Mechanical/Magnets", description="magnet")
        motor = self.typed_part("Coreless DC", "Electronics/Transducers/Vibration Motors", description="permanent magnet motor")
        self.typed_part("Charger IC", "Electronics/ICs/Power Management (PMIC)/Battery Chargers", description="battery charger")
        with CaptureQueriesContext(self.connection) as queries:
            results = self.finder().search(["magnet", "magnet", "battery"], component_queries=[1, 2])["results"]
        self.assertEqual({row["part"]["id"] for row in results[0]["matches"]}, {magnet.pk, motor.pk})
        self.assertEqual([row["part"]["id"] for row in results[1]["matches"]], [magnet.pk])
        self.assertEqual(results[2]["matches"], [])
        self.assertEqual(results[2]["type_filter"]["name"], "battery")
        self.assertFalse(results[0]["component_query"])
        self.assertEqual(len(queries), 5)  # 3 candidate searches + 1 parameter batch + 1 stock query.
        self.assertEqual(self.plugin.client.requests, [])

    def test_interpreted_category_matches_family_without_redundant_keyword(self):
        ring = self.typed_part("771-915", "Mechanical/O-Rings", description="silicone seal")
        self.typed_part("771-992", "Mechanical/O-Rings", description="rubber seal")
        self.typed_part("Silicone glue", "Mechanical/Tools & Consumables/Adhesives", keywords="silicone O-ring")
        result = self.finder().search(["silicone O-ring"], component_queries=[0])["results"][0]
        self.assertEqual([row["part"]["id"] for row in result["matches"]], [ring.pk])

    def test_component_scope_requires_exact_category_boundary_and_active_physical_part(self):
        wanted = self.typed_part("Disc", "Mechanical/Magnets/Neodymium")
        self.typed_part("Accessory", "Mechanical/Magnets Accessories", keywords="magnet")
        self.typed_part("Wrong branch", "Electronics/Magnets", keywords="magnet")
        self.typed_part("Inactive", "Mechanical/Magnets", active=False)
        self.typed_part("Virtual", "Mechanical/Magnets", virtual=True)
        self.Part.objects.create(name="magnet")
        result = self.finder().search(["magnet"], component_queries=[0])["results"][0]
        self.assertEqual([row["part"]["id"] for row in result["matches"]], [wanted.pk])

    def test_component_motor_and_transistor_subtypes_use_categories(self):
        pnp = self.typed_part("2N3906", "Electronics/Transistors/BJT/PNP")
        npn = self.typed_part("2N3904", "Electronics/Transistors/BJT/NPN")
        dc = self.typed_part("25GA370", "Electronics/Motors/DC Gear Motors")
        vibration = self.typed_part("Coreless", "Electronics/Transducers/Vibration Motors")
        stepper = self.typed_part("NEMA17", "Electronics/Motors/Stepper Motors", keywords="DC motor")
        self.typed_part("Driver", "Electronics/ICs/Motor Drivers", keywords="DC motor PNP transistor")
        result = self.finder().search(["PNP transistor", "NPN transistor", "DC motor", "motor"], component_queries=[0, 1, 2, 3])
        self.assertEqual([{m["part"]["id"] for m in row["matches"]} for row in result["results"]],
                         [{pnp.pk}, {npn.pk}, {dc.pk, vibration.pk}, {dc.pk, vibration.pk, stepper.pk}])

    def test_scoped_values_keep_equivalence_and_extra_constraints(self):
        part = self.value_part("C0603", "Capacitors", "Capacitance", "nF", .0000001)
        self.Category.objects.filter(pk=part.category_id).update(pathstring="Electronics/Passives/Capacitors/Ceramic")
        self.Part.objects.filter(pk=part.pk).update(keywords="ceramic")
        self.typed_part("Nearby", "Electronics/ICs/Op Amps", keywords="100nF capacitor ceramic")
        results = self.finder().search(["0.1uF capacitor ceramic", "100nF capacitor electrolytic"], component_queries=[0, 1])["results"]
        self.assertEqual([m["part"]["id"] for m in results[0]["matches"]], [part.pk])
        self.assertEqual(results[0]["value_match"]["display"], "100 nF")
        self.assertEqual(results[1]["matches"], [])

    def test_generic_resistor_scope_excludes_variable_resistors_but_explicit_variable_works(self):
        fixed = self.typed_part("10k resistor", "Electronics/Passives/Resistors/Fixed")
        variable = self.typed_part("10k potentiometer", "Electronics/Passives/Resistors/Variable")
        result = self.finder().search(["10k resistor", "10k variable resistor"], component_queries=[0, 1])["results"]
        self.assertEqual([m["part"]["id"] for m in result[0]["matches"]], [fixed.pk])
        self.assertEqual([m["part"]["id"] for m in result[1]["matches"]], [variable.pk])
        self.assertEqual(result[0]["type_filter"]["excluded_categories"], ["Electronics/Passives/Resistors/Variable"])

    def test_related_object_and_unknown_intent_use_full_literal_query(self):
        driver = self.typed_part("DRV", "Electronics/ICs/Motor Drivers", keywords="motor driver")
        result = self.finder().search(["motor driver", "NE555"], component_queries=[0, 1])["results"]
        self.assertEqual([m["part"]["id"] for m in result[0]["matches"]], [driver.pk])
        self.assertIsNone(result[0]["type_filter"])
        self.assertIsNone(result[1]["type_filter"])
        self.assertEqual([m["part"]["id"] for m in result[1]["matches"]], [self.part.pk])

    def test_component_pagination_stays_scoped_and_cursor_cannot_change_mode(self):
        wanted = [self.typed_part("Disc " + str(i), "Mechanical/Magnets") for i in range(3)]
        self.typed_part("magnet motor", "Electronics/Motors")
        first = self.finder().search(["magnet"], limit=1, component_queries=[0])["results"][0]
        cursor = first["next_cursor"]
        with self.assertRaises(ValueError):
            self.finder().search(["magnet"], cursor=cursor)
        # A literal cursor cannot be reused for scoped searches, either.
        self.Part.objects.create(name="NE555 board")
        literal_cursor = self.finder().search(["NE555"], limit=1)["results"][0]["next_cursor"]
        with self.assertRaises(ValueError):
            self.finder().search(["NE555"], component_queries=[0], cursor=literal_cursor)
        ids = [first["matches"][0]["part"]["id"]]
        while cursor:
            page = self.finder().search(["magnet"], limit=1, component_queries=[0], cursor=cursor)["results"][0]
            ids.extend(m["part"]["id"] for m in page["matches"])
            cursor = page["next_cursor"]
        self.assertEqual(ids, [part.pk for part in wanted])

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
        self.assertEqual(len(queries), 3)  # Candidate, parameter batch and stock query.
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
        self.assertEqual(len(queries), 3)  # One distinct query, one parameter batch, one stock query.

    def test_result_specifications_are_batched_bounded_prioritized_and_part_scoped(self):
        from django.test.utils import CaptureQueriesContext
        kind = self.ModelType.objects.create(app_label="part", model="part")
        other_kind = self.ModelType.objects.create(app_label="stock", model="stockitem")
        other = self.Part.objects.create(name="NE555 alternative")
        templates = {}
        for name, units, data in (
            ("Color", "", "Black"), ("Mounting Type", "", "SMD"),
            ("Material", "", "x" * 200), ("Voltage", "V", "12"),
            ("Resistance", "ohms", "1000"), ("Package / Case", "", "0805"),
        ):
            template = self.Template.objects.create(name=name, units=units)
            templates[name] = template
            for part in (self.part, other):
                self.Parameter.objects.create(model_type=kind, model_id=part.pk, template=template, data=data)
        blank = self.Template.objects.create(name="Capacitance", units="F")
        self.Parameter.objects.create(model_type=kind, model_id=self.part.pk, template=blank, data="   ")
        self.Parameter.objects.create(model_type=other_kind, model_id=self.part.pk,
                                      template=templates["Resistance"], data="WRONG MODEL")
        with CaptureQueriesContext(self.connection) as queries:
            result = self.finder().search(["NE555", "NE555"])
        self.assertEqual(len(queries), 3)  # Repeated query and parts do not add per-part reads.
        self.assertEqual(len(result["results"][0]["matches"]), 2)
        for match in result["results"][0]["matches"]:
            specs = match["part"]["specifications"]
            self.assertEqual([row["name"] for row in specs], ["Resistance", "Voltage", "Material", "Package / Case"])
            self.assertEqual(specs[0], {"name": "Resistance", "value": "1000", "units": "ohms"})
            self.assertEqual(specs[2]["value"], "x" * 160 + "…")
        self.assertEqual(result["results"][0]["matches"], result["results"][1]["matches"])

    def test_empty_search_results_do_not_load_parameters_or_stock(self):
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(self.connection) as queries:
            result = self.finder().search(["not-in-fixture"])
        self.assertEqual(result["results"][0]["matches"], [])
        self.assertEqual(len(queries), 1)

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
            self.assertEqual(len(queries), 3)  # Correlated match, batched display parameters and stock.
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

    def assembly_fixture(self):
        root = self.Part.objects.create(name="System", assembly=True)
        board = self.Part.objects.create(name="PCBA", assembly=True)
        missing = self.Part.objects.create(name="Not received")
        self.Bom.objects.create(part=root, sub_part=board, quantity=2, reference="Control boards")
        self.Bom.objects.create(part=root, sub_part=self.part, quantity=1, reference="Direct chip")
        self.Bom.objects.create(part=board, sub_part=self.part, quantity=3, reference="U1-U3")
        self.Bom.objects.create(part=board, sub_part=missing, quantity=1, reference="U4")
        return root, board, missing

    def test_bom_direct_expanded_and_partial_stock_highlighting(self):
        root, board, missing = self.assembly_fixture()
        service = self.bom_module.BomService(self.plugin)
        direct = service.preview(root.pk, {"quantity": 3})
        self.assertEqual({r["part"]["id"]: Decimal(r["required_quantity"]) for r in direct["components"]}, {board.pk: 6, self.part.pk: 3})
        expanded = service.preview(root.pk, {"quantity": 3, "expand": True})
        rows = {r["part"]["id"]: r for r in expanded["components"]}
        self.assertEqual(Decimal(rows[self.part.pk]["required_quantity"]), 21)
        self.assertEqual(Decimal(rows[missing.pk]["required_quantity"]), 6)
        self.assertTrue(expanded["can_locate"])
        self.assertEqual(expanded["summary"]["locatable_components"], 1)
        self.assertEqual(self.plugin.client.requests, [])
        result = service.locate(root.pk, {"quantity": 3, "expand": True})
        self.assertEqual(result["highlighted_components"], 1)
        self.assertEqual(result["highlighted_locations"], 1)
        sets = [r for r in self.plugin.client.requests if r[1] == "POST" and isinstance(r[3].get("seg"), list) and "i" in r[3]["seg"][0]]
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0][3], {"seg": [{"id": 0, "i": [147, "FF0000", 148, "FF0000"]}]})

    def test_bom_shared_subassembly_aggregates_before_native_required_calculation(self):
        root, board, _ = self.assembly_fixture()
        other = self.Part.objects.create(name="Other assembly", assembly=True)
        self.Bom.objects.create(part=root, sub_part=other, quantity=1)
        self.Bom.objects.create(part=other, sub_part=board, quantity=1)
        self.Bom.objects.filter(part=board, sub_part=self.part).update(setup_quantity=5)
        result = self.bom_module.BomService(self.plugin).preview(root.pk, {"expand": True})
        chip = next(r for r in result["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["required_quantity"]), 15)  # 1 direct + 3 boards * 3 + one setup of 5.

    def test_bom_uses_unallocated_quantities_and_excludes_reserved_locations(self):
        root, _, _ = self.assembly_fixture()
        reserved = {s.pk: s.quantity for s in self.Stock.objects.all()}
        free_location = self.Location.objects.create(name="Free", pathstring="Root / Free", parent=self.root,
            metadata={"wled_indicator": {"controller": "B", "led": 27}})
        self.Stock.objects.create(part=self.part, location=free_location, quantity=2)
        service = self.bom_module.BomService(self.plugin)
        with patch.object(self.Stock, "bulk_allocation_count", return_value=reserved):
            plan = service.preview(root.pk, {"quantity": 3})
        row = next(r for r in plan["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(row["stock_quantity"]), 27)
        self.assertEqual(Decimal(row["available_quantity"]), 2)
        self.assertEqual(Decimal(row["shortage"]), 1)
        self.assertEqual(plan["controller_leds"], {"B": [27]})

    def test_bom_reports_unmapped_missing_location_and_native_unavailable_stock(self):
        root, _, missing = self.assembly_fixture()
        self.Stock.objects.all().update(available=False)
        self.Stock.objects.create(part=self.part, location=None, quantity=1)
        unmapped = self.Location.objects.create(name="Unmapped", pathstring="Unmapped")
        self.Stock.objects.create(part=missing, location=unmapped, quantity=2)
        self.Stock.objects.create(part=missing, location=self.first, quantity=100, available=False)
        plan = self.bom_module.BomService(self.plugin).preview(root.pk, {"expand": True})
        self.assertFalse(plan["can_locate"])
        chip = next(r for r in plan["components"] if r["part"]["id"] == self.part.pk)
        other = next(r for r in plan["components"] if r["part"]["id"] == missing.pk)
        self.assertEqual(Decimal(chip["available_quantity"]), 1)
        self.assertIn("no assigned location", chip["locations"][0]["reason"])
        self.assertEqual(Decimal(other["stock_quantity"]), 2)
        self.assertIn("no wled_indicator", other["locations"][0]["reason"])

    def test_bom_optional_consumable_and_virtual_components(self):
        root, _, missing = self.assembly_fixture()
        self.Bom.objects.filter(part=root, sub_part=self.part).update(optional=True, consumable=True)
        service = self.bom_module.BomService(self.plugin)
        default = service.preview(root.pk, {})
        self.assertEqual(default["summary"]["optional_lines_skipped"], 1)
        included = service.preview(root.pk, {"include_optional": True})
        chip = next(r for r in included["components"] if r["part"]["id"] == self.part.pk)
        self.assertTrue(chip["sources"][0]["consumable"])
        self.Part.objects.filter(pk=self.part.pk).update(virtual=True)
        plan = service.preview(root.pk, {"include_optional": True})
        self.assertFalse(plan["can_locate"])

    def test_bom_inherits_only_flagged_bom_lines_for_part_variants(self):
        template = self.Part.objects.create(name="Template", assembly=True)
        self.Bom.objects.create(part=template, sub_part=self.part, quantity=2, inherited=True)
        excluded = self.Part.objects.create(name="Not inherited")
        self.Bom.objects.create(part=template, sub_part=excluded, quantity=1, inherited=False)
        variant = self.Part.objects.create(name="Variant", assembly=True, variant_of=template)
        result = self.bom_module.BomService(self.plugin).preview(variant.pk, {})
        self.assertEqual([r["part"]["id"] for r in result["components"]], [self.part.pk])
        self.assertEqual(Decimal(result["components"][0]["required_quantity"]), 2)

    def test_bom_cycle_limits_and_empty_bom_never_operate_hardware(self):
        root, board, _ = self.assembly_fixture()
        service = self.bom_module.BomService(self.plugin)
        for setting, value in (("MAX_PARTS", 2), ("MAX_LINES", 1), ("MAX_DEPTH", 0), ("MAX_STOCK_ITEMS", 1)):
            with self.subTest(setting=setting), patch.object(self.bom_module, setting, value), self.assertRaises(ValueError):
                service.locate(root.pk, {"expand": True})
        self.Bom.objects.create(part=board, sub_part=root)
        with self.assertRaisesRegex(ValueError, "circular"):
            service.locate(root.pk, {"expand": True})
        empty = self.Part.objects.create(name="Empty assembly", assembly=True)
        self.assertEqual(service.preview(empty.pk, {})["components"], [])
        with self.assertRaises(self.bom_module.ComponentsNotLocatable):
            service.locate(empty.pk, {})
        self.assertEqual(self.plugin.client.requests, [])

    def test_bom_rechecks_stock_mapping_and_component_membership_before_locate(self):
        root, _, missing = self.assembly_fixture()
        service = self.bom_module.BomService(self.plugin)
        service.preview(root.pk, {})
        self.Location.objects.filter(pk=self.first.pk).update(metadata={"wled_indicator": {"controller": "A", "led": 4}})
        result = service.locate(root.pk, {"component_id": self.part.pk, "controller_leds": {"B": [50]}})
        self.assertEqual(result["highlighted_components"], 1)
        self.assertEqual(self.plugin.client.requests[-1][3], {"seg": [{"id": 0, "i": [4, "FF0000"]}]})
        self.plugin.client.requests.clear()
        with self.assertRaisesRegex(ValueError, "not in this assembly"):
            service.locate(root.pk, {"component_id": missing.pk})
        self.Stock.objects.all().update(quantity=0)
        with self.assertRaises(self.bom_module.ComponentsNotLocatable):
            service.locate(root.pk, {"component_id": self.part.pk})
        self.assertEqual(self.plugin.client.requests, [])

    def test_bom_depth_limit_counts_longer_paths_through_shared_assemblies(self):
        root = self.Part.objects.create(name="Root assembly", assembly=True)
        shared = self.Part.objects.create(name="Shared", assembly=True)
        middle = self.Part.objects.create(name="Middle", assembly=True)
        self.Bom.objects.create(part=root, sub_part=shared)
        self.Bom.objects.create(part=root, sub_part=middle)
        self.Bom.objects.create(part=middle, sub_part=shared)
        self.Bom.objects.create(part=shared, sub_part=self.part)
        with patch.object(self.bom_module, "MAX_DEPTH", 2), self.assertRaisesRegex(ValueError, "nested levels"):
            self.bom_module.BomService(self.plugin).locate(root.pk, {"expand": True})
        self.assertEqual(self.plugin.client.requests, [])

    def test_bom_stock_queries_stay_batched_as_component_count_grows(self):
        from django.test.utils import CaptureQueriesContext
        root, _, _ = self.assembly_fixture()
        with CaptureQueriesContext(self.connection) as before:
            self.bom_module.BomService(self.plugin).preview(root.pk, {})
        for i in range(30):
            part = self.Part.objects.create(name=f"Extra {i}")
            self.Bom.objects.create(part=root, sub_part=part)
            self.Stock.objects.create(part=part, location=self.first)
        with CaptureQueriesContext(self.connection) as after:
            plan = self.bom_module.BomService(self.plugin).preview(root.pk, {})
        self.assertEqual(len(before), len(after))
        self.assertEqual(plan["summary"]["unique_locations"], 1)
        self.assertEqual(self.plugin.client.requests, [])

    def build_fixture(self):
        root, board, missing = self.assembly_fixture()
        build = self.Build.objects.create(reference="BO-System", part=root, quantity=3)
        child = self.Build.objects.create(reference="BO-PCBA", part=board, quantity=2, parent=build)
        root_line = self.BuildLine.objects.create(build=build, bom_item=self.Bom.objects.get(part=root, sub_part=self.part), quantity=5, consumed=2)
        child_line = self.BuildLine.objects.create(build=child, bom_item=self.Bom.objects.get(part=board, sub_part=self.part), quantity=7, consumed=1)
        self.BuildLine.objects.create(build=build, bom_item=self.Bom.objects.get(part=root, sub_part=board), quantity=3)
        self.BuildLine.objects.create(build=child, bom_item=self.Bom.objects.get(part=board, sub_part=missing), quantity=2)
        return build, child, root_line, child_line

    def test_build_requirements_use_saved_lines_and_consumed_quantities(self):
        build, child, line, _ = self.build_fixture()
        self.Bom.objects.filter(pk=line.bom_item_id).update(quantity=999)
        service = self.build_module.BuildComponentService(self.plugin)
        plan = service.preview(build.pk, {})
        chip = next(r for r in plan["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["required_quantity"]), 3)
        self.assertEqual(Decimal(chip["consumed_quantity"]), 2)
        self.assertEqual(plan["quantity"], 3)
        self.assertEqual(plan["summary"]["builds"], 1)
        combined = service.preview(build.pk, {"include_subbuilds": True})
        chip = next(r for r in combined["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["required_quantity"]), 9)
        self.assertEqual({r["build"]["reference"] for r in chip["sources"]}, {"BO-System", "BO-PCBA"})
        board = next(r for r in combined["components"] if r["planned_outputs"])
        self.assertEqual(board["planned_outputs"], [{"build": "BO-PCBA", "quantity": 2}])
        self.assertEqual(Decimal(board["available_quantity"]), 0)
        self.assertEqual(self.plugin.client.requests, [])

    def test_build_includes_own_allocations_and_excludes_reservations_for_other_work(self):
        build, child, line, child_line = self.build_fixture()
        self.Stock.objects.all().delete()
        allocated = self.Stock.objects.create(part=self.part, location=self.first, quantity=5)
        self.Allocation.objects.create(build_line=line, stock_item=allocated, quantity=2)
        self.Allocation.objects.create(build_line=child_line, stock_item=allocated, quantity=3)
        service = self.build_module.BuildComponentService(self.plugin)
        plan = service.preview(build.pk, {})
        chip = next(r for r in plan["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["available_quantity"]), 2)
        self.assertEqual(Decimal(chip["allocated_quantity"]), 2)
        self.assertEqual(Decimal(chip["shortage"]), 1)
        self.assertTrue(chip["can_locate"])
        combined = service.preview(build.pk, {"include_subbuilds": True})
        chip = next(r for r in combined["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["available_quantity"]), 5)
        self.assertEqual(Decimal(chip["shortage"]), 4)

    def test_build_shared_free_stock_is_not_counted_twice_across_subbuilds(self):
        build, child, line, child_line = self.build_fixture()
        self.BuildLine.objects.filter(pk__in=[line.pk, child_line.pk]).update(quantity=20, consumed=0)
        result = self.build_module.BuildComponentService(self.plugin).preview(build.pk, {"include_subbuilds": True})
        chip = next(r for r in result["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["available_quantity"]), 25)
        self.assertEqual(Decimal(chip["required_quantity"]), 40)
        self.assertEqual(Decimal(chip["shortage"]), 15)
        self.assertEqual(result["summary"]["unique_locations"], 1)

    def test_build_source_restrictions_apply_to_free_stock_but_preserve_explicit_allocations(self):
        build, child, line, _ = self.build_fixture()
        allowed = self.Location.objects.create(name="Source", pathstring="Source", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        self.Stock.objects.create(part=self.part, location=allowed, quantity=1)
        self.Build.objects.filter(pk=build.pk).update(take_from=allowed)
        service = self.build_module.BuildComponentService(self.plugin)
        result = service.preview(build.pk, {})
        self.assertEqual(result["controller_leds"], {"B": [27]})
        chip = next(r for r in result["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["shortage"]), 2)
        allocated_stock = self.Stock.objects.filter(location=self.first).first()
        self.Stock.objects.filter(pk=allocated_stock.pk).update(quantity=2)
        self.Allocation.objects.create(build_line=line, stock_item=allocated_stock, quantity=2)
        result = service.preview(build.pk, {})
        self.assertEqual(set(result["controller_leds"]), {"A", "B"})
        chip = next(r for r in result["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["shortage"]), 0)

    def test_build_fully_allocated_requirements_highlight_allocated_stock_only(self):
        build, child, line, _ = self.build_fixture()
        allocated_location = self.Location.objects.create(name="Allocated", pathstring="Allocated", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        stock = self.Stock.objects.create(part=self.part, location=allocated_location, quantity=3)
        self.Allocation.objects.create(build_line=line, stock_item=stock, quantity=3)
        result = self.build_module.BuildComponentService(self.plugin).preview(build.pk, {})
        self.assertEqual(result["controller_leds"], {"B": [27]})

    def test_build_unavailable_overallocated_and_alternative_allocations_are_accounted_for(self):
        build, child, line, _ = self.build_fixture()
        self.Stock.objects.all().delete()
        alternative = self.Part.objects.create(name="Allocated substitute")
        stock = self.Stock.objects.create(part=alternative, location=self.first, quantity=1)
        self.Allocation.objects.create(build_line=line, stock_item=stock, quantity=5)
        service = self.build_module.BuildComponentService(self.plugin)
        plan = service.preview(build.pk, {})
        chip = next(r for r in plan["components"] if r["part"]["id"] == self.part.pk)
        self.assertEqual(Decimal(chip["allocated_quantity"]), 5)
        self.assertEqual(Decimal(chip["allocated_available_quantity"]), 1)
        self.assertEqual(Decimal(chip["shortage"]), 2)
        self.assertIn("Allocated substitute", chip["locations"][0]["stock_parts"])
        self.Stock.objects.filter(pk=stock.pk).update(available=False)
        self.assertFalse(service.preview(build.pk, {})["can_locate"])

    def test_build_ignores_consumed_lines_and_closed_builds(self):
        build, child, line, _ = self.build_fixture()
        service = self.build_module.BuildComponentService(self.plugin)
        self.BuildLine.objects.filter(pk=line.pk).update(consumed=5)
        self.assertFalse(service.preview(build.pk, {})["can_locate"])
        self.Build.objects.filter(pk=child.pk).update(status=40)
        self.assertEqual(service.preview(build.pk, {"include_subbuilds": True})["summary"]["builds"], 1)
        for status in (30, 40):
            self.Build.objects.filter(pk=build.pk).update(status=status)
            self.assertEqual(service.preview(build.pk, {"include_subbuilds": True})["components"], [])
            with self.assertRaises(self.bom_module.ComponentsNotLocatable):
                service.locate(build.pk, {})
        self.assertEqual(self.plugin.client.requests, [])

    def test_build_limits_and_fresh_locate_recheck_stock_mappings_and_membership(self):
        build, child, line, _ = self.build_fixture()
        service = self.build_module.BuildComponentService(self.plugin)
        for name, value, options in (("MAX_LINES", 1, {}), ("MAX_STOCK_ITEMS", 1, {}), ("MAX_PARTS", 1, {}), ("MAX_BUILDS", 1, {"include_subbuilds": True})):
            with patch.object(self.build_module, name, value), self.assertRaises(ValueError):
                service.locate(build.pk, options)
        stock = self.Stock.objects.first()
        self.Allocation.objects.create(build_line=line, stock_item=stock)
        with patch.object(self.build_module, "MAX_ALLOCATIONS", 0), self.assertRaises(ValueError):
            service.locate(build.pk, {})
        self.assertEqual(self.plugin.client.requests, [])
        service.preview(build.pk, {})
        self.Location.objects.filter(pk=self.first.pk).update(metadata={"wled_indicator": {"controller": "A", "led": 4}})
        result = service.locate(build.pk, {"component_id": self.part.pk, "controller_leds": {"B": [55]}})
        self.assertEqual(result["highlighted_components"], 1)
        self.assertEqual(self.plugin.client.requests[-1][3], {"seg": [{"id": 0, "i": [4, "FF0000"]}]})
        self.plugin.client.requests.clear()
        self.BuildLine.objects.filter(pk=line.pk).update(consumed=5)
        with self.assertRaises(ValueError):
            service.locate(build.pk, {"component_id": self.part.pk})
        self.assertEqual(self.plugin.client.requests, [])

    def test_build_stock_and_allocation_queries_stay_batched(self):
        from django.test.utils import CaptureQueriesContext
        build, child, line, _ = self.build_fixture()
        with CaptureQueriesContext(self.connection) as before:
            self.build_module.BuildComponentService(self.plugin).preview(build.pk, {})
        for i in range(30):
            part = self.Part.objects.create(name=f"Build component {i}")
            bom = self.Bom.objects.create(part=build.part, sub_part=part)
            self.BuildLine.objects.create(build=build, bom_item=bom, quantity=2)
            self.Stock.objects.create(part=part, location=self.first)
        with CaptureQueriesContext(self.connection) as after:
            self.build_module.BuildComponentService(self.plugin).preview(build.pk, {})
        self.assertEqual(len(before), len(after))
        self.assertLessEqual(len(after), 5)
        self.assertEqual(self.plugin.client.requests, [])

    def test_picking_suggestions_cap_quantities_and_keep_split_stock_and_shortages(self):
        root, board, missing = self.assembly_fixture()
        self.Stock.objects.all().delete()
        self.Bom.objects.filter(part=root, sub_part=self.part).update(quantity=Decimal("0.3"))
        second = self.Location.objects.create(name="Second", pathstring="Second", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        self.Stock.objects.create(part=self.part, location=self.first, quantity=Decimal("0.1"))
        self.Stock.objects.create(part=self.part, location=second, quantity=Decimal("0.15"))
        plan = self.bom_module.BomService(self.plugin).preview(root.pk, {})
        picks = [item for group in plan["picking"]["locations"] for item in group["items"] if item["part_id"] == self.part.pk]
        self.assertEqual(sum(Decimal(pick["quantity"]) for pick in picks), Decimal("0.25"))
        shortage = next(item for item in plan["picking"]["shortages"] if item["part_id"] == self.part.pk)
        self.assertEqual(Decimal(shortage["quantity"]), Decimal("0.05"))
        self.Stock.objects.create(part=self.part, location=second, quantity=100)
        plan = self.bom_module.BomService(self.plugin).preview(root.pk, {})
        self.assertEqual(sum(Decimal(item["quantity"]) for group in plan["picking"]["locations"] for item in group["items"] if item["part_id"] == self.part.pk), Decimal("0.3"))
        self.assertEqual(self.plugin.client.requests, [])

    def test_picking_build_quantities_follow_source_and_allocation_plan(self):
        build, child, line, child_line = self.build_fixture()
        self.BuildLine.objects.filter(pk__in=[line.pk, child_line.pk]).update(quantity=20, consumed=0)
        plan = self.build_module.BuildComponentService(self.plugin).preview(build.pk, {"include_subbuilds": True})
        picked = sum(Decimal(item["quantity"]) for group in plan["picking"]["locations"] for item in group["items"] if item["part_id"] == self.part.pk)
        self.assertEqual(picked, 25)
        self.assertEqual(Decimal(next(item for item in plan["picking"]["shortages"] if item["part_id"] == self.part.pk)["quantity"]), 15)
        source = self.Location.objects.create(name="Source", pathstring="Source", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        self.Build.objects.filter(pk=build.pk).update(take_from=source)
        self.Stock.objects.create(part=self.part, location=source, quantity=3)
        plan = self.build_module.BuildComponentService(self.plugin).preview(build.pk, {})
        self.assertEqual([group["location"]["id"] for group in plan["picking"]["locations"]], [source.pk])
        self.assertEqual(Decimal(plan["picking"]["locations"][0]["items"][0]["quantity"]), 3)

    def test_picking_excludes_collected_components_without_stock_or_allocation_writes(self):
        root, board, _ = self.assembly_fixture()
        second = self.Location.objects.create(name="Board box", pathstring="Board box", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        self.Stock.objects.create(part=board, location=second, quantity=10)
        service = self.bom_module.BomService(self.plugin)
        plan = service.preview(root.pk, {})
        before = list(self.Stock.objects.values_list("pk", "quantity"))
        result = service.locate(root.pk, {"remaining_component_ids": [board.pk], "picking_revision": plan["picking"]["revision"]})
        self.assertEqual(result["highlighted_components"], 1)
        self.assertEqual(self.plugin.client.requests[-1][0], "B")
        self.assertEqual(self.plugin.client.requests[-1][3], {"seg": [{"id": 0, "i": [27, "FF0000"]}]})
        self.assertEqual(list(self.Stock.objects.values_list("pk", "quantity")), before)
        self.assertEqual(self.Allocation.objects.count(), 0)
        self.plugin.client.requests.clear()
        with self.assertRaises(self.bom_module.ComponentsNotLocatable):
            service.locate(root.pk, {"remaining_component_ids": [], "picking_revision": plan["picking"]["revision"]})
        self.assertEqual(self.plugin.client.requests, [])

    def test_picking_rejects_changed_requirements_and_unknown_ids_before_hardware(self):
        picking = self.picking_module
        root, board, _ = self.assembly_fixture()
        service = self.bom_module.BomService(self.plugin)
        plan = service.preview(root.pk, {})
        for ids, revision in (([999999], plan["picking"]["revision"]), ([self.part.pk], "0" * 64)):
            with self.assertRaises(picking.PickingChanged):
                service.locate(root.pk, {"remaining_component_ids": ids, "picking_revision": revision})
        self.Bom.objects.filter(part=root, sub_part=self.part).update(quantity=2)
        with self.assertRaises(picking.PickingChanged):
            service.locate(root.pk, {"remaining_component_ids": [self.part.pk], "picking_revision": plan["picking"]["revision"]})
        self.assertEqual(self.plugin.client.requests, [])

    def test_picking_fingerprints_survive_stock_mapping_and_allocation_changes(self):
        build, child, line, _ = self.build_fixture()
        service = self.build_module.BuildComponentService(self.plugin)
        first = service.preview(build.pk, {})
        self.Stock.objects.all().update(quantity=2)
        self.Allocation.objects.create(build_line=line, stock_item=self.Stock.objects.first(), quantity=1)
        self.Location.objects.filter(pk=self.first.pk).update(metadata={})
        second = service.preview(build.pk, {})
        self.assertEqual(first["picking"]["revision"], second["picking"]["revision"])
        self.BuildLine.objects.filter(pk=line.pk).update(consumed=3)
        changed = service.preview(build.pk, {})
        self.assertNotEqual(first["picking"]["revision"], changed["picking"]["revision"])
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
