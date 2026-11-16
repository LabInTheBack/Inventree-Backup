"""Local model boundaries and conservative fallback, without live services/DB."""

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_facade


@unittest.skipUnless(importlib.util.find_spec("django"), "Django is available in the InvenTree container")
class RequestInterpreterTests(unittest.TestCase):
    def setUp(self):
        self.case = test_facade.FacadeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.plugin = self.case.plugin
        self.module = importlib.import_module("locator_facade_test.request_interpreter")
        self.views = self.case.views.PluginViews(self.plugin)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        lock = patch.object(self.module, "lock_path", return_value=Path(self.temporary.name) / "model.lock")
        lock.start()
        self.addCleanup(lock.stop)
        self.session = Mock()
        self.session.__enter__ = Mock(return_value=self.session)
        self.session.__exit__ = Mock(return_value=False)
        guard = patch.object(self.module.requests, "Session", return_value=self.session)
        guard.start()
        self.addCleanup(guard.stop)
        self.plugin.search_parts = Mock(side_effect=AssertionError("Interpretation must not search"))
        self.plugin.locate_parts = Mock(side_effect=AssertionError("Interpretation must not locate"))
        self.plugin.off = Mock(side_effect=AssertionError("Interpretation must not clear lights"))

    def configure(self):
        return self.module.save_config(self.plugin, {"url": "http://ollama.invalid:11434"})

    def upstream(self, items=None, result=None, status=200, chunks=None):
        if result is None:
            result = {"done": True, "done_reason": "stop", "message": {"content": json.dumps({"items": items or ["resistor"]})}}
        response = Mock(status_code=status)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = chunks if chunks is not None else [json.dumps(result).encode()]
        self.session.post.return_value = response

    def interpret(self, text):
        response = self.views.finder_interpret(self.case.finder_request({"text": text}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.plugin.search_parts.assert_not_called()
        self.plugin.locate_parts.assert_not_called()
        self.plugin.off.assert_not_called()
        return json.loads(response.content)

    def test_disabled_and_corrupt_settings_use_standard_parser_without_transport(self):
        for raw in (None, "garbage", "[]", '{"url": 3}', '{"url":"http://x", "key":"secret"}'):
            if raw is not None:
                self.case.store.values["_INTERPRETER_CONFIG"] = raw
            result = self.interpret("Find a 10k resistor and a capacitor")
            self.assertEqual(result["interpreter"], "rules")
            self.assertEqual(len(result["requests"]), 2)
        self.session.post.assert_not_called()

    def test_prompt5_grouping_repairs_material_punctuation_and_retains_review_note(self):
        self.configure()
        self.upstream(["magnets", "batteries", "silicone, O-rings", "DC motors"])
        result = self.interpret("Find magnets, batteries, silicone, O-rings and DC motors.")
        self.assertEqual(result["interpreter"], "ollama")
        rows = result["requests"]
        self.assertEqual([row["query"] for row in rows], ["magnet", "battery", "silicone O-ring", "DC motor"])
        self.assertTrue(all(not row["needs_edit"] for row in rows), rows)
        self.assertIn("Check", rows[2]["notes"][0])

    def test_model_never_converts_numbers_or_assigns_catalogue_ids(self):
        self.configure()
        self.upstream(["a zero point one microfarad capacitor", "a 1MΩ resistor", "a 1mΩ resistor"])
        result = self.interpret("Find a zero point one microfarad capacitor and a 1MΩ resistor and a 1mΩ resistor.")
        self.assertEqual([row["query"] for row in result["requests"]], ["0.1uF capacitor", "1MΩ resistor", "1mΩ resistor"])
        args, kwargs = self.session.post.call_args
        self.assertEqual(args, ("http://ollama.invalid:11434/api/chat",))
        self.assertFalse(self.session.trust_env)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (3, 30))
        payload = kwargs["json"]
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], self.module.SCHEMA)
        self.assertEqual(payload["options"]["num_thread"], 2)

    def test_quantity_notes_and_unsupported_constraints_are_preserved(self):
        self.configure()
        sources = ["two silicone O-rings", "MOSFET with drain to source of around 40 volts"]
        self.upstream(sources)
        result = self.interpret("Find " + " and ".join(sources))
        self.assertEqual(result["interpreter"], "ollama")
        rows = result["requests"]
        self.assertIn("quantity: 2", rows[0]["notes"][0])
        self.assertIn("40V", rows[1]["query"])
        self.assertIn("around", rows[1]["query"])
        self.assertTrue(rows[1]["warnings"])

    def test_mishearing_is_never_silently_corrected(self):
        self.configure()
        self.upstream(["orderings", "DC motor"])
        result = self.interpret("Find orderings and a DC motor")
        self.assertTrue(result["requests"][0]["needs_edit"])
        self.assertIn("orderings", result["requests"][0]["query"])

    def test_invented_reordered_repeated_or_omitted_text_falls_back(self):
        self.configure()
        cases = [
            ("10k resistor", ["20k resistor"]),
            ("silicone O-rings", ["O-rings"]),
            ("MOSFET with at least 40 volts", ["MOSFET"]),
            ("motor without a gearbox", ["motor", "gearbox"]),
            ("1MΩ resistor", ["1mΩ resistor"]),
            ("resistor and capacitor", ["capacitor", "resistor"]),
            ("resistor", ["resistor", "resistor"]),
            ("Find orderings", ["O-rings"]),
            ("Find resistor and capacitor", ["resistor"]),
        ]
        for text, items in cases:
            with self.subTest(text=text, items=items):
                self.upstream(items)
                result = self.interpret(text)
                self.assertEqual(result["interpreter"], "rules")
                self.assertIn("changed or omitted", result["notice"])
                self.assertEqual(result["requests"], self.module.interpret_requests(text)["requests"])

    def test_unfamiliar_or_orphaned_attribute_requires_manual_review(self):
        self.configure()
        self.upstream(["MOSFET", "40 volts"])
        result = self.interpret("Find MOSFET and 40 volts")
        self.assertEqual(result["interpreter"], "ollama")
        self.assertTrue(result["requests"][1]["needs_edit"])

    def test_invalid_schema_is_rejected(self):
        for payload in (None, [], {}, {"items": []}, {"items": [None]}, {"items": [""]},
                        {"items": ["resistor"], "ids": [1]}, {"items": "resistor"},
                        {"items": ["resistor"] * 21}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.module.validate_extraction("resistor", payload)

    def test_model_failures_fall_back_without_exposing_upstream_bodies(self):
        self.configure()
        for kwargs in ({"status": 500}, {"chunks": [b"private upstream body"]},
                       {"chunks": [b"x" * 65537]}, {"result": {"done": False}},
                       {"result": {"done": True, "done_reason": "length", "message": {"content": '{}'}}},
                       {"result": {"done": True, "done_reason": "stop", "message": {"content": '[]'}}}):
            self.upstream(**kwargs)
            result = self.interpret("resistor")
            self.assertEqual(result["interpreter"], "rules")
            self.assertIn("notice", result)
            self.assertNotIn("private upstream", str(result))

    def test_timeout_and_connection_error_use_fallback(self):
        self.configure()
        for error, fragment in ((self.module.requests.Timeout("private URL"), "timed out"),
                                (self.module.requests.ConnectionError("private URL"), "Cannot reach")):
            self.session.post.side_effect = error
            result = self.interpret("resistor")
            self.assertIn(fragment, result["notice"])
            self.assertNotIn("private URL", result["notice"])

    def test_long_input_and_busy_slot_skip_model(self):
        self.configure()
        result = self.interpret("Find resistor " + "x" * 2000)
        self.assertIn("2,000", result["notice"])
        with self.module.interpretation_slot():
            result = self.interpret("resistor")
            self.assertIn("busy", result["notice"])
        self.session.post.assert_not_called()
        # Lock is released after an unsuccessful request too.
        self.upstream()
        self.assertEqual(self.interpret("resistor")["interpreter"], "ollama")

    def test_settings_are_independent_and_protected(self):
        request = self.case.finder_request(method="GET")
        result = self.views.interpreter_settings(request)
        self.assertEqual(result["Cache-Control"], "no-store")
        self.assertEqual(json.loads(result.content)["interpreter"]["url"], "")
        for payload in ({"url": "http://ollama.invalid:11434"}, {"url": ""}):
            result = self.views.interpreter_settings(self.case.finder_request(payload))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(json.loads(result.content)["interpreter"]["url"], payload["url"])
        self.assertNotIn("_SPEECH_CONFIG", self.case.store.values)
        self.assertIn("_WLED_CONTROLLERS", self.case.store.values)
        request.user.is_superuser = False
        self.assertEqual(self.views.interpreter_settings(request).status_code, 403)
        self.assertEqual(self.views.interpreter_settings(self.case.finder_request({}, csrf=False)).status_code, 403)
        for payload in ({"url": "file:///tmp/model"}, {"url": "http://user:secret@local"},
                        {"url": "http://local:invalid"}, {"url": "http://local", "model": ""},
                        {"url": "http://local", "language": "de"}):
            self.assertEqual(self.views.interpreter_settings(self.case.finder_request(payload)).status_code, 400)
        self.session.post.assert_not_called()

