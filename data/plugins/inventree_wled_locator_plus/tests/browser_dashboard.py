"""Optional browser checks of exported dashboard HTML with all HTTP mocked."""

import asyncio
import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

ROOT = Path(os.environ.get("WLED_DASHBOARD_FIXTURES", "/tmp/wled-dashboard-fixtures"))
ORIGIN = "http://dashboard.test"
PREFIX = "/plugin/wled-locator-plus/"


class DashboardBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = json.loads((ROOT / "fixtures.json").read_text())
        self.rows = deepcopy(self.fixture["first"]["rows"] + self.fixture["second"]["rows"])
        self.requests, self.errors, self.unexpected = [], [], []
        self.mode = "success"
        self.delay = 0
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 1440, "height": 1000})
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await self.page.route("**/*", self.route)
        await self.page.goto(ORIGIN + PREFIX)
        await self.ready()

    async def asyncTearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.unexpected, [])
        finally:
            await self.browser.close()
            await self.playwright.stop()

    async def ready(self):
        await expect(self.page.locator("[data-table-region]")).to_have_attribute("aria-busy", "false")

    def data(self, params):
        value = lambda key, default="": params.get(key, [default])[0]
        if value("view") == "tools":
            return deepcopy(self.fixture["tools"][value("controller", "A")][min(int(value("led_page", "1")), 2) - 1])
        rows = deepcopy(self.rows)
        if value("q"):
            rows = [row for row in rows if value("q").lower() in (row["path"] + " ".join(row["part_names"])).lower()]
        if value("controller"):
            rows = [row for row in rows if row["controller"] == value("controller")]
        if value("led"):
            rows = [row for row in rows if int(value("led")) in row["leds"]]
        if value("state") not in ("", "all"):
            rows = [row for row in rows if row["state"] == value("state")]
        page = min(int(value("page", "1")), max(1, (len(rows) + 24) // 25))
        data = deepcopy(self.fixture["first"])
        data.update(rows=rows[(page-1)*25:page*25], page=page, pages=max(1, (len(rows)+24)//25), total=len(rows))
        data["summary"]["mapped"] = sum(row["state"] in ("mapped", "shared") for row in self.rows)
        return data

    def review(self, body):
        changes = []
        for index, pk in enumerate(body["location_ids"]):
            row = next(row for row in self.rows if row["id"] == pk)
            leds = [body["leds"][0]+index] if body["mode"] == "sequential" and len(body["location_ids"]) > 1 else body.get("leds", [])
            changes.append({"id": pk, "name": row["name"], "path": row["path"],
                "before": {"controller": row["controller"], "leds": [led-1 for led in row["leds"]]} if row["controller"] else None,
                "after": None if body["mode"] == "remove" else {"controller": body["controller"], "leds": [led-1 for led in leds]}})
        shared_with = []
        if body.get("controller") == "A" and 148 in body.get("leds", []):
            shared_with = [{"id": 2, "path": "Root / Drawer 1", "led": 148}]
        return {"changes": changes, "revision": "a"*64, "shared_leds": body.get("leds", []) if body["mode"] == "same" and len(changes) > 1 else [], "shared_with": shared_with}

    async def route(self, route):
        request = route.request
        url = request.url
        if url == ORIGIN + PREFIX or (url.startswith(ORIGIN + PREFIX + "?") and request.is_navigation_request()):
            await route.fulfill(content_type="text/html", body=(ROOT/"index.html").read_text())
            return
        if url.endswith("favicon.ico"):
            await route.fulfill(status=204)
            return
        if url.startswith(ORIGIN + PREFIX + "dashboard/data/"):
            self.requests.append(("data", parse_qs(urlparse(url).query)))
            if self.mode == "data_error":
                await route.fulfill(status=500, json={"success": False, "error": "Database unavailable"})
            elif self.mode == "expired":
                await route.fulfill(content_type="text/html", body="Sign in")
            else:
                await route.fulfill(json={"success": True, **self.data(parse_qs(urlparse(url).query))})
            return
        if url != ORIGIN + PREFIX + "dashboard/action/":
            self.unexpected.append(url)
            await route.abort()
            return
        body = request.post_data_json
        self.requests.append((body["command"], body))
        if request.method != "POST" or not request.headers.get("x-csrftoken"):
            self.unexpected.append("Missing POST/CSRF token")
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.mode == "busy":
            await route.fulfill(status=503, json={"success": False, "code": "locator_busy"})
        elif self.mode == "offline":
            await route.fulfill(status=502, json={"success": False, "error": "Controller offline"})
        elif body["command"] == "preview":
            await route.fulfill(json={"success": True, "review": self.review(body)})
        elif body["command"] == "save":
            if self.mode == "stale":
                await route.fulfill(status=409, json={"success": False, "code": "mapping_changed", "error": "Mappings changed since your review. Review the changes again before saving."})
                return
            for change in self.review(body)["changes"]:
                row = next(row for row in self.rows if row["id"] == change["id"])
                after = change["after"]
                row.update(controller=after["controller"] if after else None, leds=[led+1 for led in after["leds"]] if after else [], state="mapped" if after else "unmapped", error="")
            if self.mode == "refresh_error": self.mode = "data_error"
            await route.fulfill(json={"success": True, "saved": len(body["location_ids"])})
        else:
            await route.fulfill(json={"success": True, "result": {}, "wled": {}})

    def row(self, name):
        return self.page.locator("[data-rows] tr").filter(has=self.page.get_by_role("link", name=name, exact=True))

    async def edit(self, name="Drawer 1"):
        await self.row(name).get_by_role("button", name=f"Edit mapping for Root / {name}", exact=True).click()
        await expect(self.page.locator("[data-editor]")).to_be_visible()

    async def review_edit(self, controller="B", leds="5"):
        await self.page.locator('[data-editor-form] [name="controller"]').select_option(controller)
        await self.page.locator('[data-editor-form] [name="leds"]').fill(leds)
        await self.page.get_by_role("button", name="Review changes", exact=True).click()
        await expect(self.page.locator("[data-review]")).to_be_visible()

    async def test_initial_layout_sharing_and_no_automatic_hardware(self):
        self.assertEqual([item[0] for item in self.requests], ["data"])
        await expect(self.row("Drawer 1").locator(".badge")).to_have_text("Shared")
        await expect(self.row("Drawer 4").locator(".badge")).to_have_text("Needs correction")
        await expect(self.page.locator("[data-tools]")).to_be_hidden()
        await expect(self.page.locator("[data-rows] tr")).to_have_count(25)
        await self.page.screenshot(path=str(ROOT/"desktop.png"), full_page=True)

    async def test_single_edit_requires_review_and_refreshes_after_save(self):
        await self.edit()
        await expect(self.page.locator("[data-save]")).to_be_hidden()
        await self.review_edit(leds="5,6")
        await expect(self.page.locator("[data-review-rows]")).to_contain_text("B · LEDs 5, 6")
        self.assertNotIn("save", [item[0] for item in self.requests])
        await self.page.get_by_role("button", name="Save mappings", exact=True).click()
        await expect(self.page.locator("[data-editor]")).to_be_hidden()
        await self.ready()
        await expect(self.row("Drawer 1").locator(".mapping")).to_contain_text("LEDs 5, 6")
        self.assertEqual([item[0] for item in self.requests], ["data", "preview", "save", "data"])
        self.assertEqual(self.requests[-2][1]["revision"], "a"*64)

    async def test_editing_after_review_invalidates_save(self):
        await self.edit(); await self.review_edit()
        await self.page.locator('[data-editor-form] [name="leds"]').fill("6")
        await expect(self.page.locator("[data-review]")).to_be_hidden()
        self.assertNotIn("save", [item[0] for item in self.requests])

    async def test_bulk_sequential_review_and_remove(self):
        await self.row("Drawer 1").get_by_role("checkbox").check()
        await self.row("Drawer 2").get_by_role("checkbox").check()
        await self.page.get_by_role("button", name="Edit mapping", exact=True).click()
        await self.review_edit(leds="10")
        await expect(self.page.locator("[data-review-rows] tr")).to_have_count(2)
        await expect(self.page.locator("[data-review-rows]")).to_contain_text("LED 10")
        await expect(self.page.locator("[data-review-rows]")).to_contain_text("LED 11")
        await self.page.locator('[data-editor-form] [name="mode"]').select_option("remove")
        await expect(self.page.locator("[data-review]")).to_be_hidden()
        await self.page.get_by_role("button", name="Review changes", exact=True).click()
        await self.page.get_by_role("button", name="Remove mappings", exact=True).click()
        await self.ready()
        await expect(self.row("Drawer 1").locator(".badge")).to_have_text("Unmapped")
        await expect(self.row("Drawer 2").locator(".badge")).to_have_text("Unmapped")
        self.assertEqual(self.requests[-2][1]["mode"], "remove")

    async def test_sharing_is_explained_and_stale_save_requires_new_review(self):
        await self.edit("Drawer 3"); await self.review_edit(controller="A", leds="148")
        await expect(self.page.locator("[data-sharing-note]")).to_contain_text("sharing is intentional")
        self.mode = "stale"
        await self.page.get_by_role("button", name="Save mappings", exact=True).click()
        await expect(self.page.locator("[data-editor-status]")).to_contain_text("changed since your review")
        await expect(self.page.locator("[data-review]")).to_be_hidden()
        await expect(self.page.locator("[data-editor]")).to_be_visible()
        await expect(self.page.get_by_role("button", name="Review changes", exact=True)).to_be_enabled()

    async def test_pagination_filters_and_selection_reset(self):
        await self.row("Drawer 1").get_by_role("checkbox").check()
        await self.page.get_by_role("button", name="Next", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-page-label]")).to_have_text("Page 2 of 2")
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        await self.page.get_by_label("Search", exact=True).fill("Drawer 1")
        await self.page.get_by_role("button", name="Search", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-page-label]")).to_have_text("Page 1 of 1")
        await self.page.get_by_role("button", name="Reset filters", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-rows] tr")).to_have_count(25)

    async def test_controller_map_selection_test_and_location_navigation(self):
        await self.page.get_by_role("button", name="Controller tools", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-led-grid] button")).to_have_count(128)
        await self.page.get_by_role("button", name="Next LEDs", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-led-grid] button")).to_have_count(72)
        await self.page.get_by_role("button", name="LED 148, 2 assigned locations", exact=True).click()
        await expect(self.page.locator("[data-led-detail]")).to_contain_text("shared")
        self.assertNotIn("test", [item[0] for item in self.requests])
        await self.page.get_by_role("button", name="Test LED", exact=True).click()
        await expect(self.page.locator("[data-status]")).to_contain_text("Testing A LED 148")
        self.assertEqual(self.requests[-1], ("test", {"command": "test", "controller": "A", "led": 148}))
        await self.page.get_by_role("button", name="Show locations", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-locations]")).to_be_visible()
        await expect(self.page.locator("[data-rows] tr")).to_have_count(2)
        await expect(self.page.locator("[data-led-filter]")).to_have_value("148")

    async def test_busy_and_offline_errors_never_report_success(self):
        self.mode = "busy"
        await self.page.get_by_role("button", name="All off", exact=True).click()
        await expect(self.page.locator("[data-status]")).to_contain_text("locator is busy")
        self.mode = "offline"
        await self.row("Drawer 1").get_by_role("button", name="Locate Root / Drawer 1", exact=True).click()
        await expect(self.page.locator("[data-status]")).to_contain_text("Controller offline")

    async def test_hardware_action_disables_overlapping_actions(self):
        self.delay = .5
        await self.page.get_by_role("button", name="All off", exact=True).click()
        await expect(self.page.get_by_role("button", name="All off", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Controller tools", exact=True)).to_be_disabled()
        await expect(self.row("Drawer 1").get_by_role("checkbox")).to_be_disabled()
        await expect(self.page.get_by_role("button", name="All off", exact=True)).to_be_enabled()
        self.assertEqual([item[0] for item in self.requests], ["data", "off"])

    async def test_refresh_failure_after_save_reports_saved_and_allows_retry(self):
        await self.edit(); await self.review_edit()
        self.mode = "refresh_error"
        await self.page.get_by_role("button", name="Save mappings", exact=True).click()
        await expect(self.page.locator("[data-status]")).to_contain_text("Saved 1 location mapping.")
        await expect(self.page.locator("[data-status]")).to_contain_text("Could not refresh")
        self.mode = "success"
        await self.page.get_by_role("button", name="Refresh dashboard", exact=True).click(); await self.ready()
        await expect(self.row("Drawer 1").locator(".mapping")).to_contain_text("LED 5")
        self.assertEqual(sum(item[0] == "save" for item in self.requests), 1)

    async def test_expired_session_and_empty_results(self):
        self.mode = "expired"
        await self.page.get_by_role("button", name="Reset filters", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-status]")).to_contain_text("session may have expired")
        self.mode = "success"
        await self.page.get_by_role("button", name="Refresh dashboard", exact=True).click(); await self.ready()
        await self.page.get_by_label("Search", exact=True).fill("nonexistent")
        await self.page.get_by_role("button", name="Search", exact=True).click(); await self.ready()
        await expect(self.page.locator("[data-rows]")).to_contain_text("No locations match")

    async def test_mobile_layout_and_untrusted_inventory_text(self):
        self.rows[0]["name"] = '<img src=x onerror="window.injected=1">'
        self.rows[0]["path"] = '<script>window.injected=1</script>'
        await self.page.set_viewport_size({"width": 390, "height": 844})
        await self.page.get_by_role("button", name="Reset filters", exact=True).click(); await self.ready()
        self.assertIsNone(await self.page.evaluate("window.injected"))
        self.assertEqual(await self.page.locator("[data-rows] img, [data-rows] script").count(), 0)
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        await self.page.screenshot(path=str(ROOT/"phone.png"))
        await self.edit("Drawer 3"); await self.review_edit()
        self.assertTrue(await self.page.evaluate("document.querySelector('dialog').getBoundingClientRect().right <= innerWidth"))
        await self.page.screenshot(path=str(ROOT/"phone-editor.png"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
