"""Run with: python3 -B -m unittest discover -s <plugin>/tests -v."""

from __future__ import annotations

import json
import threading
import tempfile
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from support import (
    BuildItem, FakePlugin, Location, Query, StockItem, inventory_fixture, modules,
)


class OfflineTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        lock = patch.object(modules.locking, "lock_path", return_value=Path(temporary.name) / "hardware.lock")
        lock.start()
        self.addCleanup(lock.stop)
        # An unexpected real HTTP request must fail, including in preview tests.
        guard = patch.object(modules.wled, "urlopen", side_effect=AssertionError("Network disabled in tests"))
        guard.start()
        self.addCleanup(guard.stop)
        self.plugin = FakePlugin()
        self.client = self.plugin.client
        self.fixture = inventory_fixture()
        self.service = modules.locator.LocatorService(self.plugin)


class LocateCompatibilityTests(OfflineTest):
    def test_part_stock_availability_grouping_and_skipped_reasons(self):
        result = self.service.preview_part_object(self.fixture.part)
        self.assertEqual(result["controller_leds"], {"A": [147, 148], "B": [27]})
        self.assertEqual(result["summary"], {
            "stock_items": 7, "lit_items": 4, "skipped_items": 3,
            "unique_locations": 3, "unique_leds": 3,
        })
        self.assertEqual([entry["item"]["id"] for entry in result["skipped"]], [5, 6, 7])
        self.assertEqual(result["locations"][0]["item_count"], 2)
        self.assertEqual(result["lit"][0]["item"]["quantity"], "2")
        self.assertEqual(self.client.requests, [])

    def test_build_allocation_grouping_and_missing_stock(self):
        result = self.service.preview_build_object(self.fixture.build)
        self.assertEqual(result["summary"], {
            "allocations": 5, "lit_allocations": 2, "skipped_allocations": 3,
            "unique_locations": 1, "unique_leds": 2,
        })
        self.assertEqual(result["locations"][0]["allocation_count"], 2)
        self.assertEqual([row["allocation"]["id"] for row in result["skipped"]], [3, 4, 5])
        self.assertEqual(self.client.requests, [])

    def test_parent_uses_mapped_leaves_and_keeps_shared_mappings(self):
        result = self.service.get_location_led_plan(self.fixture.root)
        self.assertEqual(result["mode"], "parent")
        self.assertEqual(result["controller_leds"], {"A": [147, 148], "B": [27]})
        self.assertEqual(len(result["lit"]), 3)
        self.assertEqual(len(result["skipped"]), 2)
        self.assertEqual(self.fixture.shared.metadata["wled_indicator"]["leds"], [147])
        self.assertEqual(sum(loc.child_checks for loc in Location.objects), 0)

    def test_multiple_parts_can_contribute_to_one_plan_without_losing_order(self):
        targets = modules.planning.IndicatorCollection()
        for part in (self.fixture.part, self.fixture.other):
            targets.extend(self.service.preview_part_object(part)["indicators"])
        self.assertEqual(targets.controller_leds, {"A": [147, 148], "B": [27]})
        self.assertEqual(self.client.requests, [])

    def test_led_identity_includes_controller(self):
        targets = modules.planning.IndicatorCollection()
        targets.extend([{"controller": "B", "led": 1}, {"controller": "A", "led": 1}] * 3)
        self.assertEqual(targets.controller_leds, {"B": [1], "A": [1]})
        self.assertEqual(targets.leds, [1])
        self.assertEqual(len(targets.indicators), 2)

    def test_stock_item_locate_keeps_response_shape(self):
        result = self.service.locate_stock_item_object(self.fixture.items[0])
        self.assertEqual(set(result), {
            "item", "location", "controller", "led", "leds", "indicators",
            "controller_leds", "lit", "skipped", "wled",
        })
        self.assertEqual(result["leds"], [147, 148])
        self.assertEqual(result["wled"], {
            "success": True, "clear": {"controllers": {"A": {"success": True}, "B": {"success": True}}},
        })
        self.assertEqual(self.fixture.first.metadata_reads, 1)

    def test_unavailable_stock_still_clears_before_error(self):
        with self.assertRaisesRegex(ValueError, "not currently in stock"):
            self.service.locate_stock_item_object(self.fixture.items[6])
        self.assertEqual([row[0] for row in self.client.requests if row[1] == "POST"], ["A", "B"])

    def test_missing_location_preview_performs_no_hardware_operations(self):
        result = self.service.preview_stock_item_object(self.fixture.items[7])
        self.assertFalse(result["can_locate"])
        self.assertEqual(result["reason"], "StockItem has no assigned StockLocation")
        self.assertEqual(self.client.requests, [])

    def test_multi_location_keeps_requested_order_and_skips_missing(self):
        result = self.service.locate_locations([3, 1, 2, 999])
        self.assertEqual(result["requested_ids"], [3, 1, 2, 999])
        self.assertEqual(result["controller_leds"], {"B": [27], "A": [147, 148]})
        self.assertEqual(result["skipped"], [{"id": 999, "reason": "Location not found"}])

    def test_repeated_locations_resolve_once_including_invalid_mappings(self):
        self.service.preview_part_object(self.fixture.part)
        self.service.preview_build_object(self.fixture.build)
        for location in (self.fixture.first, self.fixture.missing, self.fixture.invalid):
            self.assertEqual(location.metadata_reads, 1)

    def test_mapping_edit_invalidates_cached_plan_and_preserves_other_metadata(self):
        self.service.get_location_led_plan(self.fixture.first)
        self.service.set_location_indicators(self.fixture.first, [4, 5, 4], "B")
        result = self.service.get_location_led_plan(self.fixture.first)
        self.assertEqual(result["controller_leds"], {"B": [4, 5]})
        self.assertEqual(self.fixture.first.metadata["unrelated"], {"keep": True})
        self.service.clear_location_indicator(self.fixture.first)
        with self.assertRaisesRegex(ValueError, "no wled_indicator"):
            self.service.get_location_led_plan(self.fixture.first)

    def test_parent_assignments_stay_disallowed(self):
        with self.assertRaisesRegex(ValueError, "Parent StockLocations"):
            self.service.set_location_indicators(self.fixture.root, [1], "A")
        self.assertEqual(self.fixture.root.saves, 0)


