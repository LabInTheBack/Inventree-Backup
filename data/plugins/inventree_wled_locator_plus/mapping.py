"""StockLocation metadata helpers for WLED mappings."""

from __future__ import annotations

from stock.models import StockLocation

from .constants import METADATA_INDICATOR_KEY


def location_path(location: StockLocation) -> str:
    """Return the stable display path for a StockLocation."""
    return getattr(location, "pathstring", "") or str(location)


def location_info(location: StockLocation) -> dict:
    """Return JSON-safe StockLocation information."""
    return {
        "id": location.pk,
        "name": location.name,
        "path": location_path(location),
    }


def set_metadata_values(location: StockLocation, values: dict) -> None:
    """Set StockLocation metadata values without deleting unrelated metadata."""
    metadata = dict(location.metadata or {})
    metadata.update(values)
    location.metadata = metadata
    location.save()


def delete_metadata_keys(location: StockLocation, keys: list[str]) -> None:
    """Delete StockLocation metadata keys without touching unrelated metadata."""
    metadata = dict(location.metadata or {})
    changed = False

    for key in keys:
        if key in metadata:
            del metadata[key]
            changed = True

    if changed:
        location.metadata = metadata
        location.save()


def normalize_led_values(raw_value) -> list[int]:
    """Return unique integer LED indexes from stored metadata."""
    if isinstance(raw_value, list):
        values = raw_value
    elif raw_value in (None, ""):
        values = []
    else:
        values = [raw_value]

    leds = []
    for value in values:
        try:
            led = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("StockLocation wled_indicator LED values must be integers") from exc

        if led not in leds:
            leds.append(led)

    return leds


def indicator_payload(controller: str, leds: list[int]) -> dict:
    """Return the canonical metadata payload for one controller and one or more LEDs."""
    if not leds:
        raise ValueError("StockLocation wled_indicator needs at least one LED")

    return {
        "controller": controller,
        "led": leds[0],
        "leds": leds,
    }


def parse_indicator_metadata(location: StockLocation, wled) -> dict:
    """Read and validate controller-aware WLED metadata from a StockLocation."""
    indicator = location.get_metadata(METADATA_INDICATOR_KEY, backup_value=None)

    if isinstance(indicator, dict):
        controller_label = str(indicator.get("controller") or "").strip()
        raw_leds = indicator.get("leds", indicator.get("led", None))

        if not controller_label:
            raise ValueError("StockLocation wled_indicator metadata needs a controller")

        leds = normalize_led_values(raw_leds)
        if not leds:
            raise ValueError("StockLocation wled_indicator needs at least one LED")

        controller = wled.get_controller(controller_label)["label"]
        validated_leds = [
            wled.validate_led_index(led, controller)
            for led in leds
        ]

        return {
            "controller": controller,
            "led": validated_leds[0],
            "leds": validated_leds,
            "indicators": [
                {"controller": controller, "led": led}
                for led in validated_leds
            ],
        }

    raise ValueError("StockLocation has no wled_indicator metadata")


def inspect_mapping_metadata(location: StockLocation, controller_labels: set[str], validate_led) -> dict:
    """Return mapping metadata details without raising for invalid records."""
    metadata = location.metadata or {}
    controller = None
    led = None
    leds = []
    invalid = ""
    source = "none"

    indicator = metadata.get(METADATA_INDICATOR_KEY)

    if isinstance(indicator, dict):
        controller = str(indicator.get("controller") or "").strip()
        source = METADATA_INDICATOR_KEY

        try:
            leds = normalize_led_values(indicator.get("leds", indicator.get("led")))
        except (TypeError, ValueError):
            invalid = "wled_indicator LED values must be integers"

        if not invalid and not leds:
            invalid = "wled_indicator needs at least one LED"

        if not invalid and not controller:
            invalid = "wled_indicator controller is missing"

        if not invalid and controller not in controller_labels:
            invalid = f"Controller '{controller}' is not configured"

        if not invalid:
            validated_leds = []
            for item in leds:
                try:
                    validated_leds.append(validate_led(item, controller))
                except ValueError as exc:
                    invalid = str(exc)
                    break
            leds = validated_leds if not invalid else leds

        led = leds[0] if leds else None

    return {
        "controller": controller,
        "led": led,
        "leds": leds,
        "indicators": [
            {"controller": controller, "led": item}
            for item in leds
            if controller
        ],
        "source": source,
        "invalid": invalid,
    }
