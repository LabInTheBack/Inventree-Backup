"""Native ES-module panels in Chromium, with every network request intercepted.

Export contexts with render_panels_fixture.py in the container. Playwright and
Chromium are development tools only; these tests never contact live services.
"""

import asyncio
import json
import os
import re
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(os.environ.get("WLED_PANELS_FIXTURES", "/tmp/wled-panels-fixtures"))
STATIC = Path(__file__).resolve().parents[1] / "static"
ORIGIN = "http://panels.test"
PREFIX = "/plugin/wled-locator-plus/"


class PanelBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = json.loads((ROOT / "fixtures.json").read_text())
        self.requests, self.errors, self.unexpected = [], [], []
        self.mode = "success"
        self.read_error = False
        self.read_delay = 0
        self.write_delay = 0
        self.stock_location_id = 1
        self.stock_available = True
        self.parent_stock = False
        self.mappings = {1: ("A", [147, 148]), 2: ("A", [147]), 3: ("B", [27])}
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 1440, "height": 1000})
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())
        await self.page.route("**/*", self.route)
        await self.open("stock")

    async def asyncTearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.unexpected, [])
        finally:
            await self.browser.close()
            await self.playwright.stop()

    async def open(self, name, ready=True):
        await self.page.goto(f"{ORIGIN}/?panel={name}")
        await self.page.wait_for_function("window.renderNative !== undefined")
        if ready:
            await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")

    async def route(self, route):
        req = route.request
        parsed = urlparse(req.url)
        if parsed.netloc != "panels.test":
            self.unexpected.append(req.url); await route.abort(); return
        if parsed.path == "/":
            name = parse_qs(parsed.query).get("panel", ["stock"])[0]
            data = json.dumps(self.fixture).replace("<", "\\u003c")
            script = '''
              const fixtures = JSON.parse(document.getElementById('fixtures').textContent);
              window.helpers = await import('/static/plugins/wled-locator-plus/panel_common.js');
              window.renderNative = async (name, id='target') => {
                const panel=fixtures.contexts[name];
                const [file, fn]=panel.source.split(':');
                const module=await import('/static/plugins/wled-locator-plus/'+file);
                module[fn](document.getElementById(id), panel);
              };
              await window.renderNative(NAME);
            '''.replace("NAME", json.dumps(name))
            await route.fulfill(content_type="text/html", body=f'<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main id="target"></main><main id="second"></main><script type="application/json" id="fixtures">{data}</script><script type="module">{script}</script></body></html>')
            return
        if parsed.path.startswith("/static/plugins/wled-locator-plus/"):
            name = parsed.path.rsplit("/", 1)[-1]
            await route.fulfill(content_type="text/javascript", body=(STATIC/name).read_text())
            return
        if parsed.path == "/favicon.ico":
            await route.fulfill(status=204); return
        if parsed.path == "/login/":
            await route.fulfill(content_type="text/html", body="Sign in"); return
        if not parsed.path.startswith(PREFIX):
            self.unexpected.append(req.url); await route.abort(); return
        path = unquote(parsed.path.removeprefix(PREFIX))
        self.requests.append((req.method, path, req.headers))
        if req.method == "GET":
            if not path.startswith("preview/"):
                self.unexpected.append(f"Unsafe GET: {path}"); await route.abort(); return
            if self.read_delay: await asyncio.sleep(self.read_delay)
            if self.read_error:
                await route.fulfill(status=500, json={"success": False, "error": "Preview unavailable"}); return
            await route.fulfill(json=self.preview(path)); return
        if req.method != "POST" or len(req.headers.get("x-csrftoken", "")) != 64:
            self.unexpected.append("Missing POST/masked CSRF token")
        if self.write_delay: await asyncio.sleep(self.write_delay)
        if self.mode == "html":
            await route.fulfill(content_type="text/html", body="Sign in"); return
        if self.mode == "invalid_json":
            await route.fulfill(content_type="application/json", body="{"); return
        if self.mode == "missing_success":
            await route.fulfill(json={}); return
        if self.mode == "denied":
            await route.fulfill(status=403, json={"success": False}); return
        if self.mode == "busy":
            await route.fulfill(status=503, json={"success": False, "code": "locator_busy"}); return
        if self.mode == "offline":
            await route.fulfill(status=502, json={"success": False, "error": "Controller offline"}); return
        if self.mode == "network":
            await route.abort(); return
        if self.mode == "old_panel":
            await route.fulfill(status=405, json={"success": False}); return
        if self.mode == "refresh_error": self.read_error = True
        if path.startswith("register/"):
            pk = int(path.split("/")[2])
            if path.endswith("clear/"):
                self.mappings[pk] = None
                data = {"action": "clear-location-indicator", "location": {"id": pk, "name": "Drawer", "path": f"Cabinet / Drawer {pk}"}}
            else:
                controller = re.search(r"controller/([^/]+)/", path)
                label = controller[1] if controller else "A"
                raw = re.search(r"leds?/(.*)/$", path)[1]
                leds = list(dict.fromkeys(map(int, raw.split(","))))
                self.mappings[pk] = (label, leds)
                data = {"action": "register-location-led", "location": {"id": pk, "name": "Drawer", "path": f"Cabinet / Drawer {pk}"}, "controller": label, "led": leds[0], "leds": leds, "indicators": [{"controller": label, "led": led} for led in leds]}
        elif path.startswith("test/"):
            data = {"action": "test", "controller": "A", "leds": [0], "indicators": [{"controller": "A", "led": 0}]}
        elif path.startswith("locate/"):
            kind = path.split("/")[1]
            key = {"part": "part", "build": "build", "stock-item": "stock", "location": "location"}[kind]
            data = {**deepcopy(self.fixture["previews"][key]), "action": "locate-"+kind, "wled": {}}
        else:
            self.unexpected.append(path); await route.abort(); return
        await route.fulfill(json={**data, "success": True})

    def preview(self, path):
        kind, pk = path.split("/")[1:3]
        key = {"stock-item": "stock", "location": "parent" if pk == "6" else "location"}.get(kind, kind)
        result = deepcopy(self.fixture["previews"][key])
        if key in ("stock", "location"):
            ident = self.stock_location_id if key == "stock" else int(pk)
            mapping = self.mappings.get(ident)
            result.update(controller=mapping[0] if mapping else None, leds=mapping[1] if mapping else [],
                indicators=[{"controller": mapping[0], "led": led} for led in mapping[1]] if mapping else [], can_locate=bool(mapping), reason="" if mapping else "No LED mapping")
            if key == "stock":
                result["location"] = {"id": ident, "name": f"Drawer {ident}", "path": f"Cabinet / Drawer {ident}"} if ident else None
                result["mapping_editable"] = bool(ident)
                if not self.stock_available: result.update(can_locate=False, reason="StockItem is not currently in stock")
                if self.parent_stock: result.update(mapping_editable=False)
        if key in ("part", "build"):
            groups = []
            for group in result["locations"]:
                mapping = self.mappings.get(group["location"]["id"])
                if mapping is None:
                    entry = {"item": group["items"][0], "reason": "No LED mapping"} if key == "part" else {"allocation": group["allocations"][0], "reason": "No LED mapping"}
                    result["skipped"].append(entry)
                    continue
                group.update(controller=mapping[0], leds=mapping[1], indicators=[{"controller": mapping[0], "led": led} for led in mapping[1]])
                groups.append(group)
            result["locations"] = groups
            result["indicators"] = [indicator for group in groups for indicator in group["indicators"]]
        return result

    def posts(self):
        return [path for method, path, headers in self.requests if method == "POST"]

    async def test_strict_input_rejects_partial_numbers_and_bounds_before_post(self):
        form = self.page.locator("[data-wled-map-form]")
        for value in ("1.5", "1abc", "1e2", "+1", "-1", "0", "201", "9007199254740993"):
            await form.locator('[name="led"]').fill(value)
            await form.get_by_role("button", name="Test LED", exact=True).click()
            await expect(self.page.locator("[data-wled-result]")).to_contain_text("whole LED numbers")
        self.assertEqual(self.posts(), [])
        await form.locator('[name="controller"]').select_option("B")
        await form.locator('[name="led"]').fill("61")
        await form.get_by_role("button", name="Test LED", exact=True).click()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("1 to 60")
        self.assertEqual(self.posts(), [])

    async def test_valid_boundary_leds_are_deduplicated_and_zero_based_in_post(self):
        await self.page.get_by_label("LED Number(s)", exact=True).fill("1, 200, 1")
        await self.page.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        self.assertEqual(self.posts(), ["register/location/1/controller/A/leds/0,199/"])
        await expect(self.page.locator("[data-wled-preview]")).to_contain_text("LED 1, A / LED 200")
        self.assertEqual(await self.page.evaluate("document.cookie"), "")

    async def test_failed_responses_never_claim_success(self):
        for mode, message in (("html", "unexpected response"), ("invalid_json", "invalid JSON"),
                              ("missing_success", "invalid response"), ("denied", "Access denied"), ("old_panel", "out of date")):
            self.mode = mode
            await self.page.get_by_role("button", name="Locate This Stock Item", exact=True).click()
            await expect(self.page.locator("[data-wled-result]")).to_contain_text(message)
            await expect(self.page.locator("[data-wled-result]")).not_to_contain_text("located:")

    async def test_redirected_response_is_reported_as_expired_session(self):
        # Playwright routes only the first request in a redirect chain. Supply
        # the final browser Response directly so no mock hostname is resolved.
        await self.page.evaluate("""() => {
            window.fetch = async () => {
                const response = new Response('Sign in', {headers: {'content-type': 'text/html'}});
                Object.defineProperty(response, 'redirected', {value: true});
                return response;
            };
        }""")
        await self.page.get_by_role("button", name="Locate This Stock Item", exact=True).click()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("session expired")
        await expect(self.page.locator("[data-wled-result]")).not_to_contain_text("located:")

    async def test_part_and_build_previews_can_be_retried_without_enabling_stale_locate(self):
        for name, label in (("part", "Locate This Part"), ("build", "Locate This Build")):
            self.read_error = True
            await self.open(name)
            await expect(self.page.get_by_role("button", name=label, exact=True)).to_be_disabled()
            self.read_error = False
            await self.page.get_by_role("button", name="Retry preview", exact=True).click()
            await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
            await expect(self.page.get_by_role("button", name=label, exact=True)).to_be_enabled()

    async def test_busy_and_uncertain_hardware_errors_are_distinct(self):
        self.mode = "busy"
        await self.page.get_by_role("button", name="Locate This Stock Item", exact=True).click()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("locator is busy")
        await expect(self.page.locator("[data-wled-result]")).not_to_contain_text("Some lights may have changed")
        for mode in ("offline", "network"):
            self.mode = mode
            await self.page.get_by_role("button", name="Locate This Stock Item", exact=True).click()
            await expect(self.page.locator("[data-wled-result]")).to_contain_text("Some lights may have changed")

    async def test_initial_preview_blocks_actions_until_ready(self):
        self.read_delay = .5
        await self.open("stock", ready=False)
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_enabled()
        self.assertEqual(self.posts(), [])

    async def test_preview_failure_is_retryable_and_preserves_disabled_states(self):
        self.read_error = True
        await self.open("stock")
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        self.read_error = False
        await self.page.get_by_role("button", name="Retry preview", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_enabled()

    async def test_stock_location_id_is_refreshed_after_moving(self):
        self.stock_location_id = 2
        await self.page.get_by_role("button", name="Locate This Stock Item", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await self.page.get_by_label("LED Number(s)", exact=True).fill("12")
        await self.page.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        self.assertEqual(self.posts()[-1], "register/location/2/controller/A/leds/11/")

    async def test_successful_save_with_failed_refresh_is_not_repeated_or_called_failed(self):
        self.mode = "refresh_error"
        await self.page.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("Saved mapping:")
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("action completed")
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        self.read_error = False; self.mode = "success"
        await self.page.get_by_role("button", name="Retry preview", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        self.assertEqual(len(self.posts()), 1)

    async def test_stock_without_location_or_with_parent_and_unavailable_stock(self):
        self.stock_location_id = 0
        await self.open("stock")
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_disabled()
        self.stock_location_id = 1; self.parent_stock = True
        await self.open("stock")
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_enabled()
        self.parent_stock = False; self.stock_available = False
        await self.open("stock")
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_disabled()
        await self.page.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.get_by_role("button", name="Locate This Stock Item", exact=True)).to_be_disabled()

    async def test_part_and_build_save_clear_reassign_and_locate(self):
        for name in ("part", "build"):
            self.mappings[1] = ("A", [147, 148])
            await self.open(name)
            form = self.page.locator('[data-location-id="1"] [data-wled-map-form]')
            await form.locator('[name="led"]').fill("1,2")
            await form.get_by_role("button", name="Save Mapping", exact=True).click()
            await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
            await expect(self.page.locator('[data-location-id="1"]').locator("xpath=ancestor::tr").locator("[data-led-cell]")).to_contain_text("LED 1")
            await form.get_by_role("button", name="Clear Mapping", exact=True).click()
            await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
            await expect(form).to_be_visible()
            await form.locator('[name="led"]').fill("5")
            await form.get_by_role("button", name="Save Mapping", exact=True).click()
            await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
            await self.page.get_by_role("button", name="Locate This Part" if name == "part" else "Locate This Build", exact=True).click()
            await expect(self.page.locator("[data-wled-result]")).to_contain_text("located in")

    async def test_location_refreshes_after_clear_and_save_and_parent_has_no_form(self):
        await self.open("location")
        await self.page.get_by_role("button", name="Clear Mapping", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.get_by_role("button", name="Locate This Location", exact=True)).to_be_disabled()
        await self.page.get_by_label("LED Number(s)", exact=True).fill("10")
        await self.page.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.locator("[data-current-mapping]")).to_contain_text("LED 10")
        await expect(self.page.get_by_role("button", name="Locate This Location", exact=True)).to_be_enabled()
        await self.open("parent")
        await expect(self.page.locator("[data-wled-map-form]")).to_have_count(0)
        await self.page.get_by_role("button", name="Locate This Location", exact=True).click()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("located")

    async def test_ui_lock_covers_all_forms_and_panels_until_followup_read_finishes(self):
        await self.open("part")
        await self.page.evaluate("window.renderNative('stock', 'second')")
        await expect(self.page.locator("#second")).to_have_attribute("aria-busy", "false")
        self.write_delay = .4; self.read_delay = .4
        form = self.page.locator('#target [data-location-id="1"] [data-wled-map-form]')
        await form.get_by_role("button", name="Save Mapping", exact=True).click()
        await expect(self.page.locator('#second [data-wled-locate]')).to_be_disabled()
        await expect(self.page.locator('#target [data-wled-locate]')).to_be_disabled()
        await expect(self.page.locator('#target [data-location-id="2"] [name="led"]')).to_be_disabled()
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")
        await expect(self.page.locator('#second [data-wled-locate]')).to_be_enabled()
        self.assertEqual(len(self.posts()), 1)

    async def test_single_and_missing_controller_configuration(self):
        context = self.fixture["contexts"]["stock"]["context"]
        context["controllers"] = context["controllers"][:1]
        await self.open("stock")
        await expect(self.page.get_by_role("combobox", name="Controller", exact=True)).to_have_value("A")
        await self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        await self.page.screenshot(path=str(ROOT / "stock-phone.png"), full_page=True)
        context["controllers"] = []
        self.mappings[1] = None
        await self.open("stock")
        await expect(self.page.get_by_role("button", name="Save Mapping", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Test LED", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("combobox", name="Controller", exact=True)).to_contain_text("No controllers configured")

    async def test_unsafe_inventory_and_controller_text_is_inert(self):
        self.fixture["contexts"]["location"]["context"]["current_controller"] = '<img src=x onerror="window.injected=1">'
        self.fixture["previews"]["location"]["location"]["path"] = '<script>window.injected=1</script>'
        await self.open("location")
        self.assertIsNone(await self.page.evaluate("window.injected"))
        self.assertEqual(await self.page.locator("#target img, #target script").count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
