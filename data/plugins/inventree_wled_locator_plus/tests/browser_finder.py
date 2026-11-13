"""Optional Playwright checks against exported HTML and intercepted fake APIs.

Export fixtures with render_finder_fixture.py using the InvenTree container's
Python. Run this file using a development Python with Playwright/Chromium,
setting WLED_FINDER_FIXTURES to the export directory. No live HTTP is allowed.
This file is intentionally separate from unittest discovery: Playwright is not
an addon runtime dependency.
"""

import asyncio
import json
import os
import re
import unittest
from copy import deepcopy
from pathlib import Path

from playwright.async_api import Error as PlaywrightError, async_playwright, expect


ROOT = Path(os.environ.get("WLED_FINDER_FIXTURES", "/tmp/wled-finder-fixtures"))
ORIGIN = "http://finder.test"
PREFIX = "/plugin/wled-locator-plus/finder/"
STORAGE_KEY = "wled-locator-plus.finder.v1.user.1"


class FinderBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = json.loads((ROOT / "fixtures.json").read_text())
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(viewport={"width": 1280, "height": 960})
        self.page = await self.context.new_page()
        self.requests, self.errors, self.unexpected = [], [], []
        self.image_requests = []
        self.image_mode = "success"
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.locate_mode = "success"
        self.locate_delay = 0
        self.preview_error_once = False
        self.delay_first_preview = False
        self.first_preview_requested = asyncio.Event()
        self.search_mode = "success"
        self.more_error_once = False
        self.more_delay = 0
        self.more_requested = asyncio.Event()
        self.preview_mode = "fresh"
        self.user_id = 1
        await self.page.route("**/*", self.route)
        await self.page.goto(ORIGIN + PREFIX)

    async def asyncTearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.unexpected, [])
        finally:
            await self.browser.close()
            await self.playwright.stop()

    def matches(self, query):
        first, second = deepcopy(self.fixture["candidates"])
        if self.image_mode == "all_broken":
            # Use uncached URLs so a previously decoded image cannot hide a
            # missing-file response in this fallback scenario.
            first["part"]["thumbnail_url"] = "/media/finder-fixture/missing.thumbnail.png"
            first["part"]["image_url"] = "/media/finder-fixture/missing.png"
        if query == "empty":
            return []
        if query == "unsafe":
            first["part"]["name"] = '<img src=x onerror="window.injected=1">'
            first["part"]["full_name"] = first["part"]["name"]
            first["part"]["description"] = '<script>window.injected=1</script>'
            first["part"]["thumbnail_url"] = "javascript:window.injected=1"
            first["part"]["image_url"] = "data:image/svg+xml,<svg onload='window.injected=1'/>"
            return [first]
        if query == "unavailable":
            first["availability"] = {"in_stock_quantity": "0", "stock_items": 0, "locations": []}
            second["availability"]["locations"][0]["can_locate"] = False
            return [first, second]
        if query == "overlap":
            return [first, second]
        return [first] if query == "NE555" else [second]

    async def route(self, route):
        url = route.request.url
        if url == ORIGIN + PREFIX:
            html = (ROOT / "index.html").read_text()
            if self.user_id != 1:
                def account_config(match):
                    config = json.loads(match[2])
                    config["storage_key"] = f"wled-locator-plus.finder.v1.user.{self.user_id}"
                    return match[1] + json.dumps(config) + match[3]
                html = re.sub(r'(<script id="finder-config" type="application/json">)(.*?)(</script>)', account_config, html, flags=re.S)
            await route.fulfill(content_type="text/html", body=html)
            return
        if url.endswith("/favicon.ico"):
            await route.fulfill(status=204)
            return
        if url.startswith(ORIGIN + "/media/finder-fixture/"):
            self.image_requests.append(url)
            if self.image_mode == "all_broken" or (self.image_mode == "thumbnail_broken" and url.endswith(".thumbnail.png")):
                await route.fulfill(status=404)
            else:
                await route.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect x="20" y="28" width="88" height="72" rx="6" fill="#364657"/><path d="M10 40h10m-10 16h10m-10 16h10m-10 16h10m88-48h10m-10 16h10m-10 16h10m-10 16h10" stroke="#8b9cad" stroke-width="5"/><text x="64" y="72" font-size="22" fill="white" text-anchor="middle">IC</text></svg>')
            return
        if not url.startswith(ORIGIN + PREFIX):
            self.unexpected.append(url)
            await route.abort()
            return
        endpoint = url.removeprefix(ORIGIN + PREFIX).strip("/")
        request = route.request
        body = request.post_data_json
        self.requests.append((endpoint, body, request.headers))
        if request.method != "POST" or not request.headers.get("x-csrftoken"):
            self.unexpected.append("API request missing POST or CSRF token")
            await route.fulfill(status=400, json={"success": False})
            return
        if endpoint == "search":
            if self.search_mode == "html":
                await route.fulfill(content_type="text/html", body="<h1>Sign in</h1>")
                return
            if self.search_mode == "expired":
                await route.fulfill(status=403, json={"success": False})
                return
            if body.get("cursor"):
                self.more_requested.set()
                if self.more_delay:
                    await asyncio.sleep(self.more_delay)
                if self.more_error_once:
                    self.more_error_once = False
                    await route.fulfill(status=500, json={"success": False, "error": "Could not load more matches."})
                    return
            results = []
            for query in body["queries"]:
                if query in ("many", "many-other"):
                    candidates = [deepcopy(candidate) for candidate in self.fixture["candidates"]]
                    for index in range(101, 109):
                        candidate = deepcopy(self.fixture["candidates"][1])
                        candidate["part"].update(id=index, name=f"Extra {index}", full_name=f"Extra {index}")
                        candidates.append(candidate)
                    cursor = body.get("cursor")
                    if not cursor:
                        matches, next_cursor = candidates[:5], f"page-2:{query}"
                    elif cursor.startswith("page-2:"):
                        # A changed catalog can repeat a candidate; the UI keeps
                        # one card per part within each query group.
                        matches, next_cursor = [candidates[1], *candidates[5:9]], f"page-3:{query}"
                    else:
                        matches, next_cursor = candidates[9:], None
                    results.append({"query": query, "matches": matches, "has_more": bool(next_cursor), "next_cursor": next_cursor})
                else:
                    results.append({"query": query, "matches": self.matches(query), "has_more": False,
                                    "value_match": {"display": "10 kΩ"} if query == "10 kiloohm" else None})
            try:
                await route.fulfill(json={"success": True, "results": results, "summary": {"matched_queries": sum(bool(row["matches"]) for row in results)}})
            except PlaywrightError:
                # A new search deliberately aborts an older pagination request.
                pass
        elif endpoint == "preview":
            if self.preview_error_once:
                self.preview_error_once = False
                await route.fulfill(status=500, json={"success": False, "error": "Could not check locations."})
                return
            payload = deepcopy(self.fixture["previews"][",".join(map(str, body["part_ids"]))])
            if self.preview_mode == "renamed":
                payload["parts"][0]["part"].update(name="Updated timer", full_name="Updated timer")
                payload["parts"][0]["availability"]["in_stock_quantity"] = "77"
            elif self.preview_mode == "unavailable":
                payload["can_locate"] = False
                for part in payload["parts"]:
                    part["can_locate"] = False
                    part["availability"].update(in_stock_quantity="0", stock_items=0, locations=[])
            elif self.preview_mode == "incomplete":
                payload["parts"] = []
            elif self.preview_mode == "wrong_ids":
                payload["part_ids"] = [2]
            elif self.preview_mode == "inconsistent":
                payload["parts"][0]["can_locate"] = False
            elif self.preview_mode == "invalid_boolean":
                payload["can_locate"] = "true"
            if self.delay_first_preview and body["part_ids"] == [1]:
                self.first_preview_requested.set()
                await asyncio.sleep(.7)
            try:
                await route.fulfill(json=payload)
            except PlaywrightError:
                # A superseded preview is deliberately aborted by the page.
                pass
        elif endpoint == "locate":
            if self.locate_delay:
                await asyncio.sleep(self.locate_delay)
            if self.locate_mode == "busy":
                await route.fulfill(status=503, json={"success": False, "code": "locator_busy", "error": "Busy"})
            elif self.locate_mode == "offline":
                await route.fulfill(status=502, json={"success": False, "error": "Controller offline"})
            elif self.locate_mode == "conflict":
                payload = deepcopy(self.fixture["previews"]["1"])
                payload["can_locate"] = False
                payload["parts"][0]["can_locate"] = False
                payload["parts"][0]["availability"] = {"in_stock_quantity": "0", "stock_items": 0, "locations": []}
                await route.fulfill(status=409, json={"success": False, "code": "selection_not_locatable", "preview": payload})
            else:
                payload = deepcopy(self.fixture["previews"][",".join(map(str, body["part_ids"]))])
                payload["wled"] = {"success": True}
                await route.fulfill(json=payload)
        elif endpoint == "off":
            await route.fulfill(json={"success": True, "wled": {"success": True}})
        else:
            self.unexpected.append(endpoint)
            await route.abort()

    async def search(self, text):
        await self.page.get_by_label("Parts to find", exact=True).fill(text)
        await self.page.get_by_role("button", name="Search parts", exact=True).click()
        await expect(self.page.locator("[data-results-region]")).to_have_attribute("aria-busy", "false")

    async def add(self, name):
        await self.page.get_by_role("button", name=f"Add {name} to selection", exact=True).click()

    async def test_search_is_grouped_and_never_selects_or_lights_automatically(self):
        self.assertEqual(self.requests, [])
        await self.search("NE555;10k resistor\nempty")
        self.assertEqual(self.requests[0][1], {"queries": ["NE555", "10k resistor", "empty"]})
        await expect(self.page.locator(".query-group")).to_have_count(3)
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        self.assertEqual([entry[0] for entry in self.requests], ["search"])
        await self.search("unavailable")
        for button in await self.page.locator("[data-part-toggle]").all():
            await expect(button).to_be_disabled()

    async def test_selection_survives_searches_and_locates_then_turns_off(self):
        await self.search("NE555")
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.search("10k resistor")
        await self.add("Resistor")
        await expect(self.page.locator("[data-selected-count]")).to_have_text("2")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.page.get_by_role("button", name="Locate selected", exact=True).click()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("2 parts located together")
        self.assertEqual([body for endpoint, body, _ in self.requests if endpoint == "locate"], [{"part_ids": [1, 2]}])
        await self.page.get_by_role("button", name="Clear list", exact=True).click()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        self.assertNotIn("off", [entry[0] for entry in self.requests])
        await self.page.get_by_role("button", name="All off", exact=True).click()
        await expect(self.page.locator("[data-action-status]")).to_have_text("All locator lights are off.")
        self.assertEqual([body for endpoint, body, _ in self.requests if endpoint == "off"], [{}])

    async def test_superseded_preview_cannot_replace_new_selection(self):
        self.delay_first_preview = True
        await self.search("overlap")
        await self.add("NE555")
        await asyncio.wait_for(self.first_preview_requested.wait(), timeout=5)
        await self.add("Resistor")
        await expect(self.page.locator("[data-preview-status]")).to_contain_text("Ready to locate 2 parts")
        await self.page.wait_for_timeout(800)
        await expect(self.page.locator("[data-preview-status]")).to_contain_text("Ready to locate 2 parts")
        await expect(self.page.locator("[data-selected-count]")).to_have_text("2")

    async def test_duplicate_matches_share_one_selection_and_can_be_removed(self):
        await self.search("NE555;overlap")
        await self.page.locator('[data-part-toggle="1"]').first.click()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")
        for button in await self.page.locator('[data-part-toggle="1"]').all():
            await expect(button).to_have_text("Remove")
        await self.add("Resistor")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.page.locator('[data-selected-parts] [data-remove-part="1"]').click()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")
        await expect(self.page.locator("[data-preview-status]")).to_contain_text("Ready to locate 1 part")
        for button in await self.page.locator('[data-part-toggle="1"]').all():
            await expect(button).to_have_text("Add")

    async def test_hardware_request_disables_overlapping_actions_and_selection_edits(self):
        self.locate_delay = .7
        await self.search("NE555")
        await self.add("NE555")
        locate = self.page.get_by_role("button", name="Locate selected", exact=True)
        await expect(locate).to_be_enabled()
        await locate.click()
        await expect(self.page.get_by_role("button", name="Locating…", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="All off", exact=True)).to_be_disabled()
        await expect(self.page.locator('[data-selected-parts] [data-remove-part="1"]')).to_be_disabled()
        await expect(self.page.get_by_label("Parts to find", exact=True)).to_be_disabled()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("Part located.")
        await expect(self.page.get_by_role("button", name="All off", exact=True)).to_be_enabled()
        self.assertEqual(sum(endpoint == "locate" for endpoint, _, _ in self.requests), 1)

    async def test_partial_mapping_warning_is_visible_without_expanding_locations(self):
        await self.search("NE555")
        await expect(self.page.locator(".match > .location-warning")).to_contain_text("can’t be lit")
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.locator("[data-selected-parts] > article > .location-warning")).to_contain_text("can’t be lit")

    async def test_busy_and_controller_failure_show_retryable_messages(self):
        await self.search("NE555")
        await self.add("NE555")
        locate = self.page.get_by_role("button", name="Locate selected", exact=True)
        await expect(locate).to_be_enabled()
        self.locate_mode = "busy"
        await locate.click()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("Another locate action")
        await expect(locate).to_be_enabled()
        self.locate_mode = "offline"
        await locate.click()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("Some lights may have changed")
        await expect(locate).to_be_enabled()

    async def test_stale_stock_conflict_refreshes_selection_and_disables_locate(self):
        await self.search("NE555")
        await self.add("NE555")
        locate = self.page.get_by_role("button", name="Locate selected", exact=True)
        await expect(locate).to_be_enabled()
        self.locate_mode = "conflict"
        await locate.click()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("can no longer be located")
        await expect(locate).to_be_disabled()
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("In stock: 0")

    async def test_preview_error_can_be_retried_without_rebuilding_selection(self):
        self.preview_error_once = True
        await self.search("NE555")
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Retry location check", exact=True)).to_be_visible()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await self.page.get_by_role("button", name="Retry location check", exact=True).click()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")

    async def test_invalid_input_is_rejected_locally_and_ctrl_enter_searches(self):
        await self.search("\n".join(["timer"] * 21))
        self.assertEqual(self.requests, [])
        await expect(self.page.locator("[data-search-status]")).to_contain_text("between 1 and 20")
        await self.page.get_by_label("Parts to find", exact=True).fill("NE555")
        await self.page.get_by_label("Parts to find", exact=True).press("Control+Enter")
        await expect(self.page.locator(".query-group")).to_have_count(1)

    async def test_untrusted_part_text_is_inert(self):
        await self.search("unsafe")
        await expect(self.page.locator(".match h3")).to_contain_text("<img")
        self.assertEqual(await self.page.locator("img").count(), 0)
        self.assertIsNone(await self.page.evaluate("window.injected"))

    async def test_load_more_appends_deduplicates_and_keeps_selection(self):
        await self.search("many")
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        first_card = await self.page.locator("[data-match]").first.element_handle()
        more = self.page.get_by_role("button", name="Load more matches for many", exact=True)
        await more.click()
        await expect(self.page.locator("[data-match]")).to_have_count(9)
        self.assertTrue(await first_card.evaluate("node => node.isConnected"))
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")
        await expect(self.page.locator(".query-group").get_by_role("button", name="Remove NE555 from selection", exact=True)).to_be_visible()
        self.assertEqual([body for endpoint, body, _ in self.requests if endpoint == "search"][-1], {"queries": ["many"], "cursor": "page-2:many"})
        await more.click()
        await expect(self.page.locator("[data-match]")).to_have_count(10)
        await expect(more).to_be_hidden()
        await expect(self.page.locator(".query-group [role=status]")).to_contain_text("All current matches loaded")
        self.assertNotIn("locate", [entry[0] for entry in self.requests])

    async def test_each_query_has_independent_pagination(self):
        await self.search("many;many-other")
        await self.page.get_by_role("button", name="Load more matches for many", exact=True).click()
        groups = self.page.locator(".query-group")
        await expect(groups.nth(0).locator("[data-match]")).to_have_count(9)
        await expect(groups.nth(1).locator("[data-match]")).to_have_count(5)
        await self.page.get_by_role("button", name="Load more matches for many-other", exact=True).click()
        await expect(groups.nth(1).locator("[data-match]")).to_have_count(9)

    async def test_failed_more_request_can_retry_without_losing_matches(self):
        self.more_error_once = True
        await self.search("many")
        more = self.page.get_by_role("button", name="Load more matches for many", exact=True)
        await more.click()
        await expect(more).to_have_text("Retry load more")
        await expect(self.page.locator("[data-match]")).to_have_count(5)
        await expect(self.page.locator(".query-group [role=status]")).to_contain_text("Could not load more")
        await more.click()
        await expect(self.page.locator("[data-match]")).to_have_count(9)
        pages = [body["cursor"] for endpoint, body, _ in self.requests if endpoint == "search" and "cursor" in body]
        self.assertEqual(pages, ["page-2:many", "page-2:many"])

    async def test_new_search_cannot_receive_late_results_from_old_page(self):
        self.more_delay = .7
        await self.search("many")
        await self.page.get_by_role("button", name="Load more matches for many", exact=True).click()
        await asyncio.wait_for(self.more_requested.wait(), 5)
        await self.search("NE555")
        await expect(self.page.locator(".query-group")).to_have_count(1)
        await expect(self.page.locator("[data-match]")).to_have_count(1)
        await asyncio.sleep(.8)
        await expect(self.page.locator("[data-match]")).to_have_count(1)
        await expect(self.page.locator(".query-heading h3")).to_have_text("NE555")

    async def test_hardware_action_disables_more_and_shows_value_interpretation(self):
        await self.search("10 kiloohm")
        await expect(self.page.get_by_text("Value matching: 10 kΩ", exact=True)).to_be_visible()
        await self.search("many")
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        self.locate_delay = .5
        await self.page.get_by_role("button", name="Locate selected", exact=True).click()
        await expect(self.page.get_by_role("button", name="Load more matches for many", exact=True)).to_be_disabled()
        await expect(self.page.get_by_role("button", name="Load more matches for many", exact=True)).to_be_enabled()

    async def test_matches_load_existing_thumbnails_lazily_without_loading_originals(self):
        await self.search("NE555")
        await expect(self.page.locator(".part-thumbnail.has-image")).to_be_visible()
        image = self.page.locator(".part-thumbnail img")
        await expect(image).to_have_attribute("loading", "lazy")
        await expect(image).to_have_attribute("src", ORIGIN + "/media/finder-fixture/chip.thumbnail.png")
        self.assertEqual(self.image_requests, [ORIGIN + "/media/finder-fixture/chip.thumbnail.png"])
        await expect(self.page.get_by_role("button", name="Add NE555 to selection", exact=True)).to_be_enabled()

    async def test_missing_or_broken_images_keep_matches_usable_and_fall_back_to_original(self):
        await self.search("10k resistor")
        await expect(self.page.locator(".image-placeholder")).to_be_visible()
        self.assertEqual(await self.page.locator(".part-thumbnail img").count(), 0)
        self.assertEqual(self.image_requests, [])
        self.image_mode = "thumbnail_broken"
        await self.search("NE555")
        await expect(self.page.locator(".part-thumbnail.has-image")).to_be_visible()
        await expect(self.page.locator(".part-thumbnail img")).to_have_attribute("src", ORIGIN + "/media/finder-fixture/chip.png")
        self.assertEqual(len(self.image_requests), 2)
        self.image_mode = "all_broken"
        await self.search("NE555")
        await expect(self.page.locator(".part-thumbnail img")).to_have_count(0)
        await expect(self.page.locator(".image-placeholder")).to_be_visible()
        self.assertEqual(len(self.image_requests), 4)
        await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()

    async def test_expired_session_and_non_json_responses_are_not_reported_as_success(self):
        self.search_mode = "expired"
        await self.search("NE555")
        await expect(self.page.locator("[data-search-status]")).to_contain_text("sign in again")
        self.search_mode = "html"
        await self.search("NE555")
        await expect(self.page.locator("[data-search-status]")).to_contain_text("could not be completed")

    async def seed_recovery(self, ids, text="NE555"):
        await self.page.evaluate("([key, state]) => localStorage.setItem(key, JSON.stringify(state))", [STORAGE_KEY, {"version": 1, "part_ids": ids, "search_text": text}])

    async def stored_state(self):
        return await self.page.evaluate("key => JSON.parse(localStorage.getItem(key))", STORAGE_KEY)

    async def test_reload_restores_ids_and_text_without_searching_or_lighting(self):
        await self.search("NE555;10k resistor")
        await self.add("NE555"); await self.add("Resistor")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        self.assertEqual(await self.stored_state(), {"version": 1, "part_ids": [1, 2], "search_text": "NE555;10k resistor"})
        self.requests.clear()
        await self.page.reload()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("2")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.get_by_label("Parts to find", exact=True)).to_have_value("NE555;10k resistor")
        await expect(self.page.locator("[data-selected-parts] h3")).to_have_text(["NE555", "Resistor"])
        self.assertEqual([endpoint for endpoint, _, _ in self.requests], ["preview"])
        self.assertEqual(await self.page.locator("[data-match]").count(), 0)

    async def test_restore_waits_for_check_and_uses_current_names_and_stock(self):
        await self.seed_recovery([1])
        self.preview_mode = "renamed"
        self.delay_first_preview = True
        self.requests.clear()
        await self.page.reload()
        await asyncio.wait_for(self.first_preview_requested.wait(), 5)
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("Part #1")
        await expect(self.page.locator("[data-selected-parts] .stock-summary")).to_have_count(0)
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("Updated timer")
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("In stock: 77")
        self.assertNotIn("Updated timer", json.dumps(await self.stored_state()))
        self.assertEqual([endpoint for endpoint, _, _ in self.requests], ["preview"])

    async def test_unavailable_and_missing_restored_parts_remain_removable(self):
        await self.seed_recovery([1])
        self.preview_mode = "unavailable"
        await self.page.reload()
        await expect(self.page.locator("[data-preview-status]")).to_contain_text("cannot be located")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("In stock: 0")
        self.preview_mode = "fresh"
        await self.seed_recovery([1, 999])
        await self.page.reload()
        await expect(self.page.locator("[data-selected-parts]")).to_contain_text("no longer available")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await self.page.locator('[data-remove-part="999"]').click()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        self.assertEqual((await self.stored_state())["part_ids"], [1])

    async def test_restored_check_failure_can_retry_and_invalid_previews_cannot_enable_locate(self):
        await self.seed_recovery([1])
        self.preview_error_once = True
        await self.page.reload()
        await expect(self.page.get_by_role("button", name="Retry location check", exact=True)).to_be_visible()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await self.page.get_by_role("button", name="Retry location check", exact=True).click()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        for mode in ("incomplete", "wrong_ids", "inconsistent", "invalid_boolean"):
            self.preview_mode = mode
            await self.page.reload()
            await expect(self.page.locator("[data-preview-status]")).to_contain_text("incomplete")
            await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()

    async def test_removals_and_clear_list_are_saved_while_search_text_is_kept(self):
        await self.seed_recovery([1, 2], "overlap")
        await self.page.reload()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.page.locator('[data-remove-part="2"]').click()
        self.assertEqual((await self.stored_state())["part_ids"], [1])
        await self.page.get_by_role("button", name="Clear list", exact=True).click()
        self.assertEqual(await self.stored_state(), {"version": 1, "part_ids": [], "search_text": "overlap"})
        self.requests.clear()
        await self.page.reload()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        await expect(self.page.get_by_label("Parts to find", exact=True)).to_have_value("overlap")
        self.assertEqual(self.requests, [])

    async def test_typing_is_saved_on_immediate_navigation_without_running_search(self):
        await self.page.get_by_label("Parts to find", exact=True).fill("NE555\n100nF capacitor")
        await self.page.reload()
        await expect(self.page.get_by_label("Parts to find", exact=True)).to_have_value("NE555\n100nF capacitor")
        self.assertEqual(self.requests, [])

    async def test_invalid_stored_state_is_discarded_without_api_requests(self):
        invalid = ["{", json.dumps({"version": 7, "part_ids": [1], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": [True], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": ["1"], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": [1.5], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": [-1], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": [9007199254740992], "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": list(range(1, 102)), "search_text": "a"}),
                   json.dumps({"version": 1, "part_ids": [1], "search_text": "a"*8193}), "x"*65537]
        for raw in invalid:
            await self.page.evaluate("([key, value]) => localStorage.setItem(key, value)", [STORAGE_KEY, raw])
            self.requests.clear()
            await self.page.reload()
            await expect(self.page.locator("[data-recovery-status]")).to_contain_text("could not be restored")
            await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
            self.assertEqual(self.requests, [])

    async def test_blocked_storage_does_not_break_search_and_selection(self):
        await self.page.add_init_script("""Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('Blocked', 'SecurityError'); }});""")
        await self.page.reload()
        await expect(self.page.locator("[data-recovery-status]")).to_contain_text("unavailable")
        await self.search("NE555"); await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.locator("[data-recovery-status]")).to_contain_text("could not save")

    async def test_full_storage_cannot_restore_cleared_ids(self):
        await self.search("NE555"); await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.page.evaluate("() => { Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); }; }")
        await self.page.get_by_role("button", name="Clear list", exact=True).click()
        await expect(self.page.locator("[data-recovery-status]")).to_contain_text("could not save")
        self.assertIsNone(await self.stored_state())
        self.requests.clear()
        await self.page.reload()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        self.assertEqual(self.requests, [])

    async def test_recovery_is_scoped_to_account_and_another_tab_can_open_list(self):
        await self.search("NE555"); await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        self.user_id = 2
        self.requests.clear()
        await self.page.reload()
        await expect(self.page.locator("[data-selected-count]")).to_have_text("0")
        await expect(self.page.get_by_label("Parts to find", exact=True)).to_have_value("")
        self.assertEqual(self.requests, [])
        self.user_id = 1
        tab = await self.page.context.new_page()
        tab.on("pageerror", lambda error: self.errors.append(str(error)))
        await tab.route("**/*", self.route)
        await tab.goto(ORIGIN + PREFIX)
        await expect(tab.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(tab.locator("[data-selected-count]")).to_have_text("1")
        await tab.close()

    async def test_idle_tab_does_not_overwrite_a_newer_saved_list_on_reload(self):
        await self.search("NE555"); await self.add("NE555")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        # Simulate another tab saving a newer list in the shared origin storage.
        await self.seed_recovery([2], "10k resistor")
        await self.page.reload()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await expect(self.page.locator("[data-selected-parts] h3")).to_have_text(["Resistor"])
        self.assertEqual((await self.stored_state())["part_ids"], [2])

    async def test_back_forward_restore_rechecks_readiness(self):
        await self.seed_recovery([1])
        await self.page.reload()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        self.preview_mode = "unavailable"
        await self.page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}))")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_disabled()
        await expect(self.page.locator("[data-preview-status]")).to_contain_text("cannot be located")

    async def test_desktop_and_phone_layouts_fit_and_keep_selection_accessible(self):
        await self.search("NE555;10k resistor")
        await self.add("NE555")
        await self.add("Resistor")
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_enabled()
        await self.page.screenshot(path=str(ROOT / "desktop.png"), full_page=True)
        await self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        await expect(self.page.get_by_role("link", name="View selected (2)")).to_be_visible()
        await self.page.get_by_role("link", name="View selected (2)").click()
        await expect(self.page.get_by_role("button", name="Locate selected", exact=True)).to_be_in_viewport()
        await self.page.screenshot(path=str(ROOT / "phone.png"), full_page=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
