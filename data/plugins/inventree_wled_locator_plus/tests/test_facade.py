"""Exercise real Django callbacks when Django is available (e.g. in Docker).

Inventory models and plugin settings remain in-memory fixtures. These tests do
not initialize InvenTree or connect to the production database.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from support import Build, BuildItem, Location, ManufacturerPart, Parameter, Part, PLUGIN_DIR, StockItem, inventory_fixture, module


@unittest.skipUnless(importlib.util.find_spec("django"), "Django is available in the InvenTree container")
class FacadeTests(unittest.TestCase):
    def setUp(self):
        from django.conf import settings
        if not settings.configured:
            settings.configure(
                INSTALLED_APPS=[], DEFAULT_CHARSET="utf-8", USE_I18N=False, SECRET_KEY="offline-test-secret",
                DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            )
        import django
        django.setup()
        from django.db.models import Q
        StockItem.IN_STOCK_FILTER = Q(quantity__gt=0)

        class PluginBase:
            def plugin_static_file(self, path):
                return path

        class SettingsStore:
            values = {
                "_WLED_CONTROLLERS": json.dumps([
                    {"label": "A", "address": "http://a.invalid", "max_leds": 200, "primary": True},
                    {"label": "B", "address": "http://b.invalid", "max_leds": 60},
                ]),
                "_CLEAR_COLOR": "000000", "_REQUEST_TIMEOUT": "3",
            }

            @classmethod
            def set_setting(cls, key, value, **kwargs):
                cls.values[key] = value

        self.store = SettingsStore
        dependencies = {
            "locator_facade_test": module("locator_facade_test", __path__=[str(PLUGIN_DIR)]),
            "build.models": module("build.models", Build=Build, BuildItem=BuildItem),
            "part.models": module("part.models", Part=Part),
            "company.models": module("company.models", ManufacturerPart=ManufacturerPart),
            "common.models": module("common.models", Parameter=Parameter),
            "stock.models": module("stock.models", StockItem=StockItem, StockLocation=Location),
            "plugin": module("plugin", InvenTreePlugin=PluginBase),
            "plugin.mixins": module("plugin.mixins", **{
                name: type(name, (), {}) for name in ("LocateMixin", "UrlsMixin", "UserInterfaceMixin")
            }),
            "plugin.models": module("plugin.models", PluginSetting=SettingsStore),
        }
        context = patch.dict(sys.modules, dependencies)
        context.start()
        self.addCleanup(context.stop)
        self.facade = importlib.import_module("locator_facade_test.plugin")
        self.operations = importlib.import_module("locator_facade_test.operations")
        self.views = importlib.import_module("locator_facade_test.views")
        self.plugin = self.facade.WledLocatorPlus()
        self.plugin._plugin_config_object = Mock(return_value=object())
        self.plugin._read_plugin_setting = Mock(side_effect=self.store.values.get)
        self.fixture = inventory_fixture()
        guard = patch("locator_facade_test.wled.urlopen", side_effect=AssertionError("Network disabled in tests"))
        guard.start()
        self.addCleanup(guard.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        lock = patch("locator_facade_test.locking.lock_path", return_value=Path(temporary.name) / "hardware.lock")
        lock.start()
        self.addCleanup(lock.stop)

    def test_settings_and_services_are_reused_only_within_one_operation(self):
        with self.operations.operation(self.plugin):
            first_client = self.plugin.wled()
            first_locator = self.plugin.locator()
            for led in range(20):
                self.plugin.validate_led_index(led, "A")
            self.assertIs(first_locator.wled, first_client)
            self.assertIs(self.plugin.locator(), first_locator)
            self.assertEqual(self.plugin._read_plugin_setting.call_count, 1)
        with self.operations.operation(self.plugin):
            self.assertIsNot(self.plugin.wled(), first_client)
            self.plugin.validate_led_index(1, "A")
        self.assertEqual(self.plugin._read_plugin_setting.call_count, 2)

    def test_saved_settings_invalidate_client_and_location_plan(self):
        with self.operations.operation(self.plugin):
            locator = self.plugin.locator()
            locator.get_location_led_plan(self.fixture.first)
            self.plugin.save_wled_controller("A", "a.invalid", 100)
            with self.assertRaisesRegex(ValueError, "between 0 and 99"):
                locator.get_location_led_plan(self.fixture.first)
            self.assertEqual(self.plugin.get_wled_controller("A")["max_leds"], 100)

    def test_saved_admin_options_are_visible_immediately(self):
        with self.operations.operation(self.plugin):
            self.assertEqual(self.plugin.get_admin_options()["request_timeout"], 3)
            self.assertEqual(self.plugin.save_admin_options(clear_color="#abcdef", request_timeout=5), {
                "clear_color": "ABCDEF", "request_timeout": 5,
            })

    def test_native_location_panel_preserves_context(self):
        result = self.plugin.get_ui_panels(None, {"target_model": "stocklocation", "target_id": 1})
        self.assertEqual(len(result), 1)
        context = result[0]["context"]
        self.assertEqual(context["current_leds"], [147, 148])
        self.assertEqual(context["current_controller"], "A")
        self.assertEqual(context["default_controller"], "A")
        self.assertEqual(context["locate_url"], "/plugin/wled-locator-plus/locate/location/1/")
        self.assertEqual(self.plugin._read_plugin_setting.call_count, 1)

    def test_controller_view_refreshes_configuration_between_requests(self):
        request = types.SimpleNamespace(user=types.SimpleNamespace(is_authenticated=True, is_superuser=True), GET={})
        views = self.views.PluginViews(self.plugin)
        first = json.loads(views.controllers(request).content)
        self.assertEqual(first["count"], 2)
        self.store.values["_WLED_CONTROLLERS"] = "[]"
        second = json.loads(views.controllers(request).content)
        self.assertEqual(second["count"], 0)
        self.assertIsNone(self.operations.current_operation(self.plugin))

    def test_all_registered_callbacks_have_operation_scope(self):
        for pattern in self.views.PluginViews(self.plugin).urls():
            with self.subTest(name=pattern.name):
                self.assertTrue(hasattr(pattern.callback, "__wrapped__"))

    def test_native_locate_entrypoint_uses_scoped_services_and_real_http_format(self):
        requests = []
        def respond(request, **kwargs):
            requests.append(request)
            count = 200 if request.host == "a.invalid" else 60
            payload = {"seg": [{"id": 0, "start": 0, "stop": count}]} if request.method == "GET" else {"success": True}
            response = Mock()
            response.read.return_value = json.dumps(payload).encode()
            response.status = 200
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            return response
        with patch("locator_facade_test.wled.urlopen", side_effect=respond):
            result = self.plugin.locate_stock_item(1)
        self.assertIsNotNone(result)
        self.assertEqual(result["controller_leds"], {"A": [147, 148]})
        self.assertEqual(len(requests), 5)  # Clear A/B (two each), then light A.
        self.assertEqual(self.plugin._read_plugin_setting.call_count, 3)
        self.assertIsNone(self.operations.current_operation(self.plugin))

    def finder_request(self, payload=None, *, method="POST", csrf=True, content_type="application/json", body=None):
        from django.conf import settings
        from django.middleware.csrf import get_token
        from django.test import RequestFactory
        factory = RequestFactory()
        if method == "GET":
            request = factory.get("/plugin/wled-locator-plus/finder/preview/")
        else:
            request = factory.post(
                "/plugin/wled-locator-plus/finder/preview/",
                data=json.dumps(payload) if body is None else body,
                content_type=content_type,
            )
        request.user = types.SimpleNamespace(is_authenticated=True, is_superuser=True, pk=1)
        if csrf:
            token = get_token(request)
            request.COOKIES[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
            request.META["HTTP_X_CSRFTOKEN"] = token
        return request

    def test_finder_preview_is_authenticated_and_post_only(self):
        views = self.views.PluginViews(self.plugin)
        response = views.finder_preview(self.finder_request(method="GET"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")
        for authenticated, superuser in ((False, False), (True, False)):
            request = self.finder_request({"part_ids": [1, 2]})
            request.user = types.SimpleNamespace(is_authenticated=authenticated, is_superuser=superuser)
            self.assertEqual(views.finder_preview(request).status_code, 403)

    def test_finder_rejects_missing_csrf_token(self):
        views = self.views.PluginViews(self.plugin)
        for callback in (views.finder_search, views.finder_preview, views.finder_locate, views.finder_off):
            request = self.finder_request({"part_ids": [1]}, csrf=False)
            self.assertEqual(callback(request).status_code, 403)

    def test_finder_rejects_invalid_payloads_before_hardware_calls(self):
        views = self.views.PluginViews(self.plugin)
        for payload in ([], {"part_ids": []}, {"part_ids": [True]}, {"part_ids": [1.5]}, {"part_ids": ["1"]}, {"part_ids": [0]}, {"part_ids": list(range(1, 102))}):
            with self.subTest(payload=payload):
                response = views.finder_preview(self.finder_request(payload))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(views.finder_preview(self.finder_request(body="{")).status_code, 400)
        self.assertEqual(views.finder_preview(self.finder_request(body="x" * 65537)).status_code, 413)
        self.assertEqual(views.finder_preview(self.finder_request(body="{}", content_type="text/plain")).status_code, 415)

    def test_finder_reports_django_body_limit_as_oversized_request(self):
        from django.test import override_settings
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=16):
            response = self.views.PluginViews(self.plugin).finder_preview(self.finder_request(body="x" * 1024))
        self.assertEqual(response.status_code, 413)

    def test_finder_search_validates_each_query_and_limit(self):
        view = self.views.PluginViews(self.plugin).finder_search
        for payload in ({}, {"queries": "NE555"}, {"queries": [""]}, {"queries": [False]},
                        {"queries": ["x" * 201]}, {"queries": ["x\x00y"]}, {"queries": ["x"] * 21},
                        {"queries": ["x"], "limit": True}, {"queries": ["x"], "limit": 11}):
            with self.subTest(payload=payload):
                self.assertEqual(view(self.finder_request(payload)).status_code, 400)

    def test_finder_search_dispatches_queries_without_selecting_a_part(self):
        self.plugin.search_parts = Mock(return_value={"results": [{"query": "555", "match_status": "multiple", "matches": []}]})
        response = self.views.PluginViews(self.plugin).finder_search(self.finder_request({"queries": ["555", "10k"], "limit": 3}))
        self.assertEqual(response.status_code, 200)
        self.plugin.search_parts.assert_called_once_with(["555", "10k"], limit=3, cursor=None)
        self.assertNotIn("wled", json.loads(response.content))

    def test_finder_search_forwards_cursor_and_rejects_invalid_page_tokens(self):
        self.plugin.search_parts = Mock(return_value={"results": []})
        response = self.views.PluginViews(self.plugin).finder_search(self.finder_request({"queries": ["555"], "cursor": "signed-token"}))
        self.assertEqual(response.status_code, 200)
        self.plugin.search_parts.assert_called_once_with(["555"], limit=5, cursor="signed-token")
        self.plugin.search_parts = self.facade.WledLocatorPlus.search_parts.__get__(self.plugin)
        for cursor in (True, [], "", "bad-token"):
            with self.subTest(cursor=cursor):
                response = self.views.PluginViews(self.plugin).finder_search(self.finder_request({"queries": ["555"], "cursor": cursor}))
                self.assertEqual(response.status_code, 400)

    def test_finder_preview_keeps_all_selected_parts_and_combines_shared_leds(self):
        response = self.views.PluginViews(self.plugin).finder_preview(self.finder_request({"part_ids": [2, 1, 2]}))
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["part_ids"], [2, 1])
        self.assertEqual(result["controller_leds"], {"A": [147, 148], "B": [27]})
        self.assertTrue(result["can_locate"])

    def test_finder_locate_returns_correctable_conflict_for_missing_parts(self):
        response = self.views.PluginViews(self.plugin).finder_locate(self.finder_request({"part_ids": [1, 999]}))
        self.assertEqual(response.status_code, 409)
        result = json.loads(response.content)
        self.assertEqual(result["code"], "selection_not_locatable")
        self.assertEqual(result["preview"]["missing_part_ids"], [999])

    def test_finder_locate_uses_database_targets_and_returns_combined_response(self):
        requests = []
        def respond(request, **kwargs):
            requests.append(request)
            count = 200 if request.host == "a.invalid" else 60
            payload = {"seg": [{"id": 0, "start": 0, "stop": count}]} if request.method == "GET" else {"success": True}
            response = Mock()
            response.read.return_value = json.dumps(payload).encode()
            response.status = 200
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            return response
        with patch("locator_facade_test.wled.urlopen", side_effect=respond):
            response = self.views.PluginViews(self.plugin).finder_locate(self.finder_request({
                "part_ids": [1, 2], "controller_leds": {"B": [59]},
            }))
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["controller_leds"], {"A": [147, 148], "B": [27]})
        self.assertEqual(result["summary"]["selected_parts"], 2)
        self.assertEqual(len(requests), 6)
        self.assertEqual(json.loads(requests[-1].data), {"seg": [{"id": 0, "i": [27, "FF0000"]}]})

    def test_finder_transport_failure_is_reported_as_bad_gateway(self):
        self.plugin.locate_parts = Mock(side_effect=self.views.WledRequestError("simulated offline controller"))
        response = self.views.PluginViews(self.plugin).finder_locate(self.finder_request({"part_ids": [1]}))
        self.assertEqual(response.status_code, 502)
        self.assertFalse(json.loads(response.content)["success"])

    def test_busy_response_is_retryable_for_new_and_existing_endpoints(self):
        locking = importlib.import_module("locator_facade_test.locking")
        views = self.views.PluginViews(self.plugin)
        self.plugin.locate_parts = Mock(side_effect=locking.LocatorBusyError("Another action is running"))
        self.plugin.off = Mock(side_effect=locking.LocatorBusyError("Another action is running"))
        for response in (
            views.finder_locate(self.finder_request({"part_ids": [1]})),
            views.off(self.finder_request()),
        ):
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response["Retry-After"], "1")
            self.assertEqual(json.loads(response.content)["code"], "locator_busy")

    def test_typed_finder_page_sets_csrf_cookie_and_needs_no_inventory_lookups(self):
        self.plugin.finder = Mock(side_effect=AssertionError("Page rendering must not load inventory"))
        response = self.views.PluginViews(self.plugin).finder_page(self.finder_request(method="GET"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("csrftoken", response.cookies)
        html = response.content.decode()
        self.assertIn("Part finder", html)
        self.assertIn('data-locate disabled', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('/plugin/wled-locator-plus/finder/off/', html)
        self.assertNotIn('<script src=', html)
        self.plugin._read_plugin_setting.assert_not_called()

    def test_finder_recovery_key_is_account_scoped_without_inventory_queries(self):
        import re
        views = self.views.PluginViews(self.plugin)
        keys = []
        for pk in (1, 2, None):
            request = self.finder_request(method="GET")
            request.user.pk = pk
            response = views.finder_page(request)
            config = json.loads(re.search(r'<script id="finder-config" type="application/json">(.*?)</script>', response.content.decode(), re.S)[1])
            keys.append(config["storage_key"])
        self.assertEqual(keys, ["wled-locator-plus.finder.v1.user.1", "wled-locator-plus.finder.v1.user.2", None])
        self.plugin._read_plugin_setting.assert_not_called()

    def test_typed_finder_page_token_works_for_json_preview(self):
        from html.parser import HTMLParser
        class TokenParser(HTMLParser):
            token = None
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "input" and values.get("name") == "csrfmiddlewaretoken":
                    self.token = values["value"]
        views = self.views.PluginViews(self.plugin)
        page = views.finder_page(self.finder_request(method="GET"))
        parser = TokenParser()
        parser.feed(page.content.decode())
        request = self.finder_request({"part_ids": [1, 2]}, csrf=False)
        request.COOKIES["csrftoken"] = page.cookies["csrftoken"].value
        request.META["HTTP_X_CSRFTOKEN"] = parser.token
        self.assertEqual(views.finder_preview(request).status_code, 200)

    def test_typed_finder_page_requires_superuser_and_get(self):
        views = self.views.PluginViews(self.plugin)
        request = self.finder_request(method="GET")
        request.user.is_superuser = False
        self.assertEqual(views.finder_page(request).status_code, 403)
        self.assertEqual(views.finder_page(self.finder_request({})).status_code, 405)

    def test_typed_finder_off_is_a_json_post_with_the_existing_response_shape(self):
        self.plugin.off = Mock(return_value={"success": True})
        response = self.views.PluginViews(self.plugin).finder_off(self.finder_request({}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"success": True, "action": "finder-off", "wled": {"success": True}})
        self.plugin.off.assert_called_once_with()

    def test_finder_frontend_alias_resolves_before_dashboard_wildcard(self):
        from django.urls import path, resolve
        root_urls = module("finder_test_root_urls", urlpatterns=[path("web/", lambda request: None, name="web")])
        with patch.dict(sys.modules, {"InvenTree": module("InvenTree", urls=root_urls)}):
            views = self.views.PluginViews(self.plugin)
            self.plugin._register_web_alias(views)
            self.plugin._register_web_alias(views)
            result = resolve("/web/plugin/wled-locator-plus/finder/", urlconf=root_urls)
            self.assertEqual(result.func.__name__, "finder_page")
            self.assertEqual(sum(pattern.name == "wled-locator-plus-web-finder" for pattern in root_urls.urlpatterns), 1)

    def test_existing_dashboard_links_to_typed_finder(self):
        response = self.views.PluginViews(self.plugin).index(self.finder_request(method="GET"))
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/plugin/wled-locator-plus/finder/">Part finder</a>', response.content.decode())

    def test_dashboard_shell_is_read_only_and_ignores_old_action_links(self):
        views = self.views.PluginViews(self.plugin)
        request = self.finder_request(method="GET")
        request.GET = {"action": "off"}
        self.plugin.off = Mock(side_effect=AssertionError("Page loading must not operate lights"))
        with patch.object(self.views, "build_dashboard", side_effect=AssertionError("Shell must not load inventory")):
            response = views.index(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("csrftoken", response.cookies)
        self.plugin._read_plugin_setting.assert_not_called()
        self.plugin.off.assert_not_called()

    def test_dashboard_json_requires_superuser_csrf_and_post(self):
        views = self.views.PluginViews(self.plugin)
        self.assertEqual(views.dashboard_action(self.finder_request(method="GET")).status_code, 405)
        request = self.finder_request({"command": "off"})
        request.user.is_superuser = False
        self.assertEqual(views.dashboard_action(request).status_code, 403)
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=["testserver"]):
            self.assertEqual(views.dashboard_action(self.finder_request({"command": "off"}, csrf=False)).status_code, 403)
        for body, content_type, expected in (("{", "application/json", 400), ("x" * 65537, "application/json", 413), ("{}", "text/plain", 415)):
            response = views.dashboard_action(self.finder_request(body=body, content_type=content_type))
            self.assertEqual(response.status_code, expected)

    def test_dashboard_get_is_authenticated_and_never_runs_mutations(self):
        views = self.views.PluginViews(self.plugin)
        request = self.finder_request(method="GET")
        with patch.object(self.views, "build_dashboard", return_value={"rows": []}) as build:
            response = views.dashboard_data(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        build.assert_called_once_with(self.plugin, request.GET)
        request.user.is_superuser = False
        self.assertEqual(views.dashboard_data(request).status_code, 403)
        self.assertEqual(views.dashboard_data(self.finder_request({})).status_code, 405)

    def test_dashboard_stale_review_and_unknown_actions_return_clear_errors(self):
        views = self.views.PluginViews(self.plugin)
        conflict = self.views.DashboardConflict("Mappings changed")
        with patch.object(self.views, "save_mapping", side_effect=conflict):
            response = views.dashboard_action(self.finder_request({"command": "save"}))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "mapping_changed")
        self.assertEqual(views.dashboard_action(self.finder_request({"command": "unknown"})).status_code, 400)

    def test_dashboard_locate_off_and_test_use_existing_execution(self):
        views = self.views.PluginViews(self.plugin)
        self.plugin.off = Mock(return_value={"success": True})
        with patch.object(self.views, "locate_dashboard_locations", return_value={"located": 2}) as locate:
            payload = {"command": "locate", "location_ids": [2, 1]}
            self.assertEqual(views.dashboard_action(self.finder_request(payload)).status_code, 200)
            locate.assert_called_once_with(self.plugin, payload)
        self.assertEqual(views.dashboard_action(self.finder_request({"command": "off"})).status_code, 200)
        self.plugin.off.assert_called_once_with()
        self.assertEqual(views.dashboard_action(self.finder_request({"command": "locate", "location_ids": [True]})).status_code, 400)
        self.plugin.clear_all_controllers = Mock(return_value={})
        self.plugin.set_led = Mock(return_value={})
        self.assertEqual(views.dashboard_action(self.finder_request({"command": "test", "controller": "A", "led": 148})).status_code, 200)
        self.plugin.set_led.assert_called_once_with(147, "A")
        self.plugin.set_led.reset_mock()
        self.assertEqual(views.dashboard_action(self.finder_request({"command": "test", "controller": "A", "led": 999})).status_code, 400)
        self.plugin.set_led.assert_not_called()

    def native_callbacks(self):
        views = self.views.PluginViews(self.plugin)
        return [
            (views.off, ()), (views.test_led, (0,)), (views.test_led_controller, ("A", 0)),
            (views.test_leds, ("0,1",)), (views.test_leds_controller, ("A", "0,1")),
            (views.register_location_led, (1, 0)), (views.register_location_indicator, (1, 0, "A")),
            (views.register_location_leds, (1, "0,1")), (views.register_location_indicators, (1, "0,1", "A")),
            (views.clear_location_indicator, (1,)), (views.locate_location, (1,)),
            (views.locate_stock_item, (1,)), (views.locate_part, (1,)), (views.locate_build, (1,)),
            (views.locate_locations, ()),
        ]

    def test_all_native_mutations_reject_get_before_settings_or_hardware(self):
        for callback, args in self.native_callbacks():
            with self.subTest(callback=callback.__name__):
                response = callback(self.finder_request(method="GET"), *args)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Allow"], "POST")
        self.plugin._read_plugin_setting.assert_not_called()

    def test_all_native_mutations_require_csrf_and_superuser(self):
        for callback, args in self.native_callbacks():
            with self.subTest(callback=callback.__name__):
                self.assertEqual(callback(self.finder_request({}, csrf=False), *args).status_code, 403)
                request = self.finder_request({})
                request.user.is_superuser = False
                self.assertEqual(callback(request, *args).status_code, 403)
        self.plugin._read_plugin_setting.assert_not_called()

    def test_native_panel_context_token_authorizes_post_even_without_readable_cookie(self):
        from django.conf import settings
        request = self.finder_request(method="GET")
        panel = self.plugin.get_ui_panels(request, {"target_model": "stocklocation", "target_id": 1})[0]
        token = panel["context"]["csrf_token"]
        self.assertEqual(len(token), 64)
        post = self.finder_request({}, csrf=False)
        post.COOKIES[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
        post.META["HTTP_X_CSRFTOKEN"] = token
        self.plugin.off = Mock(return_value={})
        self.assertEqual(self.views.PluginViews(self.plugin).off(post).status_code, 200)
        self.plugin.off.assert_called_once_with()

    def test_native_save_post_preserves_response_and_other_metadata(self):
        views = self.views.PluginViews(self.plugin)
        with patch.object(self.views, "get_object_or_404", return_value=self.fixture.first):
            response = views.register_location_indicators(self.finder_request({}), 1, "0,1,0", "B")
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["action"], "register-location-led")
        self.assertEqual(result["leds"], [0, 1])
        self.assertEqual(result["controller"], "B")
        self.assertEqual(self.fixture.first.metadata["unrelated"], {"keep": True})

    def test_native_malformed_led_paths_never_save_or_clear(self):
        views = self.views.PluginViews(self.plugin)
        self.plugin.clear_all_controllers = Mock(side_effect=AssertionError("Invalid input must not clear LEDs"))
        for value in ("1.5", "1abc", "1e2", "+1", "-1", "９", "9" * 4097, ",".join(["1"] * 513)):
            with self.subTest(value=value[:30]), patch.object(self.views, "get_object_or_404", return_value=self.fixture.first):
                self.assertEqual(views.register_location_indicators(self.finder_request({}), 1, value, "A").status_code, 400)
                self.assertEqual(views.test_leds_controller(self.finder_request({}), "A", value).status_code, 400)
        self.assertEqual(self.fixture.first.saves, 0)
        self.plugin.clear_all_controllers.assert_not_called()

    def test_native_location_preview_reports_leaf_parent_and_unmapped_readiness(self):
        views = self.views.PluginViews(self.plugin)
        leaf = json.loads(views.preview_location(self.finder_request(method="GET"), 1).content)
        parent = json.loads(views.preview_location(self.finder_request(method="GET"), 6).content)
        unmapped = json.loads(views.preview_location(self.finder_request(method="GET"), 4).content)
        self.assertTrue(leaf["can_locate"])
        self.assertFalse(leaf["has_children"])
        self.assertEqual(leaf["leds"], [147, 148])
        self.assertTrue(parent["has_children"])
        self.assertEqual(parent["controller_leds"], {"A": [147, 148], "B": [27]})
        self.assertFalse(unmapped["can_locate"])
        self.assertTrue(unmapped["reason"])
        self.assertEqual(views.preview_location(self.finder_request({}), 1).status_code, 405)
        request = self.finder_request(method="GET")
        request.user.is_superuser = False
        self.assertEqual(views.preview_location(request, 1).status_code, 403)

    def test_native_stock_item_preview_marks_parent_mapping_read_only(self):
        self.fixture.items[0].location = self.fixture.root
        response = self.views.PluginViews(self.plugin).preview_stock_item(self.finder_request(method="GET"), 1)
        result = json.loads(response.content)
        self.assertTrue(result["can_locate"])
        self.assertFalse(result["mapping_editable"])


if __name__ == "__main__":
    unittest.main()
