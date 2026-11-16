"""Voice API boundaries and transport; no production DB, microphones or network."""

import importlib
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_facade


@unittest.skipUnless(importlib.util.find_spec("django"), "Django is available in the InvenTree container")
class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.case = test_facade.FacadeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.plugin = self.case.plugin
        self.speech = importlib.import_module("locator_facade_test.speech")
        self.views = self.case.views.PluginViews(self.plugin)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        guard = patch.object(self.speech, "speech_lock_path", return_value=Path(self.temporary.name) / "speech.lock")
        guard.start()
        self.addCleanup(guard.stop)
        self.session = Mock()
        self.session.__enter__ = Mock(return_value=self.session)
        self.session.__exit__ = Mock(return_value=False)
        guard = patch.object(self.speech.requests, "Session", return_value=self.session)
        guard.start()
        self.addCleanup(guard.stop)
        self.plugin.search_parts = Mock(side_effect=AssertionError("Transcription must not search"))
        self.plugin.locate_parts = Mock(side_effect=AssertionError("Transcription must not locate"))
        self.plugin.off = Mock(side_effect=AssertionError("Transcription must not clear lights"))

    def request(self, audio=b"fake audio", content_type="audio/webm;codecs=opus", csrf=True, language=None):
        from django.conf import settings
        from django.middleware.csrf import get_token
        from django.test import RequestFactory
        request = RequestFactory().post("/plugin/wled-locator-plus/finder/transcribe/", data=audio, content_type=content_type)
        request.META["CONTENT_TYPE"] = content_type
        request.content_type = content_type.split(";", 1)[0]
        request.user = types.SimpleNamespace(is_authenticated=True, is_superuser=True)
        if language is not None:
            request.META["HTTP_X_SPEECH_LANGUAGE"] = language
        if csrf:
            token = get_token(request)
            request.COOKIES[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
            request.META["HTTP_X_CSRFTOKEN"] = token
        return request

    def configure(self, **overrides):
        return self.speech.save_config(self.plugin, {
            "url": "http://speech.invalid:8000", "model": self.speech.DEFAULT_MODEL, **overrides,
        })

    def upstream(self, payload=None, status=200, chunks=None):
        response = Mock(status_code=status)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = chunks if chunks is not None else [json.dumps(payload or {"text": "10 kilo ohm resistor"}).encode()]
        self.session.post.return_value = response
        return response

    def test_raw_audio_requires_post_superuser_csrf_and_supported_type_before_transport(self):
        get = self.case.finder_request(method="GET")
        self.assertEqual(self.views.finder_transcribe(get).status_code, 405)
        for attribute in ("is_authenticated", "is_superuser"):
            request = self.request()
            setattr(request.user, attribute, False)
            self.assertEqual(self.views.finder_transcribe(request).status_code, 403)
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=["testserver"]):
            self.assertEqual(self.views.finder_transcribe(self.request(csrf=False)).status_code, 403)
        self.assertEqual(self.views.finder_transcribe(self.request(content_type="text/plain")).status_code, 415)
        self.session.post.assert_not_called()
        self.plugin._read_plugin_setting.assert_not_called()

    def test_empty_oversized_and_declared_oversized_audio_never_reach_service(self):
        self.assertEqual(self.views.finder_transcribe(self.request(audio=b"")).status_code, 400)
        response = self.views.finder_transcribe(self.request(audio=b"x" * (self.speech.MAX_AUDIO_BYTES + 1)))
        self.assertEqual(response.status_code, 413)
        request = self.request()
        request.META["CONTENT_LENGTH"] = str(self.speech.MAX_AUDIO_BYTES + 1)
        request.read = Mock(side_effect=AssertionError("Reject declared oversized body before reading"))
        self.assertEqual(self.views.finder_transcribe(request).status_code, 413)
        for length in ("invalid", "²", "9" * 5000):
            request.META["CONTENT_LENGTH"] = length
            self.assertEqual(self.views.finder_transcribe(request).status_code, 400)
        self.session.post.assert_not_called()

    def test_body_read_is_bounded_even_without_content_length(self):
        self.configure()
        request = self.request()
        request.META.pop("CONTENT_LENGTH")
        request.read = Mock(return_value=b"x" * (self.speech.MAX_AUDIO_BYTES + 1))
        self.assertEqual(self.views.finder_transcribe(request).status_code, 413)
        request.read.assert_called_once_with(self.speech.MAX_AUDIO_BYTES + 1)
        self.session.post.assert_not_called()

    def test_success_uses_server_model_and_codec_normalization_without_inventory(self):
        self.configure(url="http://speech.invalid:8000/v1/")
        self.upstream({"text": "  10 kilo ohm resistor  "})
        response = self.views.finder_transcribe(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(json.loads(response.content)["text"], "10 kilo ohm resistor")
        args, kwargs = self.session.post.call_args
        self.assertEqual(args, ("http://speech.invalid:8000/v1/audio/transcriptions",))
        self.assertEqual(kwargs["data"], {"model": self.speech.DEFAULT_MODEL, "response_format": "json", "temperature": "0", "language": "en", "prompt": self.speech.TRANSCRIPTION_PROMPT})
        self.assertIn("O-rings", kwargs["data"]["prompt"])
        self.assertIn("PNP and NPN", kwargs["data"]["prompt"])
        self.assertLess(len(kwargs["data"]["prompt"]), 512)
        self.assertEqual(kwargs["files"], {"file": ("recording.webm", b"fake audio", "audio/webm")})
        self.assertEqual(kwargs["timeout"], (3, 60))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertFalse(self.session.trust_env)
        self.plugin.search_parts.assert_not_called()
        self.plugin.locate_parts.assert_not_called()
        self.plugin.off.assert_not_called()

    def test_transcription_always_uses_english_and_mp4_is_supported(self):
        self.configure()
        self.upstream()
        self.assertEqual(self.views.finder_transcribe(self.request(content_type="audio/mp4")).status_code, 200)
        self.assertEqual(self.session.post.call_args.kwargs["data"]["language"], "en")
        self.assertEqual(self.session.post.call_args.kwargs["files"]["file"][0], "recording.m4a")

    def test_retired_stored_language_cannot_reenable_other_languages(self):
        config = self.configure()
        self.upstream()
        for language in ("en", "de", "ru", "auto", ""):
            self.case.store.values["_SPEECH_CONFIG"] = json.dumps({**config, "language": language})
            self.assertEqual(self.speech.get_config(self.plugin), config)
            self.assertEqual(self.views.finder_transcribe(self.request()).status_code, 200)
            self.assertEqual(self.session.post.call_args.kwargs["data"]["language"], "en")

    def test_other_recording_languages_are_rejected_before_reading_audio_or_settings(self):
        for language in ("de", "ru", "auto", "fr", "DE", "", "http://bad", "en,de"):
            request = self.request(language=language)
            request.read = Mock(side_effect=AssertionError("Reject invalid language before reading audio"))
            response = self.views.finder_transcribe(request)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.content)["code"], "speech_language")
        self.session.post.assert_not_called()
        self.plugin._read_plugin_setting.assert_not_called()

    def test_interpret_endpoint_prepares_english_requests_without_inventory_or_speech(self):
        for text in ("find a 10k resistor and a 10 microfarad capacitor.",
                     "Please find a ten kilo ohm resistor and a ten microfarad capacitor."):
            response = self.views.finder_interpret(self.case.finder_request({"text": text}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store")
            result = json.loads(response.content)
            self.assertEqual(len(result["requests"]), 2)
            self.assertTrue(all(not row["warnings"] for row in result["requests"]), result)
        self.assertTrue(all(call.args == ("_INTERPRETER_CONFIG",)
                            for call in self.plugin._read_plugin_setting.call_args_list))
        self.session.post.assert_not_called()
        self.plugin.search_parts.assert_not_called()
        self.plugin.locate_parts.assert_not_called()
        self.plugin.off.assert_not_called()

    def test_interpret_endpoint_is_protected_bounded_and_never_runs_search(self):
        self.assertEqual(self.views.finder_interpret(self.case.finder_request(method="GET")).status_code, 405)
        request = self.case.finder_request({"text": "resistor"})
        request.user.is_superuser = False
        self.assertEqual(self.views.finder_interpret(request).status_code, 403)
        self.assertEqual(self.views.finder_interpret(self.case.finder_request({"text": "resistor"}, csrf=False)).status_code, 403)
        for payload in ({}, {"text": ""}, {"text": "x" * 8193}, {"text": "resistor", "language": "fr"}, {"text": ";".join(["resistor"] * 21)}):
            self.assertEqual(self.views.finder_interpret(self.case.finder_request(payload)).status_code, 400)
        for body, content_type, status in (("{", "application/json", 400), ("{}", "text/plain", 415), ("x" * 65537, "application/json", 413)):
            self.assertEqual(self.views.finder_interpret(self.case.finder_request(body=body, content_type=content_type)).status_code, status)
        self.plugin._read_plugin_setting.assert_not_called()
        self.session.post.assert_not_called()

    def test_unconfigured_or_corrupt_settings_leave_typed_finder_usable(self):
        for value in ("", "{", "[]", '{"url":"ftp://bad"}', '{"language":null}'):
            self.case.store.values["_SPEECH_CONFIG"] = value
            response = self.views.finder_transcribe(self.request())
            self.assertEqual(response.status_code, 503)
            self.assertEqual(json.loads(response.content)["code"], "speech_not_configured")
            self.assertEqual(self.views.finder_page(self.case.finder_request(method="GET")).status_code, 200)
        self.session.post.assert_not_called()

    def test_service_errors_are_sanitized_and_audio_is_retryable(self):
        self.configure()
        for status in (301, 400, 401, 404, 413, 500):
            self.upstream(status=status)
            response = self.views.finder_transcribe(self.request())
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("speech.invalid", response.content.decode())
        self.session.post.side_effect = self.speech.requests.Timeout("private upstream details")
        response = self.views.finder_transcribe(self.request())
        self.assertEqual(response.status_code, 504)
        self.assertNotIn("private upstream", response.content.decode())
        self.session.post.side_effect = self.speech.requests.ConnectionError("private upstream details")
        self.assertEqual(self.views.finder_transcribe(self.request()).status_code, 502)

    def test_invalid_empty_and_oversized_transcripts_have_clear_errors(self):
        self.configure()
        cases = [({"text": "  "}, 422), ({"text": 1}, 502), ({"text": "x" * 8193}, 502), ({"other": "value"}, 502), (["text"], 502)]
        for payload, status in cases:
            self.upstream(payload)
            self.assertEqual(self.views.finder_transcribe(self.request()).status_code, status)
        for chunks in ([b"<html>proxy error</html>"], [b"x" * 65537]):
            self.upstream(chunks=chunks)
            self.assertEqual(self.views.finder_transcribe(self.request()).status_code, 502)

    def test_overlapping_transcription_is_rejected_and_lock_is_released_after_errors(self):
        self.configure()
        self.upstream()
        with self.speech.transcription_slot():
            response = self.views.finder_transcribe(self.request())
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response["Retry-After"], "2")
            self.assertEqual(json.loads(response.content)["code"], "speech_busy")
        self.session.post.assert_not_called()
        self.session.post.side_effect = self.speech.requests.Timeout()
        self.assertEqual(self.views.finder_transcribe(self.request()).status_code, 504)
        self.session.post.side_effect = None
        self.assertEqual(self.views.finder_transcribe(self.request()).status_code, 200)

    def test_config_save_is_one_setting_and_invalid_values_do_not_change_it(self):
        config = self.configure()
        saved = self.case.store.values["_SPEECH_CONFIG"]
        invalid = [
            {"url": "ftp://bad"}, {"url": "http://u:p@host"}, {"url": "http://host:bad"},
            {"url": "http://host?token=secret"}, {"url": "http://host/#fragment"}, {"url": "http://host/\npath"},
            {"url": None}, {"model": ""}, {"model": "a b"}, {"language": "english"},
            {"language": "en"}, {"language": "de"}, {"language": "ru"}, {"language": "auto"}, {"unknown": 1},
        ]
        for payload in invalid:
            response = self.views.speech_settings(self.case.finder_request(payload))
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(self.case.store.values["_SPEECH_CONFIG"], saved)
        response = self.views.speech_settings(self.case.finder_request(config))
        self.assertEqual(response.status_code, 200)
        response = self.views.speech_settings(self.case.finder_request(method="GET"))
        self.assertEqual(json.loads(response.content)["speech"], config)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.session.post.assert_not_called()

    def test_speech_settings_require_superuser_and_protected_json_writes(self):
        request = self.case.finder_request(method="GET")
        request.user.is_superuser = False
        self.assertEqual(self.views.speech_settings(request).status_code, 403)
        request = self.case.finder_request({})
        request.user.is_authenticated = False
        self.assertEqual(self.views.speech_settings(request).status_code, 403)
        self.assertEqual(self.views.speech_settings(self.case.finder_request({}, csrf=False)).status_code, 403)
        for body, content_type, status in (("{", "application/json", 400), ("{}", "text/plain", 415), ("x" * 65537, "application/json", 413)):
            response = self.views.speech_settings(self.case.finder_request(body=body, content_type=content_type))
            self.assertEqual(response.status_code, status)
        self.plugin._read_plugin_setting.assert_not_called()