class WledExecutionTests(OfflineTest):
    def test_another_action_cannot_clear_or_set_while_a_locate_holds_the_lock(self):
        with modules.locking.hardware_action(), ThreadPoolExecutor(max_workers=1) as pool:
            for action in (self.client.off, lambda: self.client.set_leds([147], "A")):
                with self.assertRaises(modules.locking.LocatorBusyError):
                    pool.submit(action).result(timeout=5)
        self.assertEqual(self.client.requests, [])

    def test_normalized_controller_locate_uses_one_get_and_two_posts(self):
        self.plugin = FakePlugin([{"label": "A", "address": "a.invalid", "max_leds": 200}])
        client = self.plugin.client
        result = modules.execution.apply_controller_leds(client, {"A": [147, 148]})
        self.assertEqual([(row[1], row[2]) for row in client.requests], [
            ("GET", "/json/state"), ("POST", "/json/state"), ("POST", "/json/state"),
        ])
        self.assertEqual(client.requests[-1][3], {"seg": [{"id": 0, "i": [147, "FF0000", 148, "FF0000"]}]})
        self.assertEqual(result, {"success": True, "clear": {"success": True}})

    def test_split_segments_are_normalized_before_clear_and_light(self):
        self.client.states["A"] = {"seg": [
            {"id": 0, "start": 0, "stop": 100}, {"id": 3, "start": 100, "stop": 200},
        ]}
        modules.execution.apply_controller_leds(self.client, {"A": [147]})
        requests = [row for row in self.client.requests if row[0] == "A"]
        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[1][3], {"seg": [
            {"id": 0, "start": 0, "stop": 200}, {"id": 3, "stop": 0},
        ]})
        self.assertEqual(requests[-1][3], {"seg": [{"id": 0, "i": [147, "FF0000"]}]})

    def test_relative_segment_translation_remains_available(self):
        self.client.states["A"] = {"seg": [
            {"id": 2, "start": 0, "stop": 100}, {"id": 5, "start": 100, "stop": 200},
        ]}
        self.assertEqual(self.client.segment_led_data([147, 3], "AABBCC", "A"), [
            {"id": 2, "i": [3, "AABBCC"]}, {"id": 5, "i": [47, "AABBCC"]},
        ])

    def test_segment_state_is_checked_again_for_next_execution(self):
        modules.execution.apply_controller_leds(self.client, {"A": [147]})
        self.client.states["A"] = {"seg": [{"id": 1, "start": 50, "stop": 200}]}
        self.client.requests.clear()
        modules.execution.apply_controller_leds(self.client, {"A": [147]})
        self.assertIn(("A", "GET", "/json/state", None), self.client.requests)
        self.assertEqual(self.client.requests[1][3]["seg"][0], {"id": 0, "start": 0, "stop": 200})

    def test_clear_failure_does_not_light_any_targets_and_resets_execution_cache(self):
        self.client.failures.add(("B", "POST", "/json/state"))
        with self.assertRaises(modules.wled.WledRequestError):
            modules.execution.apply_controller_leds(self.client, {"A": [147]})
        self.assertIsNone(self.client._normalized_controllers)
        self.assertFalse(any(row[3] == {"seg": [{"id": 0, "i": [147, "FF0000"]}]} for row in self.client.requests))

    def test_auto_led_count_reads_info_once_per_client(self):
        self.plugin = FakePlugin([{"label": "A", "address": "a.invalid"}])
        for led in range(20):
            self.plugin.client.validate_led_index(led, "A")
        self.assertEqual(self.plugin.client.requests, [("A", "GET", "/json/info", None)])

    def test_failed_auto_detection_is_not_retried_for_every_mapping(self):
        self.plugin = FakePlugin([{"label": "A", "address": "a.invalid"}])
        self.plugin.client.failures.add(("A", "GET", "/json/info"))
        for led in range(5):
            with self.assertRaisesRegex(ValueError, "auto-detection failed"):
                self.plugin.client.validate_led_index(led, "A")
        self.assertEqual(len(self.plugin.client.requests), 1)

    def test_controller_save_refreshes_defaults_and_led_count(self):
        self.client.get_configured_controllers()
        self.client.save_controllers([{"label": "C", "address": "c.invalid", "max_leds": 5}])
        self.assertEqual(self.client.get_controller()["label"], "C")
        self.assertEqual(self.client.get_controller_max_leds(), 5)
        self.assertEqual(self.client.get_controller()["marker_color"], "FF0000")

    def test_invalid_direct_set_has_no_hardware_side_effects(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 199"):
            self.client.set_leds([200], "A")
        self.assertEqual(self.client.requests, [])

    def test_http_payload_and_timeout_use_existing_wire_format(self):
        client = modules.wled.WledClient(self.plugin)
        response = Mock()
        response.read.return_value = b'{"success": true}'
        response.status = 200
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(modules.wled, "urlopen", return_value=response) as http:
            self.assertEqual(client.post_state({"seg": {"i": [1, "FF0000"]}}, "A"), {"success": True})
        request = http.call_args.args[0]
        self.assertEqual(request.full_url, "http://controller-a.invalid/json/state")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"seg": {"i": [1, "FF0000"]}})
        self.assertEqual(http.call_args.kwargs["timeout"], 3)


