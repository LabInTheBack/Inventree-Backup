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


def parse_indicator_metadata(location: StockLocation, wled) -> dict:
    """Read and validate controller-aware WLED metadata from a StockLocation."""
    indicator = location.get_metadata(METADATA_INDICATOR_KEY, backup_value=None)

    if isinstance(indicator, dict):
        controller_label = str(indicator.get("controller") or "").strip()
        led = indicator.get("led", None)

        if not controller_label:
            raise ValueError("StockLocation wled_indicator metadata needs a controller")

        try:
            led = int(led)
        except (TypeError, ValueError) as exc:
            raise ValueError("StockLocation wled_indicator led must be an integer") from exc

        return {
            "controller": wled.get_controller(controller_label)["label"],
            "led": wled.validate_led_index(led, controller_label),
        }

    raise ValueError("StockLocation has no wled_indicator metadata")


def inspect_mapping_metadata(location: StockLocation, controller_labels: set[str], validate_led) -> dict:
    """Return mapping metadata details without raising for invalid records."""
    metadata = location.metadata or {}
    controller = None
    led = None
    invalid = ""
    source = "none"

    indicator = metadata.get(METADATA_INDICATOR_KEY)

    if isinstance(indicator, dict):
        controller = str(indicator.get("controller") or "").strip()
        source = METADATA_INDICATOR_KEY

        try:
            led = int(indicator.get("led"))
        except (TypeError, ValueError):
            invalid = "wled_indicator LED is not an integer"

        if not invalid and not controller:
            invalid = "wled_indicator controller is missing"

        if not invalid and controller not in controller_labels:
            invalid = f"Controller '{controller}' is not configured"

        if not invalid:
            try:
                validate_led(led, controller)
            except ValueError as exc:
                invalid = str(exc)

    return {
        "controller": controller,
        "led": led,
        "source": source,
        "invalid": invalid,
    }
