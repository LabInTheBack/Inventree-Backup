"""Exercise the real Plugin Configuration module with intercepted services."""

import os
import unittest
from pathlib import Path

from playwright.async_api import async_playwright, expect


STATIC = Path(os.environ.get("WLED_SPEECH_STATIC_DIR", str(Path(__file__).resolve().parents[1] / "static")))
ORIGIN = "https://speech-settings.test"
PREFIX = "/plugin/wled-locator-plus/"


class SpeechSettingsBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.speech = {"url": "http://speech.invalid:8000", "model": "Systran/faster-whisper-small"}
        self.posts, self.errors, self.unexpected = [], [], []
        self.read_error = self.write_error = False
        self.interpreter = {"url": "http://ollama.invalid:11434", "model": "qwen3.5:2b-q4_K_M"}
        self.parser_read_error = self.parser_write_error = False
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(viewport={"width": 1100, "height": 1000})
        await self.context.add_cookies([{"name": "csrftoken", "value": "a" * 32, "url": ORIGIN}])
        self.page = await self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await self.page.route("**/*", self.route)
        await self.page.goto(ORIGIN)
        await expect(self.page.locator("[data-speech-form]")).to_be_visible()

    async def asyncTearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.unexpected, [])
        finally:
            await self.browser.close()
            await self.playwright.stop()

    async def route(self, route):
        request = route.request
        path = request.url.removeprefix(ORIGIN)
        if path == "/":
            return await route.fulfill(content_type="text/html", body='''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><main id="target"></main><script type="module">import {renderPluginSettings} from '/admin_settings.js'; renderPluginSettings(document.getElementById('target'), {});</script></body></html>''')
        if path == "/admin_settings.js":
            return await route.fulfill(content_type="text/javascript", body=(STATIC / "admin_settings.js").read_text())
        if path == "/favicon.ico":
            return await route.fulfill(status=204)
        if request.method == "POST":
            self.posts.append((path, request.post_data_json, request.headers))
        if path == PREFIX + "controllers/":
            return await route.fulfill(json={"success": True, "controllers": [{"label": "Cabinet", "address": "http://wled.invalid", "max_leds": 200}], "options": {}, "count": 1})
        if path == PREFIX + "controllers/mappings/":
            return await route.fulfill(json={"success": True, "mappings": {}})
        if path == PREFIX + "speech/settings/":
            if request.method == "GET" and self.read_error:
                return await route.fulfill(status=500, json={"success": False})
            if request.method == "POST":
                if self.write_error:
                    return await route.fulfill(status=400, json={"success": False, "error": "Invalid speech URL"})
                self.speech = request.post_data_json
            return await route.fulfill(json={"success": True, "speech": self.speech})
        if path == PREFIX + "interpreter/settings/":
            if request.method == "GET" and self.parser_read_error:
                return await route.fulfill(status=500, json={"success": False})
            if request.method == "POST":
                if self.parser_write_error:
                    return await route.fulfill(status=400, json={"success": False, "error": "Invalid parser URL"})
                self.interpreter = request.post_data_json
            return await route.fulfill(json={"success": True, "interpreter": self.interpreter})
        self.unexpected.append(request.url)
        await route.abort()

    async def test_save_and_disable_voice_only_write_speech_setting(self):
        form = self.page.locator("[data-speech-form]")
        await expect(form.locator('[name="url"]')).to_have_value(self.speech["url"])
        self.assertEqual(self.posts, [])
        await form.locator('[name="url"]').fill("http://another.invalid:18000")
        await expect(form.locator('[name="language"]')).to_have_count(0)
        await form.get_by_role("button", name="Save Voice Settings").click()
        await expect(form.locator("[data-speech-status]")).to_contain_text("saved")
        self.assertEqual(self.posts[0][0], PREFIX + "speech/settings/")
        self.assertEqual(self.posts[0][1], {"url": "http://another.invalid:18000", "model": "Systran/faster-whisper-small"})
        self.assertEqual(self.posts[0][2]["x-csrftoken"], "a" * 32)
        await form.locator('[name="url"]').fill("")
        await form.get_by_role("button", name="Save Voice Settings").click()
        await expect(form.get_by_role("button", name="Save Voice Settings")).to_be_enabled()
        self.assertEqual(self.posts[-1][1]["url"], "")
        await expect(self.page.locator("[data-controller-form]")).to_have_count(1)

    async def test_save_error_preserves_edits_and_controller_controls(self):
        self.write_error = True
        form = self.page.locator("[data-speech-form]")
        await form.locator('[name="url"]').fill("http://retry.invalid")
        await form.get_by_role("button", name="Save Voice Settings").click()
        await expect(form.locator("[data-speech-status]")).to_contain_text("Invalid speech URL")
        await expect(form.locator('[name="url"]')).to_have_value("http://retry.invalid")
        await expect(self.page.get_by_role("button", name="Sync", exact=True).first).to_be_enabled()

    async def test_speech_read_failure_does_not_break_wled_configuration(self):
        self.read_error = True
        await self.page.reload()
        await expect(self.page.get_by_text("Speech settings are unavailable.", exact=False)).to_be_visible()
        await expect(self.page.locator("[data-controller-form]")).to_have_count(1)
        await expect(self.page.get_by_role("button", name="Sync", exact=True).first).to_be_enabled()

    async def test_phone_settings_fit_the_viewport(self):
        await self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        self.assertEqual(self.posts, [])

    async def test_parser_save_and_disable_leave_speech_and_controller_settings_alone(self):
        form = self.page.locator("[data-interpreter-form]")
        await expect(form.locator('[name="url"]')).to_have_value(self.interpreter["url"])
        await form.locator('[name="url"]').fill("")
        await form.get_by_role("button", name="Save Parser Settings").click()
        await expect(form.locator("[data-interpreter-status]")).to_contain_text("saved")
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.posts[0][0], PREFIX + "interpreter/settings/")
        self.assertEqual(self.posts[0][1], {"url": "", "model": "qwen3.5:2b-q4_K_M"})
        self.assertEqual(self.posts[0][2]["x-csrftoken"], "a" * 32)
        await expect(self.page.locator('[data-speech-form] [name="url"]')).to_have_value(self.speech["url"])
        await expect(self.page.locator("[data-controller-form]")).to_have_count(1)

    async def test_parser_save_failure_retains_edits(self):
        self.parser_write_error = True
        form = self.page.locator("[data-interpreter-form]")
        await form.locator('[name="url"]').fill("http://retry.invalid:11434")
        await form.get_by_role("button", name="Save Parser Settings").click()
        await expect(form.locator("[data-interpreter-status]")).to_contain_text("Invalid parser URL")
        await expect(form.locator('[name="url"]')).to_have_value("http://retry.invalid:11434")
        await expect(form.get_by_role("button", name="Save Parser Settings")).to_be_enabled()

    async def test_parser_read_failure_preserves_voice_and_hardware_configuration(self):
        self.parser_read_error = True
        await self.page.reload()
        await expect(self.page.get_by_text("Request parser settings are unavailable.", exact=False)).to_be_visible()
        await expect(self.page.locator("[data-speech-form]")).to_be_visible()
        await expect(self.page.locator("[data-controller-form]")).to_have_count(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