class DashboardTests(OfflineTest):
    def test_dashboard_mapping_inspection_never_discovers_controller_counts(self):
        record = {"pk": 1, "name": "Drawer", "pathstring": "Cabinet / Drawer", "metadata": self.fixture.first.metadata}
        row = modules.dashboard.mapping_row(record, self.plugin.wled(), {"A", "B"})
        self.assertEqual(row["leds"], [148, 149])
        self.assertEqual(row["state"], "mapped")
        self.plugin.client._controllers = None
        self.plugin.settings["WLED_CONTROLLERS"] = '[{"label":"A","address":"http://a.invalid"}]'
        self.plugin.client.invalidate_configuration()
        row = modules.dashboard.mapping_row(record, self.plugin.wled(), {"A"})
        self.assertEqual(row["state"], "invalid")
        self.assertIn("no saved LED count", row["error"])
        self.assertEqual(self.plugin.client.requests, [])

    def test_dashboard_rejects_malformed_mapping_and_unbounded_selection(self):
        for metadata in (None, {"wled_indicator": []}, {"wled_indicator": "bad"}):
            row = modules.dashboard.mapping_row({"pk": 1, "name": "Drawer", "pathstring": "Drawer", "metadata": metadata}, self.plugin.wled(), {"A"})
            self.assertEqual(row["state"], "invalid")
        for ids in ([], [True], ["1"], list(range(1, 102)), [0], [2**63]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                modules.dashboard.location_ids(ids)
        self.assertEqual(modules.dashboard.location_ids([2, 1, 2]), [2, 1])


class OperationScopeTests(unittest.TestCase):
    def test_nested_scope_reuses_state_and_failure_discards_it(self):
        plugin = object()
        with self.assertRaisesRegex(RuntimeError, "test"):
            with modules.operations.operation(plugin) as outer:
                with modules.operations.operation(plugin) as inner:
                    self.assertIs(inner, outer)
                    inner.settings["key"] = "value"
                raise RuntimeError("test")
        self.assertIsNone(modules.operations.current_operation(plugin))
        with modules.operations.operation(plugin) as new:
            self.assertEqual(new.settings, {})

    def test_different_plugins_restore_the_outer_scope(self):
        first, second = object(), object()
        with modules.operations.operation(first) as outer:
            with modules.operations.operation(second):
                self.assertIsNone(modules.operations.current_operation(first))
            self.assertIs(modules.operations.current_operation(first), outer)

    def test_concurrent_threads_do_not_share_request_caches(self):
        plugin = object()
        barrier = threading.Barrier(2)
        def run(value):
            with modules.operations.operation(plugin) as current:
                current.settings["value"] = value
                barrier.wait(timeout=5)
                return current.settings["value"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, [1, 2]))
        self.assertEqual(results, [1, 2])


if __name__ == "__main__":
    unittest.main()
