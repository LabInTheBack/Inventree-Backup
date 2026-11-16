"""Assembly panel browser checks. Every HTTP request is intercepted."""

import asyncio
import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(os.environ.get("WLED_BOM_FIXTURES", "/tmp/wled-bom-fixtures"))
STATIC = Path(os.environ.get("WLED_BOM_STATIC_DIR", str(Path(__file__).resolve().parents[1] / "static")))
ORIGIN = "http://bom.test"


class BomBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = json.loads((ROOT / "fixtures.json").read_text())
        self.requests, self.errors, self.unexpected, self.images = [], [], [], []
        self.mode, self.preview_error, self.delay = "success", False, 0
        self.image_mode = "missing"
        self.user_id = 1
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 1400, "height": 1000})
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await self.page.route("**/*", self.route)
        await self.page.goto(ORIGIN)
        await self.ready()

    async def asyncTearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.unexpected, [])
        finally:
            await self.browser.close()
            await self.playwright.stop()

    async def ready(self):
        await expect(self.page.locator("#target")).to_have_attribute("aria-busy", "false")

    async def route(self, route):
        request = route.request
        path = urlparse(request.url).path
        if urlparse(request.url).netloc != "bom.test":
            self.unexpected.append(request.url); await route.abort(); return
        if path == "/":
            build_mode = "build=1" in urlparse(request.url).query
            values = deepcopy(self.fixture["build_context" if build_mode else "context"])
            values["picking_storage_key"] = values["picking_storage_key"].replace("user.1.", f"user.{self.user_id}.")
            context = json.dumps(values).replace("<", "\\u003c")
            await route.fulfill(content_type="text/html", body=f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>
                <main id="target"></main><aside id="other"><button>Other panel</button></aside>
                <script type="module">
                import {{renderBomPanel}} from '/static/bom_panel.js';
                import {{registerPanel}} from '/static/panel_common.js';
                registerPanel(document.getElementById('other'), {{}});
                renderBomPanel(document.getElementById('target'), {{context:{context}}});
                </script></body></html>'''); return
        if path.startswith("/static/"):
            await route.fulfill(content_type="text/javascript", body=(STATIC / path.rsplit("/", 1)[-1]).read_text()); return
        if path.startswith("/media/"):
            self.images.append(path)
            if self.image_mode == "success" or self.image_mode == "original" and not path.endswith("thumbnail.png"):
                await route.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><rect width="96" height="96" fill="#ddd"/><rect x="24" y="24" width="48" height="48" fill="#345"/></svg>')
            else:
                await route.fulfill(status=404)
            return
        if path == "/favicon.ico":
            await route.fulfill(status=204); return
        if request.method != "POST" or request.headers.get("x-csrftoken") != "a" * 64:
            self.unexpected.append(f"Unprotected request: {request.method} {path}")
        payload = request.post_data_json
        self.requests.append((path, payload))
        is_build = "/components/build/" in path
        current_context = self.fixture["build_context"] if is_build else self.fixture["context"]
        preview_action = "build-component-preview" if is_build else "component-preview"
        locate_action = "build-component-locate" if is_build else "component-locate"
        if path == current_context["preview_url"]:
            if self.preview_error:
                await route.fulfill(status=500, json={"success": False, "action": preview_action, "error": "Preview unavailable"}); return
            if is_build:
                plan = deepcopy(self.fixture["build_previews"][str(int(payload["include_subbuilds"]))])
            else:
                key = f'{payload["quantity"]}-{int(payload["expand"])}-{int(payload["include_optional"])}'
                plan = deepcopy(self.fixture["previews"][key])
            if self.mode == "unsafe":
                plan["components"][0]["part"]["name"] = '<img src=x onerror="window.injected=1">'
                plan["components"][0]["part"]["full_name"] = '<script>window.injected=1</script>'
                plan["components"][0]["part"]["image_url"] = "javascript:window.injected=1"
                plan["components"][0]["part"]["thumbnail_url"] = "data:image/svg+xml,<svg onload='window.injected=1'/>"
            if self.mode == "invalid_preview": plan["components"] = None
            if self.mode == "unavailable":
                plan["can_locate"] = False
                plan["summary"]["locatable_components"] = 0
                for row in plan["components"]: row["can_locate"] = False
            if self.mode == "inconsistent":
                for row in plan["components"]: row["can_locate"] = False
            if self.mode == "empty":
                plan["can_locate"] = False
                plan["components"] = []
                plan["summary"].update(components=0, locatable_components=0, short_components=0, unique_locations=0)
                plan["picking"].update(locations=[], shortages=[])
            if self.mode == "closed" and is_build:
                plan["build"]["active"] = False
                plan["can_locate"] = False
                plan["components"] = []
                plan["summary"].update(components=0, locatable_components=0, short_components=0, unique_locations=0, builds=0)
                plan["picking"].update(locations=[], shortages=[])
            if self.mode == "split":
                group = deepcopy(plan["picking"]["locations"][0])
                group["location"] = {"id": 900, "path": "Other drawer", "name": "Other drawer"}
                group["items"][0]["quantity"] = "0.5"
                plan["picking"]["locations"][0]["items"][0]["quantity"] = "0.5"
                plan["picking"]["locations"].append(group)
            if self.mode == "changed":
                plan["components"][0]["picking_fingerprint"] = "b" * 64
                plan["picking"]["revision"] = "c" * 64
            await route.fulfill(json={"success": True, "action": preview_action, **plan}); return
        if self.delay: await asyncio.sleep(self.delay)
        if self.mode == "busy":
            await route.fulfill(status=503, json={"success": False, "action": locate_action, "code": "locator_busy"}); return
        if self.mode == "html":
            await route.fulfill(content_type="text/html", body="Sign in"); return
        if self.mode == "unverified":
            await route.fulfill(json={"success": True, "action": locate_action}); return
        if self.mode == "picking_conflict":
            self.mode = "changed"
            await route.fulfill(status=409, json={"success": False, "action": locate_action, "code": "picking_changed", "error": "Component requirements changed. Review the refreshed picking checklist before highlighting"}); return
        if self.mode == "refresh_error": self.preview_error = True
        if path == self.fixture["context"]["off_url"]:
            await route.fulfill(json={"success": True, "action": "finder-off"}); return
        if path != current_context["locate_url"]:
            self.unexpected.append(path); await route.abort(); return
        await route.fulfill(json={"success": True, "action": locate_action, "highlighted_components": 1, "highlighted_locations": 1})

    async def test_initial_preview_is_read_only_and_partial_highlighting_is_enabled(self):
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.requests[0][0].endswith("preview/"))
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("1 of 2")
        await expect(self.page.locator("#target")).to_contain_text("No on-hand stock")
        await expect(self.page.locator("#target")).to_contain_text("optional BOM lines excluded")

    async def test_expand_and_quantity_change_only_refresh_preview(self):
        await self.page.locator("[data-bom-expand]").check(); await self.ready()
        await self.page.locator("[data-bom-quantity]").fill("3")
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        await self.page.locator("[data-bom-quantity]").press("Tab"); await self.ready()
        self.assertTrue(all(path.endswith("preview/") for path, _ in self.requests))
        self.assertEqual(self.requests[-1][1], {"quantity": 3, "expand": True, "include_optional": False})
        await expect(self.page.locator("#target")).to_contain_text("21")

    async def test_combined_highlight_individual_highlight_and_off(self):
        await self.page.locator("[data-bom-locate]").click(); await self.ready()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("Highlighted 1")
        writes = [payload for path, payload in self.requests if path.endswith("locate/")]
        self.assertEqual(len(writes), 1)
        self.assertNotIn("controller_leds", writes[0])
        await self.page.get_by_text("Component details and stock", exact=True).click()
        await self.page.locator("[data-bom-part] button:enabled").first.click(); await self.ready()
        writes = [payload for path, payload in self.requests if path.endswith("locate/")]
        self.assertIn("component_id", writes[-1])
        await self.page.get_by_role("button", name="All off", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-wled-result]")).to_have_text("All locator lights are off.")

    async def test_invalid_quantity_cannot_highlight(self):
        await self.page.locator("[data-bom-quantity]").fill("0")
        await self.page.locator("[data-bom-quantity]").press("Tab"); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("1 to 10000")
        self.assertEqual(len(self.requests), 1)

    async def test_preview_failure_and_retry(self):
        self.preview_error = True
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        self.preview_error = False
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()

    async def test_controls_across_panels_lock_through_write_and_refresh(self):
        self.delay = 0.5
        await self.page.locator("[data-bom-locate]").click()
        await expect(self.page.locator("[data-bom-quantity]")).to_be_disabled()
        await expect(self.page.locator("#other button")).to_be_disabled()
        await self.ready()
        await expect(self.page.locator("#other button")).to_be_enabled()

    async def test_busy_and_unexpected_response_show_errors(self):
        for mode, message in (("busy", "locator is busy"), ("html", "Some lights may have changed"), ("unverified", "could not be verified")):
            self.mode = mode
            await self.page.locator("[data-bom-locate]").click(); await self.ready()
            await expect(self.page.locator("[data-wled-result]")).to_contain_text(message)

    async def test_failed_refresh_after_write_disables_locate(self):
        self.mode = "refresh_error"
        await self.page.locator("[data-bom-locate]").click(); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("Highlighted")
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("Preview unavailable")

    async def test_invalid_preview_and_no_available_stock_disable_locate(self):
        for mode in ("invalid_preview", "unavailable", "inconsistent", "empty"):
            self.mode = mode
            await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
            await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()

    async def test_optional_components_are_explicit_and_do_not_change_lights(self):
        await self.page.get_by_label("Include optional components").check(); await self.ready()
        self.assertTrue(self.requests[-1][1]["include_optional"])
        self.assertTrue(all(path.endswith("preview/") for path, _ in self.requests))
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("1 of 3")

    async def test_safe_text_images_and_mobile_layout(self):
        await self.page.get_by_text("Component details and stock", exact=True).click()
        self.mode = "unsafe"
        await self.page.set_viewport_size({"width": 390, "height": 844})
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        self.assertIsNone(await self.page.evaluate("window.injected"))
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.assertTrue(self.images)
        await self.page.screenshot(path="/tmp/wled-bom-mobile.png", full_page=True)

    async def test_build_panel_uses_saved_quantity_and_shows_existing_allocations(self):
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        await expect(self.page.locator("[data-bom-quantity]")).to_have_count(0)
        await expect(self.page.locator("[data-bom-expand]")).to_have_count(0)
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("build quantity 3, completed 0")
        await expect(self.page.locator("#target")).to_contain_text("Allocated: 3; usable allocated: 3; consumed: 2")
        self.assertEqual(self.requests[-1][1], {"include_subbuilds": False})
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()

    async def test_build_subbuild_toggle_uses_real_child_requirements_without_operating_lights(self):
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        await self.page.locator("[data-bom-subbuilds]").check(); await self.ready()
        self.assertEqual(self.requests[-1][1], {"include_subbuilds": True})
        self.assertTrue(all(path.endswith("preview/") for path, _ in self.requests))
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("2 active build order(s)")
        await expect(self.page.locator("#target")).to_contain_text("BO-PCBA")
        await expect(self.page.locator("#target")).to_contain_text("Planned outputs are not counted as stock")

    async def test_build_combined_individual_and_off_use_protected_build_routes(self):
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        await self.page.locator("[data-bom-locate]").click(); await self.ready()
        writes = [(path, payload) for path, payload in self.requests if path.endswith("locate/")]
        self.assertEqual(writes[-1][0], self.fixture["build_context"]["locate_url"])
        self.assertFalse(writes[-1][1]["include_subbuilds"])
        self.assertIn("picking_revision", writes[-1][1])
        await self.page.get_by_text("Component details and stock", exact=True).click()
        await self.page.locator("[data-bom-part] button:enabled").first.click(); await self.ready()
        writes = [payload for path, payload in self.requests if path.endswith("locate/")]
        self.assertIn("component_id", writes[-1])
        await self.page.get_by_role("button", name="All off", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("All locator lights are off")

    async def test_build_preview_failure_and_closed_build_disable_highlighting(self):
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        self.preview_error = True
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        self.preview_error = False
        self.mode = "closed"
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        await expect(self.page.locator("[data-wled-preview-status]")).to_contain_text("complete or cancelled")

    async def test_picking_marks_are_local_and_all_done_disables_highlighting(self):
        requests = len(self.requests)
        await self.page.locator("[data-pick-collected]").first.check()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("1 of 2")
        await expect(self.page.locator("[data-bom-locate]")).to_be_disabled()
        for check in await self.page.locator("[data-pick-collected]").all():
            if not await check.is_checked(): await check.check()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("2 of 2")
        self.assertEqual(len(self.requests), requests)
        await self.page.get_by_role("button", name="Reset picking progress").click()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()
        self.assertEqual(len(self.requests), requests)

    async def test_picking_progress_and_options_survive_reload_with_fresh_preview(self):
        await self.page.locator("[data-bom-quantity]").fill("3")
        await self.page.locator("[data-bom-quantity]").press("Tab"); await self.ready()
        await self.page.locator("[data-pick-collected]").first.check()
        await self.page.reload(); await self.ready()
        await expect(self.page.locator("[data-bom-quantity]")).to_have_value("3")
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("1 of 2")
        self.assertTrue(all(path.endswith("preview/") for path, _ in self.requests))
        record = await self.page.evaluate("key => JSON.parse(localStorage.getItem(key))", self.fixture["context"]["picking_storage_key"])
        self.assertEqual(set(record), {"version", "options", "collected"})
        self.assertEqual(set(record["collected"][0]), {"id", "fingerprint"})

    async def test_picking_scope_changes_reset_marks_and_accounts_are_isolated(self):
        await self.page.locator("[data-pick-collected]").first.check()
        self.user_id = 2
        await self.page.reload(); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")
        self.user_id = 1
        await self.page.reload(); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("1 of 2")
        await self.page.locator("[data-bom-expand]").check(); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")

    async def test_split_locations_show_pick_quantities_and_synchronize_component_marks(self):
        self.mode = "split"
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        chip = self.fixture["previews"]["1-0-0"]["picking"]["locations"][0]["items"][0]["part_id"]
        checks = self.page.locator(f'[data-pick-collected="{chip}"]')
        await expect(checks).to_have_count(2)
        await expect(self.page.locator("[data-picking-checklist]")).to_contain_text("Collect here: 0.5")
        await checks.first.check()
        await expect(checks.first).to_be_checked()
        await expect(checks.last).to_be_checked()
        await checks.last.uncheck()
        await expect(checks.first).not_to_be_checked()

    async def test_changed_requirements_reset_only_affected_marks(self):
        await self.page.locator("[data-pick-collected]").first.check()
        self.mode = "changed"
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")
        await expect(self.page.locator("[data-picking-checklist]")).to_contain_text("requirements changed")
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()

    async def test_highlighting_remaining_sends_fresh_revision_and_excludes_collected_ids(self):
        await self.page.goto(ORIGIN + "?build=1"); await self.ready()
        missing = self.page.locator("[data-picking-shortages] [data-pick-collected]").first
        collected_id = int(await missing.get_attribute("data-pick-collected"))
        await missing.check()
        await self.page.locator("[data-bom-locate]").click(); await self.ready()
        payload = next(payload for path, payload in reversed(self.requests) if path.endswith("locate/"))
        self.assertNotIn(collected_id, payload["remaining_component_ids"])
        self.assertEqual(payload["picking_revision"], self.fixture["build_previews"]["0"]["picking"]["revision"])
        self.mode = "picking_conflict"
        await self.page.locator("[data-bom-locate]").click(); await self.ready()
        await expect(self.page.locator("[data-wled-result]")).to_contain_text("requirements changed")

    async def test_corrupt_and_unavailable_storage_leave_checklist_usable(self):
        key = self.fixture["context"]["picking_storage_key"]
        await self.page.evaluate("key => localStorage.setItem(key, '{invalid')", key)
        await self.page.reload(); await self.ready()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("0 of 2")
        await self.page.add_init_script("Storage.prototype.getItem = Storage.prototype.setItem = function(){throw new Error('Storage blocked')}")
        await self.page.reload(); await self.ready()
        await expect(self.page.locator("[data-picking-checklist]")).to_contain_text("Progress cannot be saved")
        await self.page.locator("[data-pick-collected]").first.check()
        await expect(self.page.locator("[data-picking-progress]")).to_contain_text("1 of 2")

    async def test_picking_images_stay_right_on_phone_and_desktop_without_changing_progress(self):
        self.image_mode = "success"
        for page_url in (ORIGIN, ORIGIN + "?build=1"):
            await self.page.goto(page_url); await self.ready()
            for width in (1400, 390):
                await self.page.set_viewport_size({"width": width, "height": 1000})
                image = self.page.locator("[data-pick-image] img").first
                await expect(image).to_have_js_property("naturalWidth", 96)
                image_box = await image.bounding_box()
                row = self.page.locator("[data-pick-part]").filter(has=self.page.locator("[data-pick-image] img")).first
                content_box = await row.locator(":scope > div").bounding_box()
                self.assertGreaterEqual(image_box["x"], content_box["x"] + content_box["width"])
                self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            requests = len(self.requests)
            await self.page.locator("[data-pick-collected]").first.check()
            await expect(self.page.locator("[data-picking-progress]")).to_contain_text("1 of 2")
            await expect(self.page.locator("[data-pick-image] img").first).to_have_js_property("naturalWidth", 96)
            self.assertEqual(len(self.requests), requests)
        await self.page.screenshot(path="/tmp/wled-picking-images-mobile.png", full_page=True)

    async def test_picking_images_fall_back_to_original_and_missing_placeholder(self):
        self.image_mode = "original"
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        image = self.page.locator("[data-pick-image] img").first
        await expect(image).to_have_js_property("naturalWidth", 96)
        await expect(image).to_have_attribute("src", ORIGIN + "/media/parts/chip.png")
        await expect(self.page.locator("[data-picking-shortages] [data-pick-image]").first).to_have_text("No image")
        self.image_mode = "missing"
        # Use fresh URLs so Chromium's decoded image cache cannot retain the
        # successful original from the first half of this scenario.
        self.fixture["previews"]["1-0-0"]["components"][0]["part"].update(
            image_url="/media/parts/missing.png", thumbnail_url="/media/parts/missing.thumbnail.png")
        await self.page.get_by_role("button", name="Refresh component preview").click(); await self.ready()
        await expect(self.page.locator("[data-pick-image]").first).to_have_text("No image")
        await expect(self.page.locator("[data-bom-locate]")).to_be_enabled()


if __name__ == "__main__":
    unittest.main()
