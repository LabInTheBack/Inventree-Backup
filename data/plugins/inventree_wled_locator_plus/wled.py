"""Small WLED HTTP client helpers."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import DEFAULT_CONTROLLER_LABEL


logger = logging.getLogger("inventree.plugin.wled_locator_plus")
COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class WledRequestError(RuntimeError):
    """Raised when the WLED controller request fails."""


def normalize_hex_color(value: str) -> str:
    """Return a normalized six-character hex color."""
    color = str(value or "").strip().lstrip("#")

    if not COLOR_RE.match(color):
        raise ValueError("Color must be a six-character hex value")

    return color.upper()


def normalize_controller_label(value: str) -> str:
    """Return a stable WLED controller label."""
    label = str(value or "").strip()

    if not label or not LABEL_RE.match(label):
        raise ValueError("Controller label must use letters, numbers, hyphen, or underscore")

    return label


def normalize_led_count(value, *, label: str = "Controller", allow_auto: bool = True) -> int | None:
    """Return a positive LED count, or None for auto-detected counts."""
    if allow_auto and value in (None, "", "auto"):
        return None

    max_leds = int(value)
    if max_leds < 1:
        raise ValueError(f"{label} max_leds must be at least 1")

    return max_leds


def decode_json_body(response, default: dict) -> dict:
    """Decode a JSON HTTP response body."""
    body = response.read().decode("utf-8")
    return json.loads(body) if body else default


class WledClient:
    """HTTP client for the configured WLED controller."""

    def __init__(self, plugin):
        self.plugin = plugin
        self._configured_controllers_cache = None

    def normalize_base_url(self, address: str) -> str:
        """Return a normalized controller base URL."""
        address = str(address or "").strip()
        if not address:
            raise ValueError("WLED controller address must not be empty")

        if not address.startswith(("http://", "https://")):
            address = f"http://{address}"

        return address.rstrip("/")

    def get_configured_controllers(self) -> list[dict]:
        """Return configured WLED controllers before info discovery."""
        if self._configured_controllers_cache is not None:
            return [dict(controller) for controller in self._configured_controllers_cache]

        text = str(self.plugin.get_setting("WLED_CONTROLLERS", backup_value="") or "").strip()

        if not text:
            return []

        try:
            raw_controllers = json.loads(text)
        except ValueError as exc:
            raise ValueError("WLED_CONTROLLERS must be valid JSON") from exc

        if not isinstance(raw_controllers, list):
            raise ValueError("WLED_CONTROLLERS must be a JSON list")

        controllers = []
        labels = set()

        for raw in raw_controllers:
            controller = self.deserialize_controller(raw)
            label = controller["label"]

            if label in labels:
                raise ValueError(f"Duplicate WLED controller label: {label}")

            labels.add(label)
            controllers.append(controller)

        if not controllers:
            return []

        if not any(controller["primary"] for controller in controllers):
            controllers[0]["primary"] = True

        self._configured_controllers_cache = [dict(controller) for controller in controllers]
        return controllers

    def deserialize_controller(self, raw: dict) -> dict:
        """Return a normalized controller record from plugin settings JSON."""
        if not isinstance(raw, dict):
            raise ValueError("Each WLED controller must be an object")

        label = normalize_controller_label(raw.get("label", ""))

        return {
            "label": label,
            "address": self.normalize_base_url(raw.get("address", "")),
            "max_leds": normalize_led_count(
                raw.get("max_leds", None),
                label=f"Controller {label}",
            ),
            "marker_color": normalize_hex_color(raw.get("marker_color") or "FF0000"),
            "name": str(raw.get("name", "")).strip(),
            "version": str(raw.get("version", "")).strip(),
            "primary": bool(raw.get("primary", label == DEFAULT_CONTROLLER_LABEL)),
        }

    def serialize_controller(self, controller: dict) -> dict:
        """Return a controller record suitable for plugin settings."""
        item = {
            "label": normalize_controller_label(controller.get("label", "")),
            "address": self.normalize_base_url(controller.get("address", "")),
            "marker_color": normalize_hex_color(
                controller.get("marker_color") or "FF0000"
            ),
            "primary": bool(controller.get("primary")),
        }

        max_leds = normalize_led_count(controller.get("max_leds", None))
        if max_leds is not None:
            item["max_leds"] = max_leds

        name = str(controller.get("name", "")).strip()
        if name:
            item["name"] = name

        version = str(controller.get("version", "")).strip()
        if version:
            item["version"] = version

        return item

    def save_controllers(self, controllers: list[dict]) -> list[dict]:
        """Persist WLED controllers to the plugin settings JSON field."""
        serialized = []
        labels = set()

        for raw in controllers:
            item = self.serialize_controller(raw)
            if item["label"] in labels:
                raise ValueError(f"Duplicate WLED controller label: {item['label']}")
            labels.add(item["label"])
            serialized.append(item)

        if serialized and not any(item.get("primary") for item in serialized):
            serialized[0]["primary"] = True

        self.plugin.set_setting("WLED_CONTROLLERS", json.dumps(serialized, indent=2))
        self._configured_controllers_cache = [dict(controller) for controller in serialized]
        return serialized

    def upsert_controller(self, controller: dict) -> dict:
        """Create or update one WLED controller record."""
        item = self.serialize_controller(controller)
        controllers = self.get_configured_controllers()
        found = False

        if item.get("primary"):
            for existing in controllers:
                existing["primary"] = False

        for index, existing in enumerate(controllers):
            if existing["label"] == item["label"]:
                controllers[index] = {**existing, **item}
                found = True
                break

        if not found:
            controllers.append(item)

        self.save_controllers(controllers)
        return self.get_controller(item["label"])

    def delete_controller(self, label: str) -> list[dict]:
        """Remove one WLED controller record."""
        label = normalize_controller_label(label)
        controllers = [
            controller
            for controller in self.get_configured_controllers()
            if controller["label"] != label
        ]

        if len(controllers) == len(self.get_configured_controllers()):
            raise ValueError(f"WLED controller is not configured: {label}")

        return self.save_controllers(controllers)

    def get_controller(self, label: str | None = None) -> dict:
        """Return a configured controller by label, defaulting to the primary."""
        controllers = self.get_configured_controllers()

        if not controllers:
            raise ValueError("No WLED controllers are configured")

        if label in (None, ""):
            for controller in controllers:
                if controller.get("primary"):
                    return controller
            return controllers[0]

        for controller in controllers:
            if controller["label"] == label:
                return controller

        raise ValueError(f"WLED controller is not configured: {label}")

    def get_controllers(self, include_info: bool = False) -> list[dict]:
        """Return configured controllers, optionally enriched with WLED info."""
        controllers = []

        for controller in self.get_configured_controllers():
            item = dict(controller)
            if include_info:
                info = self.get_info(item["label"])
                led_count = info.get("leds", {}).get("count")
                if isinstance(led_count, int) and led_count > 0:
                    item["max_leds"] = led_count
                    item["max_leds_source"] = "wled_info"
                else:
                    item["max_leds_source"] = "setting"
                item["info"] = info
            elif item.get("max_leds"):
                item["max_leds_source"] = "setting"
            else:
                item["max_leds_source"] = "wled_info"

            controllers.append(item)

        return controllers

    def get_max_leds(self) -> int:
        """Return configured LED count."""
        return self.get_controller_max_leds()

    def get_controller_max_leds(self, label: str | None = None) -> int:
        """Return LED count for a controller.

        Normal locate/test/register paths must not depend on repeated live WLED
        info requests. Prefer the saved controller record, and only fall back to
        WLED /json/info when no manual or synced LED count has been stored yet.
        """
        controller = self.get_controller(label)

        if controller.get("max_leds"):
            return int(controller["max_leds"])

        try:
            info = self.get_info(controller["label"])
            led_count = info.get("leds", {}).get("count")
            if isinstance(led_count, int) and led_count > 0:
                return led_count
        except WledRequestError as exc:
            raise ValueError(
                f"Controller {controller['label']} has no saved LED count and "
                f"WLED auto-detection failed: {exc}"
            ) from exc

        raise ValueError(f"Controller {controller['label']} has no saved or detectable LED count")

    def get_timeout(self) -> int:
        """Return configured HTTP timeout."""
        timeout = int(self.plugin.get_setting("REQUEST_TIMEOUT", backup_value=3))

        if timeout < 1:
            raise ValueError("REQUEST_TIMEOUT must be at least 1")

        return timeout

    def validate_led_index(self, led_index: int, controller_label: str | None = None) -> int:
        """Validate and return an LED index."""
        if not isinstance(led_index, int):
            raise ValueError("LED index must be an integer")

        max_leds = self.get_controller_max_leds(controller_label)

        if led_index < 0 or led_index >= max_leds:
            raise ValueError(f"LED index must be between 0 and {max_leds - 1}")

        return led_index

    def request_json(self, controller_label: str | None, path: str, payload: dict | None = None, method: str = "GET") -> dict:
        """Send a JSON request to a WLED controller."""
        controller = self.get_controller(controller_label)
        url = f"{controller['address']}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        try:
            with urlopen(request, timeout=self.get_timeout()) as response:
                result = decode_json_body(response, {"ok": True})
                self.record_last_request(
                    {
                        "success": True,
                        "controller": controller["label"],
                        "url": url,
                        "status": getattr(response, "status", None),
                        "response": result,
                    }
                )
                return result
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.exception("WLED request failed for controller %s: %s", controller["label"], exc)
            self.record_last_request(
                {
                    "success": False,
                    "controller": controller["label"],
                    "url": url,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
            raise WledRequestError(
                f"WLED request failed for controller {controller['label']} ({exc.__class__.__name__}): {exc}"
            ) from exc

    def get_info(self, controller_label: str | None = None) -> dict:
        """Return WLED /json/info for a controller."""
        return self.request_json(controller_label, "/json/info")

    def get_info_for_address(self, address: str) -> dict:
        """Return WLED /json/info for an address before it is saved."""
        url = f"{self.normalize_base_url(address)}/json/info"
        request = Request(url, headers={"Content-Type": "application/json"}, method="GET")

        try:
            with urlopen(request, timeout=self.get_timeout()) as response:
                result = decode_json_body(response, {})
                self.record_last_request({
                    "success": True,
                    "controller": None,
                    "url": url,
                    "status": getattr(response, "status", None),
                    "response": result,
                })
                return result
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.exception("WLED info sync failed for address %s: %s", address, exc)
            self.record_last_request({
                "success": False,
                "controller": None,
                "url": url,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            })
            raise WledRequestError(f"WLED info sync failed ({exc.__class__.__name__}): {exc}") from exc

    def post_state(self, payload: dict, controller_label: str | None = None) -> dict:
        """POST a JSON state payload to WLED."""
        return self.request_json(controller_label, "/json/state", payload=payload, method="POST")

    def record_last_request(self, result: dict) -> None:
        """Store request diagnostics on the plugin instance without a database schema."""
        self.plugin._wled_locator_last_request = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    def get_last_request(self) -> dict | None:
        """Return the last WLED request result for diagnostics."""
        return getattr(self.plugin, "_wled_locator_last_request", None)

    def clear_leds(self, controller_label: str | None = None) -> dict:
        """Clear the configured LED range."""
        max_leds = self.get_controller_max_leds(controller_label)
        color = normalize_hex_color(
            self.plugin.get_setting("CLEAR_COLOR", backup_value="000000")
        )
        return self.post_state({"seg": {"i": [0, max_leds, color]}}, controller_label=controller_label)

    def clear_all_controllers(self) -> dict:
        """Clear every configured WLED controller."""
        results = {}

        for controller in self.get_controllers(include_info=False):
            label = controller["label"]
            results[label] = self.clear_leds(label)

        if len(results) == 1:
            return next(iter(results.values()))

        return {"controllers": results}

    def set_led(self, led_index: int, controller_label: str | None = None) -> dict:
        """Light a single LED with the marker color."""
        led_index = self.validate_led_index(led_index, controller_label)
        color = self.get_controller(controller_label).get("marker_color") or "FF0000"
        return self.post_state({"seg": {"i": [led_index, color]}}, controller_label=controller_label)

    def set_leds(self, led_indices: list[int], controller_label: str | None = None) -> dict:
        """Light multiple LEDs in one WLED request."""
        color = self.get_controller(controller_label).get("marker_color") or "FF0000"
        led_data = []

        for led_index in led_indices:
            led_data.extend([self.validate_led_index(led_index, controller_label), color])

        return self.post_state({"seg": {"i": led_data}}, controller_label=controller_label)

    def off(self) -> dict:
        """Turn off all configured LEDs."""
        return self.clear_all_controllers()
