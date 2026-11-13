"""Ordered, controller-aware LED collection, independent of InvenTree and HTTP."""

from __future__ import annotations


class IndicatorCollection:
    """Collect unique targets without changing existing JSON response fields."""

    def __init__(self):
        self.controller_leds = {}
        self.indicators = []
        self._seen = set()

    def extend(self, indicators):
        for indicator in indicators:
            controller, led = indicator["controller"], indicator["led"]
            key = (controller, led)
            if key in self._seen:
                continue
            self._seen.add(key)
            self.controller_leds.setdefault(controller, []).append(led)
            self.indicators.append({"controller": controller, "led": led})

    @property
    def leds(self):
        """Preserve the existing plain-LED field and its first-seen order."""
        return list(dict.fromkeys(item["led"] for item in self.indicators))
