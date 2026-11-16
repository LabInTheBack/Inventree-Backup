"""Voice browser checks plus inherited finder regressions; synthetic audio only."""

import asyncio
import json
import re
import unittest

import browser_finder
from test_voice_requests import voice
from playwright.async_api import Error as PlaywrightError, expect


MOCK_MEDIA = r"""(() => {
  window.voiceMock = {mode: 'ok', stopped: 0, acquired: 0, bytes: 100};
  window.RealMediaRecorder = window.MediaRecorder;
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {configurable: true, value: async () => {
    if (voiceMock.mode === 'denied') throw new DOMException('denied', 'NotAllowedError');
    if (voiceMock.mode === 'pending') await new Promise((resolve) => {voiceMock.allow = resolve;});
    voiceMock.acquired++;
    return {getTracks: () => [{stop: () => {voiceMock.stopped++;}}]};
  }});
  window.MediaRecorder = class {
    static isTypeSupported(type) {return type.startsWith('audio/webm');}
    constructor(stream, options) {this.state = 'inactive'; this.mimeType = options.mimeType; voiceMock.recorder = this;}
    start() {this.state = 'recording';}
    stop() {
      this.state = 'inactive';
      setTimeout(() => {
        this.ondataavailable?.({data: new Blob([new Uint8Array(voiceMock.bytes)], {type: this.mimeType})});
        this.onstop?.();
      }, 0);
    }
  };
})();
"""


