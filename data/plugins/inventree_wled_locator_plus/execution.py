"""Execute a resolved locate plan without querying inventory objects."""

from __future__ import annotations


def apply_controller_leds(wled, controller_leds: dict) -> dict:
    """Clear the whole locator system once, then light the selected targets."""
    with wled.execution():
        clear_result = wled.clear_all_controllers()
        results = {"clear": clear_result, "set": {}}

        for controller, led_indices in controller_leds.items():
            results["set"][controller] = (
                wled.set_leds(led_indices, controller)
                if led_indices
                else {"success": True, "message": "No mapped LEDs to light"}
            )

        if len(results["set"]) == 1:
            set_result = next(iter(results["set"].values()))
            return {**set_result, "clear": clear_result}

        return {"controllers": results}