class VoiceBrowserTests(browser_finder.FinderBrowserTests):
    async def asyncSetUp(self):
        self.voice_mode = "success"
        self.voice_requests = []
        self.voice_delay = 0
        self.voice_started = asyncio.Event()
        self.interpret_mode = "success"
        self.interpret_delay = 0
        self.interpret_started = asyncio.Event()
        self.interpret_requests = []
        self.transcript_text = "Please find a 10 kilo ohm resistor and a 10 microfarad capacitor."
        await super().asyncSetUp()
        await self.context.add_init_script(MOCK_MEDIA)
        await self.page.reload()

    async def route(self, route):
        if route.request.url == browser_finder.ORIGIN + browser_finder.PREFIX + "interpret/":
            body = route.request.post_data_json
            self.interpret_requests.append(body)
            self.interpret_started.set()
            if self.interpret_delay:
                await asyncio.sleep(self.interpret_delay)
            if self.interpret_mode == "error":
                return await route.fulfill(status=503, json={"success": False, "error": "Interpretation unavailable"})
            if self.interpret_mode == "bad":
                return await route.fulfill(json={"success": True, "version": voice.INTERPRETER_VERSION, "requests": [{"query": "resistor"}]})
            if self.interpret_mode == "old":
                return await route.fulfill(json={"success": True, "version": 1, "requests": [{"query": "resistor"}]})
            try:
                if self.interpret_mode == "model":
                    payload = voice.interpret_requests("magnet; battery; silicone O-ring; DC motor")
                    payload["interpreter"] = "ollama"
                    payload["requests"][2]["notes"].append("Grouped 'silicone, O-rings' as one request. Check that its material belongs to this part.")
                else:
                    payload = voice.interpret_requests(body["text"])
                if self.interpret_mode == "fallback":
                    payload["interpreter"] = "rules"
                    payload["notice"] = "Cannot reach the local request parser; the standard parser was used."
            except ValueError as exc:
                return await route.fulfill(status=400, json={"success": False, "error": str(exc)})
            try:
                return await route.fulfill(json={"success": True, **payload})
            except PlaywrightError:
                return
        if route.request.url != browser_finder.ORIGIN + browser_finder.PREFIX + "transcribe/":
            return await super().route(route)
        request = route.request
        self.voice_requests.append({"headers": request.headers, "body": request.post_data_buffer})
        self.voice_started.set()
        if self.voice_delay:
            await asyncio.sleep(self.voice_delay)
        if self.voice_mode == "session":
            return await route.fulfill(status=403, json={"success": False})
        if self.voice_mode == "error":
            return await route.fulfill(status=504, json={"success": False, "error": "Transcription timed out. Try a shorter recording."})
        if self.voice_mode == "bad":
            return await route.fulfill(json={"success": True, "text": []})
        if self.voice_mode == "html":
            return await route.fulfill(content_type="text/html", body="<h1>Proxy error</h1>")
        try:
            return await route.fulfill(json={"success": True, "text": self.transcript_text})
        except PlaywrightError:
            return

    async def record(self):
        await self.page.get_by_role("button", name="Record request", exact=True).click()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("Recording…")

    async def finish(self):
        await self.record()
        await self.page.get_by_role("button", name="Stop and transcribe").click()
        await expect(self.page.locator("[data-voice-review]")).to_be_visible()
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()

    async def test_voice_transcript_is_editable_and_does_not_change_search_or_selection(self):
        await self.search("NE555")
        await self.add("NE555")
        await expect(self.page.locator("[data-locate]")).to_be_enabled()
        before = len(self.requests)
        await self.finish()
        await expect(self.page.locator("#part-queries")).to_have_value("NE555")
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")
        await expect(self.page.locator("[data-locate]")).to_be_enabled()
        self.assertEqual(len(self.requests), before)
        self.assertEqual(len(self.voice_requests), 1)
        self.assertIn("audio/webm", self.voice_requests[0]["headers"]["content-type"])
        self.assertTrue(self.voice_requests[0]["headers"].get("x-csrftoken"))
        self.assertNotIn("x-speech-language", self.voice_requests[0]["headers"])
        await self.page.locator("#voice-transcript").fill("10k resistor\n100nF capacitor")
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await self.page.get_by_role("button", name="Interpret request", exact=True).click()
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await self.page.get_by_role("button", name="Add to parts to find").click()
        await expect(self.page.locator("#part-queries")).to_have_value("NE555\n10k resistor\n100nF capacitor")
        self.assertEqual(len(self.requests), before)
        self.assertEqual((await self.stored_state())["search_text"], "NE555\n10k resistor\n100nF capacitor")
        self.assertTrue(await self.page.evaluate("voiceMock.stopped > 0"))
        await self.page.get_by_role("button", name="Search parts", exact=True).click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("3 searches")

    async def test_voice_denied_microphone_keeps_typed_search_working(self):
        await self.page.evaluate("voiceMock.mode = 'denied'")
        await self.page.get_by_role("button", name="Record request", exact=True).click()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("denied")
        await expect(self.page.get_by_role("button", name="Record request", exact=True)).to_be_enabled()
        await self.search("NE555")
        self.assertEqual(self.voice_requests, [])

    async def test_voice_discard_during_recording_never_uploads(self):
        await self.record()
        await self.page.get_by_role("button", name="Discard recording").click()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("discarded")
        await self.page.wait_for_timeout(100)
        self.assertEqual(self.voice_requests, [])
        self.assertTrue(await self.page.evaluate("voiceMock.stopped > 0"))

    async def test_voice_late_microphone_permission_after_discard_releases_tracks(self):
        await self.page.evaluate("voiceMock.mode = 'pending'")
        await self.page.get_by_role("button", name="Record request", exact=True).click()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("permission")
        await self.page.get_by_role("button", name="Discard recording").click()
        await self.page.evaluate("voiceMock.allow()")
        await self.page.wait_for_function("voiceMock.stopped === 1")
        self.assertEqual(self.voice_requests, [])

    async def test_voice_transcription_error_can_retry_without_recording_again(self):
        self.voice_mode = "error"
        await self.record()
        await self.page.get_by_role("button", name="Stop and transcribe").click()
        await expect(self.page.get_by_role("button", name="Retry transcription")).to_be_visible()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("timed out")
        self.voice_mode = "success"
        await self.page.get_by_role("button", name="Retry transcription").click()
        await expect(self.page.locator("[data-voice-review]")).to_be_visible()
        self.assertEqual(len(self.voice_requests), 2)
        self.assertEqual(await self.page.evaluate("voiceMock.acquired"), 1)
        self.assertEqual(self.voice_requests[0]["body"], self.voice_requests[1]["body"])
        self.assertEqual(self.requests, [])

    async def test_voice_session_and_malformed_responses_are_recoverable(self):
        for mode, expected in (("session", "expired"), ("bad", "invalid transcript"), ("html", "Transcription failed")):
            self.voice_mode = mode
            await self.record()
            await self.page.get_by_role("button", name="Stop and transcribe").click()
            await expect(self.page.locator("[data-voice-status]")).to_contain_text(expected)
            await expect(self.page.get_by_role("button", name="Record request", exact=True)).to_be_enabled()
        await self.search("NE555")

    async def test_voice_oversized_and_empty_recording_never_upload(self):
        for size, expected in ((4194305, "exceeds"), (0, "empty")):
            await self.page.evaluate("size => {voiceMock.bytes = size;}", size)
            await self.record()
            await self.page.get_by_role("button", name="Stop and transcribe").click()
            await expect(self.page.locator("[data-voice-status]")).to_contain_text(expected)
        self.assertEqual(self.voice_requests, [])

    async def test_voice_time_limit_stops_and_transcribes(self):
        await self.page.clock.install()
        await self.record()
        await self.page.clock.fast_forward(61000)
        await expect(self.page.locator("[data-voice-review]")).to_be_visible()
        self.assertEqual(len(self.voice_requests), 1)
        self.assertTrue(await self.page.evaluate("voiceMock.stopped > 0"))

    async def test_voice_pagehide_discards_active_microphone_without_upload(self):
        await self.record()
        await self.page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        await self.page.wait_for_timeout(100)
        self.assertEqual(self.voice_requests, [])
        self.assertTrue(await self.page.evaluate("voiceMock.stopped > 0"))

    async def test_voice_upload_does_not_lock_typed_search(self):
        self.voice_delay = 1
        await self.record()
        await self.page.get_by_role("button", name="Stop and transcribe").click()
        await self.voice_started.wait()
        await expect(self.page.locator("#part-queries")).to_be_enabled()
        await self.search("NE555")
        await expect(self.page.locator("[data-voice-review]")).to_be_visible()
        self.assertEqual(len(self.voice_requests), 1)

    async def test_voice_actual_browser_encoder_uploads_webm_and_stops_track(self):
        await self.page.evaluate("""() => {
          window.MediaRecorder = window.RealMediaRecorder;
          const context = new AudioContext();
          const oscillator = context.createOscillator();
          const destination = context.createMediaStreamDestination();
          oscillator.connect(destination); oscillator.start();
          window.realAudio = {context, oscillator, stream: destination.stream};
          Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => destination.stream});
        }""")
        await self.record()
        await self.page.wait_for_timeout(350)
        await self.page.get_by_role("button", name="Stop and transcribe").click()
        await expect(self.page.locator("[data-voice-review]")).to_be_visible()
        self.assertTrue(self.voice_requests[0]["body"].startswith(bytes.fromhex("1a45dfa3")))
        self.assertTrue(await self.page.evaluate("realAudio.stream.getTracks().every(track => track.readyState === 'ended')"))
        await self.page.evaluate("realAudio.oscillator.stop(); realAudio.context.close()")

    async def test_voice_draft_is_not_persisted_before_explicit_add(self):
        await self.finish()
        await self.page.locator("#voice-transcript").fill("private draft")
        self.assertIsNone(await self.stored_state())
        await self.page.reload()
        await expect(self.page.locator("[data-voice-review]")).to_be_hidden()
        await expect(self.page.locator("#part-queries")).to_have_value("")

    async def test_voice_missing_browser_support_keeps_typing_available(self):
        await self.context.add_init_script("window.MediaRecorder = undefined")
        await self.page.reload()
        await expect(self.page.get_by_role("button", name="Record request", exact=True)).to_be_disabled()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("unavailable")
        await self.search("NE555")

    async def test_local_model_lines_and_grouping_note_require_explicit_add_and_search(self):
        self.interpret_mode = "model"
        self.transcript_text = "Find magnets, batteries, silicone, O-rings and DC motors."
        await self.finish()
        await expect(self.page.locator("#voice-queries")).to_have_value("magnet\nbattery\nsilicone O-ring\nDC motor")
        await expect(self.page.locator("[data-voice-notes]")).to_contain_text("Check that its material belongs")
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("using the local model")
        await expect(self.page.locator("#part-queries")).to_have_value("")
        self.assertEqual(self.requests, [])
        await self.page.locator("[data-voice-use]").click()
        await expect(self.page.locator("#part-queries")).to_have_value("magnet\nbattery\nsilicone O-ring\nDC motor")
        self.assertEqual(self.requests, [])

    async def test_model_fallback_notice_is_visible_and_standard_queries_remain_usable(self):
        self.interpret_mode = "fallback"
        await self.finish()
        await expect(self.page.locator("[data-voice-notes]")).to_contain_text("standard parser was used")
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await expect(self.page.locator("#part-queries")).to_have_value("")
        self.assertEqual(self.requests, [])

    async def test_voice_has_no_language_controls_and_prepares_english_queries(self):
        await expect(self.page.locator("#voice-language")).to_have_count(0)
        await self.finish()
        self.assertEqual(self.interpret_requests[-1], {"text": self.transcript_text})
        self.assertNotIn("x-speech-language", self.voice_requests[-1]["headers"])
        self.assertEqual(len((await self.page.locator("#voice-queries").input_value()).splitlines()), 2)
        await expect(self.page.locator("#part-queries")).to_have_value("")
        self.assertEqual(self.requests, [])

    async def test_voice_prompt4_prepares_five_lines_and_keeps_last_request_visible(self):
        self.transcript_text = "Batteries, two silicone O-rings, 3 magnets, two magnets, PNP transistors"
        await self.finish()
        expected = "battery\nsilicone O-ring\nmagnet\nmagnet\nPNP transistor"
        await expect(self.page.locator("#voice-queries")).to_have_value(expected)
        await expect(self.page.locator("[data-voice-notes]")).to_contain_text("quantity: 2")
        self.assertEqual(self.requests, [])
        await self.page.locator("[data-voice-use]").click()
        await expect(self.page.locator("#part-queries")).to_have_value(expected)
        await self.page.locator("[data-voice-last] summary").click()
        await expect(self.page.locator("[data-voice-last-transcript]")).to_have_text(self.transcript_text)
        await expect(self.page.locator("[data-voice-last-queries]")).to_have_text(expected)
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("5 searches")
        self.assertEqual(self.requests[-1][1]["queries"], expected.splitlines())
        self.assertEqual(self.requests[-1][1]["component_queries"], [0, 1, 2, 3, 4])
        await expect(self.page.locator("[data-results]")).to_contain_text("No matching battery parts")
        await expect(self.page.locator("[data-results]")).to_contain_text("Component type: PNP transistor")
        await self.page.reload()
        await expect(self.page.locator("[data-voice-last]")).to_be_hidden()

    async def test_component_modes_keep_same_text_typed_and_interpreted_separate(self):
        await self.page.locator("#part-queries").fill("magnet")
        self.transcript_text = "Find a magnet."
        await self.finish()
        await self.page.locator("[data-voice-use]").click()
        await expect(self.page.locator("[data-component-status]")).to_contain_text("1 interpreted search line")
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("2 searches")
        self.assertEqual(self.requests[-1][1], {"queries": ["magnet", "magnet"], "component_queries": [1]})
        self.assertEqual(await self.page.locator("[data-results] p.query-note").filter(has_text="Component type:").all_text_contents(),
                         ["Component type: magnet"])
        await self.page.locator("[data-results] summary").filter(has_text="Category filter").click()
        await expect(self.page.locator("[data-results]")).to_contain_text("Mechanical/Magnets")

    async def test_component_modes_survive_reload_without_search_or_transcript_storage(self):
        await self.page.locator("#part-queries").fill("NE555")
        self.transcript_text = "Find O-rings and a DC motor."
        await self.finish()
        await self.page.locator("[data-voice-use]").click()
        state = await self.stored_state()
        self.assertEqual(state, {"version": 1, "part_ids": [], "search_text": "NE555\nO-ring\nDC motor", "component_queries": [1, 2]})
        before = len(self.requests)
        await self.page.reload()
        self.assertEqual(len(self.requests), before)
        await expect(self.page.locator("[data-component-status]")).to_contain_text("2 interpreted search lines")
        await expect(self.page.locator("[data-voice-last]")).to_be_hidden()
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("3 searches")
        self.assertEqual(self.requests[-1][1]["component_queries"], [1, 2])

    async def test_editing_one_interpreted_line_preserves_other_modes_after_insertion(self):
        self.transcript_text = "Find O-rings and a DC motor."
        await self.finish()
        await self.page.locator("[data-voice-use]").click()
        await self.page.locator("#part-queries").fill("NE555\nO-ring\n12V motor")
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("3 searches")
        self.assertEqual(self.requests[-1][1], {"queries": ["NE555", "O-ring", "12V motor"], "component_queries": [1]})
        await self.page.locator("#part-queries").fill("NE555\n12V motor")
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results-count]")).to_have_text("2 searches")
        self.assertEqual(self.requests[-1][1], {"queries": ["NE555", "12V motor"]})

    async def test_interpreted_unknown_type_reports_literal_fallback_and_pages_keep_mode(self):
        await self.page.locator("[data-voice-paste]").click()
        await self.page.locator("#voice-transcript").fill("Find many")
        await self.page.locator("[data-voice-interpret]").click()
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await self.page.locator("[data-voice-use]").click()
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-results]")).to_contain_text("Component type not recognized safely")
        await self.page.locator("[data-load-more]").click()
        await expect(self.page.locator("[data-match]")).to_have_count(9)
        self.assertEqual(self.requests[-1][1], {"queries": ["many"], "cursor": "page-2:many", "component_queries": [0]})

    async def test_missing_server_type_confirmation_keeps_selection_and_reports_error(self):
        await self.search("NE555")
        await self.add("NE555")
        self.transcript_text = "Find a magnet."
        await self.finish()
        await self.page.locator("[data-voice-use]").click()
        self.search_mode = "no_types"
        await self.page.locator("[data-search-button]").click()
        await expect(self.page.locator("[data-search-status]")).to_contain_text("filtering was not confirmed")
        await expect(self.page.locator("[data-selected-count]")).to_have_text("1")
        self.assertNotIn("locate", [endpoint for endpoint, _, _ in self.requests])

    async def test_invalid_saved_component_indexes_are_discarded(self):
        for indexes in ([True], [1], [0, 0], "0", [0.5]):
            await self.page.evaluate("([key, indexes]) => localStorage.setItem(key, JSON.stringify({version: 1, part_ids: [], search_text: 'magnet', component_queries: indexes}))",
                                     [browser_finder.STORAGE_KEY, indexes])
            await self.page.reload()
            await expect(self.page.locator("#part-queries")).to_have_value("")
            self.assertIsNone(await self.stored_state())

    async def test_voice_flagged_misheard_word_cannot_be_added_without_correction(self):
        self.transcript_text = "Find orderings and a DC motor."
        await self.record()
        await self.page.locator("[data-voice-stop]").click()
        await expect(self.page.locator("[data-voice-query-status]")).to_contain_text("need correction")
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await self.page.locator("#voice-transcript").fill("Find O-rings and a DC motor.")
        await self.page.locator("[data-voice-interpret]").click()
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await expect(self.page.locator("#voice-queries")).to_have_value("O-ring\nDC motor")
        self.assertEqual(self.requests, [])

    async def test_voice_stale_interpretation_response_is_not_accepted(self):
        self.interpret_mode = "old"
        await self.record()
        await self.page.locator("[data-voice-stop]").click()
        await expect(self.page.locator("[data-voice-query-status]")).to_contain_text("outdated")
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await self.search("NE555")

    async def test_voice_paste_interprets_multiple_parts_without_microphone(self):
        await self.page.get_by_role("button", name="Type or paste request").click()
        await self.page.locator("#voice-transcript").fill("find a 10k resistor and a 10 microfarad capacitor.")
        await self.page.get_by_role("button", name="Interpret request", exact=True).click()
        await expect(self.page.locator("#voice-queries")).to_have_value("10k resistor\n10uF capacitor")
        await self.page.screenshot(path=str(browser_finder.ROOT / "voice-review.png"), full_page=True)
        await self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        await self.page.screenshot(path=str(browser_finder.ROOT / "voice-phone.png"), full_page=True)
        await self.page.get_by_role("button", name="Add to parts to find").click()
        await expect(self.page.locator("#part-queries")).to_have_value("10k resistor\n10uF capacitor")
        self.assertEqual(self.voice_requests, [])
        self.assertEqual(self.requests, [])

    async def test_voice_query_edits_are_used_instead_of_raw_transcript(self):
        await self.finish()
        await self.page.locator("#voice-queries").fill("NE555\nM3 nut")
        await self.page.get_by_role("button", name="Add to parts to find").click()
        await expect(self.page.locator("#part-queries")).to_have_value("NE555\nM3 nut")
        self.assertEqual(self.requests, [])

    async def test_voice_uncertainty_is_flagged_and_unknown_constraint_is_retained(self):
        self.transcript_text = "Find a MOSFET with drain to source of around 40 volts and a capacitor of 10 microfarads."
        await self.finish()
        await expect(self.page.locator("[data-voice-notes]")).to_contain_text("Ranges")
        await expect(self.page.locator("[data-voice-notes]")).to_contain_text("literal search text")
        self.assertIn("around 40V", await self.page.locator("#voice-queries").input_value())
        self.assertEqual(self.requests, [])

    async def test_voice_interpretation_failure_allows_explicit_manual_search_lines(self):
        for mode in ("error", "bad"):
            self.interpret_mode = mode
            await self.record()
            await self.page.get_by_role("button", name="Stop and transcribe").click()
            await expect(self.page.locator("[data-voice-query-status]")).to_contain_text("unavailable" if mode == "error" else "incomplete")
            await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await self.page.locator("#voice-queries").fill("10k resistor\n10uF capacitor")
        await self.page.get_by_role("button", name="Add to parts to find").click()
        await expect(self.page.locator("#part-queries")).to_have_value("10k resistor\n10uF capacitor")
        self.assertEqual(self.requests, [])

    async def test_voice_query_limits_do_not_truncate_or_append_invalid_lines(self):
        await self.finish()
        long_line = "resistor " + "x" * 300
        await self.page.locator("#voice-queries").fill(long_line)
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await expect(self.page.locator("#voice-queries")).to_have_value(long_line)
        await self.page.locator("#part-queries").fill("\n".join(["NE555"] * 20))
        await self.page.locator("#voice-queries").fill("capacitor")
        await self.page.get_by_role("button", name="Add to parts to find").click()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("exceed 20")
        self.assertEqual(len((await self.page.locator("#part-queries").input_value()).splitlines()), 20)

    async def test_voice_browser_without_microphone_can_use_pasted_requests(self):
        await self.context.add_init_script("window.MediaRecorder = undefined")
        await self.page.reload()
        await self.page.get_by_role("button", name="Type or paste request").click()
        await self.page.locator("#voice-transcript").fill("Find a ten kilo ohm resistor and a ten microfarad capacitor.")
        await self.page.get_by_role("button", name="Interpret request", exact=True).click()
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        self.assertEqual(len((await self.page.locator("#voice-queries").input_value()).splitlines()), 2)
        self.assertEqual(self.voice_requests, [])

    async def test_voice_old_backend_boot_config_keeps_typed_search_working(self):
        async def legacy(route):
            html = (browser_finder.ROOT / "index.html").read_text()
            def remove_interpreter(match):
                config = json.loads(match[2])
                config.pop("interpret_url", None)
                return match[1] + json.dumps(config) + match[3]
            html = re.sub(r'(<script id="finder-config" type="application/json">)(.*?)(</script>)', remove_interpreter, html, flags=re.S)
            await route.fulfill(content_type="text/html", body=html)
        await self.page.route(browser_finder.ORIGIN + browser_finder.PREFIX, legacy)
        await self.page.reload()
        await expect(self.page.locator("[data-voice-status]")).to_contain_text("Restart InvenTree")
        await expect(self.page.locator("[data-voice-record]")).to_be_disabled()
        await expect(self.page.locator("[data-voice-paste]")).to_be_disabled()
        await self.search("NE555")

    async def test_elapsed_times_are_separate_and_stop_on_completion(self):
        self.voice_delay = 1
        self.interpret_delay = 1
        await self.record()
        await self.page.locator("[data-voice-stop]").click()
        await asyncio.wait_for(self.voice_started.wait(), timeout=5)
        transcription = self.page.locator("[data-voice-transcription-time]")
        interpretation = self.page.locator("[data-voice-interpretation-time]")
        await expect(transcription).to_contain_text("Transcribing")
        await self.page.wait_for_timeout(300)
        self.assertNotIn("0.0 s", await transcription.inner_text())
        await asyncio.wait_for(self.interpret_started.wait(), timeout=5)
        await expect(transcription).to_contain_text("Transcribed")
        await expect(interpretation).to_contain_text("Interpreting")
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await expect(interpretation).to_contain_text("Interpreted")
        completed = await interpretation.inner_text()
        await self.page.wait_for_timeout(300)
        self.assertEqual(await interpretation.inner_text(), completed)
        self.assertEqual(self.requests, [])

    async def test_clear_searches_discards_pending_audio_and_stale_transcript(self):
        self.voice_delay = .6
        await self.record()
        await self.page.locator("[data-voice-stop]").click()
        await asyncio.wait_for(self.voice_started.wait(), timeout=5)
        await self.page.locator("[data-clear-searches]").click()
        await self.page.wait_for_timeout(750)
        await expect(self.page.locator("#voice-transcript")).to_have_value("")
        await expect(self.page.locator("[data-voice-workspace]")).to_be_hidden()
        await expect(self.page.locator("[data-voice-transcription-time]")).to_be_hidden()
        await expect(self.page.locator("[data-voice-record]")).to_be_enabled()
        self.assertEqual(self.interpret_requests, [])
        self.assertEqual(self.requests, [])

    async def test_cancel_interpretation_keeps_transcript_and_ignores_late_response(self):
        self.interpret_delay = .6
        await self.page.locator("[data-voice-paste]").click()
        await self.page.locator("#voice-transcript").fill("Find a 10k resistor")
        await self.page.locator("[data-voice-interpret]").click()
        await asyncio.wait_for(self.interpret_started.wait(), timeout=5)
        await self.page.get_by_role("button", name="Cancel request", exact=True).click()
        await self.page.wait_for_timeout(750)
        await expect(self.page.locator("#voice-transcript")).to_have_value("Find a 10k resistor")
        await expect(self.page.locator("#voice-queries")).to_have_value("")
        await expect(self.page.locator("[data-voice-interpretation-time]")).to_contain_text("Cancelled")
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        self.assertEqual(self.requests, [])

    async def test_voice_add_search_lines_respects_hardware_action_lock(self):
        await self.finish()
        await self.search("NE555")
        await self.add("NE555")
        await expect(self.page.locator("[data-locate]")).to_be_enabled()
        self.locate_delay = 0.4
        await self.page.locator("[data-locate]").click()
        await expect(self.page.locator("[data-voice-use]")).to_be_disabled()
        await expect(self.page.locator("[data-action-status]")).to_contain_text("Part located")
        await expect(self.page.locator("[data-voice-use]")).to_be_enabled()
        await self.page.locator("[data-voice-use]").click()
        self.assertIn("10uF capacitor", await self.page.locator("#part-queries").input_value())
        self.assertEqual(sum(endpoint == "locate" for endpoint, *_ in self.requests), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
