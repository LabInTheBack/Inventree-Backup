"""InvenTree object lookup and LED locating logic."""

from __future__ import annotations

import logging

from build.models import Build, BuildItem
from part.models import Part
from stock.models import StockItem, StockLocation

from .constants import METADATA_INDICATOR_KEY
from .mapping import (
    delete_metadata_keys,
    indicator_payload,
    location_info,
    normalize_led_values,
    parse_indicator_metadata,
    set_metadata_values,
)
from .wled import WledClient


logger = logging.getLogger("inventree.plugin.wled_locator_plus")


class LocatorService:
    """Resolve InvenTree objects to WLED LED indexes."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.wled = WledClient(plugin)

    def get_location_info(self, location: StockLocation) -> dict:
        """Return simple JSON-safe location information."""
        return location_info(location)

    def get_stock_item_info(self, item: StockItem) -> dict:
        """Return simple JSON-safe stock item information."""
        location = item.location

        return {
            "id": item.pk,
            "part": str(item.part),
            "quantity": self.format_quantity(item.quantity),
            "in_stock": item.in_stock,
            "location": self.get_location_info(location) if location else None,
        }

    def format_quantity(self, quantity) -> str:
        """Return a human-readable quantity without unnecessary decimal zeroes."""
        text = str(quantity)

        if "." not in text:
            return text

        return text.rstrip("0").rstrip(".")

    def get_part_info(self, part: Part) -> dict:
        """Return simple JSON-safe part information."""
        return {
            "id": part.pk,
            "name": part.name,
            "full_name": part.full_name,
        }

    def get_build_info(self, build: Build) -> dict:
        """Return simple JSON-safe build information."""
        return {
            "id": build.pk,
            "reference": build.reference,
            "title": build.title,
            "part": self.get_part_info(build.part) if build.part else None,
        }

    def get_build_allocation_info(self, allocation: BuildItem) -> dict:
        """Return simple JSON-safe BuildItem allocation information."""
        item = allocation.stock_item

        return {
            "id": allocation.pk,
            "quantity": self.format_quantity(allocation.quantity),
            "stock_item": self.get_stock_item_info(item) if item else None,
            "build_line": allocation.build_line_id,
        }

    def set_location_led(self, location: StockLocation, led: int) -> int:
        """Store the WLED LED index on a StockLocation."""
        indicator = self.set_location_indicator(location, led, controller_label=None)
        return indicator["led"]

    def set_location_indicator(self, location: StockLocation, led: int, controller_label: str | None = None) -> dict:
        """Store a WLED controller and LED index on a StockLocation."""
        return self.set_location_indicators(location, [led], controller_label)

    def set_location_indicators(
        self,
        location: StockLocation,
        leds: list[int],
        controller_label: str | None = None,
    ) -> dict:
        """Store a WLED controller and one or more LED indexes on a StockLocation."""
        if location.has_children:
            raise ValueError("Parent StockLocations cannot be assigned a direct LED")

        controller = self.wled.get_controller(controller_label)
        validated_leds = []
        for led in normalize_led_values(leds):
            validated = self.wled.validate_led_index(led, controller["label"])
            if validated not in validated_leds:
                validated_leds.append(validated)

        if not validated_leds:
            raise ValueError("At least one LED is required")

        self.set_metadata_values(
            location,
            {METADATA_INDICATOR_KEY: indicator_payload(controller["label"], validated_leds)},
        )

        return {
            "controller": controller["label"],
            "led": validated_leds[0],
            "leds": validated_leds,
            "indicators": [
                {"controller": controller["label"], "led": led}
                for led in validated_leds
            ],
        }

    def clear_location_indicator(self, location: StockLocation) -> dict:
        """Remove WLED mapping metadata from a StockLocation."""
        if location.has_children:
            raise ValueError("Parent StockLocations do not have direct LED assignments")

        removed = []
        metadata = dict(location.metadata or {})

        if METADATA_INDICATOR_KEY in metadata:
            removed.append(METADATA_INDICATOR_KEY)

        self.delete_metadata_keys(location, removed)

        return {
            "location": self.get_location_info(location),
            "removed_keys": removed,
            "summary": {"removed": len(removed)},
        }

    def set_metadata_values(self, location: StockLocation, values: dict) -> None:
        """Set StockLocation metadata values without deleting unrelated metadata."""
        set_metadata_values(location, values)

    def delete_metadata_keys(self, location: StockLocation, keys: list[str]) -> None:
        """Delete StockLocation metadata keys without touching unrelated metadata."""
        delete_metadata_keys(location, keys)

    def get_location_led(self, location: StockLocation) -> int:
        """Read and validate the WLED LED index from StockLocation metadata."""
        return self.get_location_indicator(location)["led"]

    def get_location_indicator(self, location: StockLocation) -> dict:
        """Read and validate the WLED controller/LED mapping from metadata."""
        return parse_indicator_metadata(location, self.wled)

    def add_indicator(self, controller_leds: dict, indicators: list[dict], indicator: dict) -> None:
        """Add an indicator to grouped locate structures once."""
        controller = indicator["controller"]
        led = indicator["led"]
        controller_leds.setdefault(controller, [])

        if led not in controller_leds[controller]:
            controller_leds[controller].append(led)

        if not any(item["controller"] == controller and item["led"] == led for item in indicators):
            indicators.append({"controller": controller, "led": led})

    def add_indicators(self, controller_leds: dict, indicators: list[dict], new_indicators: list[dict]) -> None:
        """Add multiple indicators to grouped locate structures."""
        for indicator in new_indicators:
            self.add_indicator(controller_leds, indicators, indicator)

    def compatibility_leds(self, indicators: list[dict]) -> list[int]:
        """Return plain LED indexes for older response fields."""
        leds = []

        for indicator in indicators:
            led = indicator["led"]
            if led not in leds:
                leds.append(led)

        return leds

    def apply_controller_leds(self, controller_leds: dict) -> dict:
        """Clear all WLEDs, then light LEDs grouped by WLED controller."""
        clear_result = self.wled.clear_all_controllers()
        results = {"clear": clear_result, "set": {}}

        for controller, led_indices in controller_leds.items():
            results["set"][controller] = (
                self.wled.set_leds(led_indices, controller)
                if led_indices
                else {"success": True, "message": "No mapped LEDs to light"}
            )

        if len(results["set"]) == 1:
            set_result = next(iter(results["set"].values()))
            return {**set_result, "clear": clear_result}

        return {"controllers": results}

    def get_location_led_plan(self, location: StockLocation) -> dict:
        """Return LEDs used to locate a StockLocation.

        Leaf locations use their own metadata. Parent locations use mapped
        descendants, because the parent is only a container.
        """
        if not location.has_children:
            indicator = self.get_location_indicator(location)
            controller_leds = {}
            indicators = []
            self.add_indicators(controller_leds, indicators, indicator["indicators"])
            return {
                "location": self.get_location_info(location),
                "mode": "leaf",
                "controller": indicator["controller"],
                "led": indicator["led"],
                "leds": indicator["leds"],
                "indicators": indicators,
                "controller_leds": controller_leds,
                "lit": [{
                    "location": self.get_location_info(location),
                    "controller": indicator["controller"],
                    "led": indicator["led"],
                    "leds": indicator["leds"],
                    "indicators": indicator["indicators"],
                    "indicator": indicator,
                }],
                "skipped": [],
            }

        lit = []
        skipped = []
        indicators = []
        controller_leds = {}

        descendants = location.get_descendants(include_self=False).order_by(
            "pathstring",
            "name",
        )

        for child in descendants:
            if child.has_children:
                continue

            try:
                indicator = self.get_location_indicator(child)
            except ValueError as exc:
                skipped.append({
                    "location": self.get_location_info(child),
                    "reason": str(exc),
                })
                continue

            self.add_indicators(controller_leds, indicators, indicator["indicators"])

            lit.append({
                "location": self.get_location_info(child),
                "controller": indicator["controller"],
                "led": indicator["led"],
                "leds": indicator["leds"],
                "indicators": indicator["indicators"],
                "indicator": indicator,
            })

        if not indicators:
            raise ValueError("Parent StockLocation has no mapped child LEDs")

        return {
            "location": self.get_location_info(location),
            "mode": "parent",
            "controller": None,
            "led": None,
            "leds": self.compatibility_leds(indicators),
            "indicators": indicators,
            "controller_leds": controller_leds,
            "lit": lit,
            "skipped": skipped,
        }

    def locate_location(self, location: StockLocation) -> dict:
        """Clear WLED LEDs and light mapped LEDs for a StockLocation."""
        try:
            plan = self.get_location_led_plan(location)
        except ValueError:
            self.wled.clear_all_controllers()
            raise

        result = self.apply_controller_leds(plan["controller_leds"])

        return {
            **plan,
            "wled": result,
        }

    def locate_stock_location(self, location_pk):
        """Locate a StockLocation through InvenTree's LocateMixin."""
        logger.info("Locating StockLocation pk=%s with WLED Locator Plus", location_pk)

        try:
            location = StockLocation.objects.get(pk=location_pk)
        except StockLocation.DoesNotExist:
            logger.warning("StockLocation pk=%s not found", location_pk)
            return None

        try:
            result = self.locate_location(location)
        except Exception as exc:
            logger.exception("Failed to locate StockLocation pk=%s: %s", location_pk, exc)
            return None

        logger.info("Located StockLocation pk=%s using WLED LEDs %s", location_pk, result["leds"])
        return result

    def locate_stock_item_object(self, item: StockItem) -> dict:
        """Locate a StockItem by locating its assigned StockLocation."""
        preview = self.preview_stock_item_object(item)
        if not preview["can_locate"]:
            self.wled.clear_all_controllers()
            raise ValueError(preview["reason"])

        result = self.locate_location(item.location)

        return {
            "item": preview["item"],
            "location": result["location"],
            "controller": result["controller"],
            "led": result["led"],
            "leds": result["leds"],
            "indicators": result["indicators"],
            "controller_leds": result["controller_leds"],
            "lit": result["lit"],
            "skipped": result["skipped"],
            "wled": result["wled"],
        }

    def preview_stock_item_object(self, item: StockItem) -> dict:
        """Return the StockLocation and LED used to locate a StockItem."""
        item_info = self.get_stock_item_info(item)

        if not item.in_stock:
            return self.stock_item_preview_failure(
                item_info,
                item_info["location"],
                "StockItem is not currently in stock",
            )

        if item.location is None:
            return self.stock_item_preview_failure(
                item_info,
                None,
                "StockItem has no assigned StockLocation",
            )

        try:
            plan = self.get_location_led_plan(item.location)
        except ValueError as exc:
            return self.stock_item_preview_failure(
                item_info,
                item_info["location"],
                str(exc),
            )

        return {
            "item": item_info,
            "location": item_info["location"],
            "controller": plan["controller"],
            "led": plan["led"],
            "leds": plan["leds"],
            "indicators": plan["indicators"],
            "controller_leds": plan["controller_leds"],
            "lit": plan["lit"],
            "skipped": plan["skipped"],
            "can_locate": True,
            "reason": "",
        }

    def stock_item_preview_failure(self, item_info: dict, location: dict | None, reason: str) -> dict:
        """Return a consistent StockItem preview failure payload."""
        return {
            "item": item_info,
            "location": location,
            "controller": None,
            "led": None,
            "leds": [],
            "indicators": [],
            "controller_leds": {},
            "lit": [],
            "skipped": [],
            "can_locate": False,
            "reason": reason,
        }

    def locate_stock_item(self, item_pk):
        """Locate a StockItem through InvenTree's LocateMixin."""
        logger.info("Locating StockItem pk=%s with WLED Locator Plus", item_pk)

        try:
            item = StockItem.objects.select_related("part", "location").get(pk=item_pk)
        except StockItem.DoesNotExist:
            logger.warning("StockItem pk=%s not found", item_pk)
            return None

        try:
            result = self.locate_stock_item_object(item)
        except Exception as exc:
            logger.exception("Failed to locate StockItem pk=%s: %s", item_pk, exc)
            return None

        logger.info("Located StockItem pk=%s using WLED LEDs %s", item_pk, result["leds"])
        return result

    def locate_part_object(self, part: Part) -> dict:
        """Locate a Part by lighting LEDs for its available StockItems."""
        plan = self.preview_part_object(part)
        wled_result = self.apply_controller_leds(plan["controller_leds"])

        return {
            **plan,
            "wled": wled_result,
        }

    def preview_part_object(self, part: Part) -> dict:
        """Return the StockItems, StockLocations, and LEDs used to locate a Part."""
        stock_items = StockItem.objects.select_related("part", "location").filter(
            part=part,
            location__isnull=False,
        ).order_by("pk")
        lit = []
        skipped = []
        indicators = []
        controller_leds = {}
        location_groups = {}
        stock_item_count = 0

        for item in stock_items:
            stock_item_count += 1
            item_info = self.get_stock_item_info(item)

            if not item.in_stock:
                skipped.append({
                    "item": item_info,
                    "reason": "StockItem is not currently in stock",
                })
                continue

            try:
                plan = self.get_location_led_plan(item.location)
            except ValueError as exc:
                skipped.append({"item": item_info, "reason": str(exc)})
                continue

            for indicator in plan["indicators"]:
                self.add_indicator(controller_leds, indicators, indicator)

            location_id = item.location.pk
            location_info = self.get_location_info(item.location)
            location_group = location_groups.setdefault(
                location_id,
                {
                    "location": location_info,
                    "controller": plan["controller"],
                    "led": plan["led"],
                    "leds": [],
                    "indicators": [],
                    "controller_leds": {},
                    "lit": plan["lit"],
                    "items": [],
                    "item_count": 0,
                },
            )

            for indicator in plan["indicators"]:
                self.add_indicator(
                    location_group["controller_leds"],
                    location_group["indicators"],
                    indicator,
                )

            location_group["leds"] = self.compatibility_leds(location_group["indicators"])

            location_group["items"].append(item_info)
            location_group["item_count"] += 1

            lit.append({
                "item": item_info,
                "location": location_info,
                "controller": plan["controller"],
                "led": plan["led"],
                "leds": plan["leds"],
                "indicators": plan["indicators"],
                "lit": plan["lit"],
            })

        return {
            "part": self.get_part_info(part),
            "lit": lit,
            "locations": list(location_groups.values()),
            "leds": self.compatibility_leds(indicators),
            "indicators": indicators,
            "controller_leds": controller_leds,
            "skipped": skipped,
            "summary": {
                "stock_items": stock_item_count,
                "lit_items": len(lit),
                "skipped_items": len(skipped),
                "unique_locations": len(location_groups),
                "unique_leds": len(indicators),
            },
        }

    def locate_build_object(self, build: Build) -> dict:
        """Locate a Build Order by lighting LEDs for its allocated StockItems."""
        plan = self.preview_build_object(build)
        wled_result = self.apply_controller_leds(plan["controller_leds"])

        return {
            **plan,
            "wled": wled_result,
        }

    def preview_build_object(self, build: Build) -> dict:
        """Return allocated StockItems, StockLocations, and LEDs used to locate a Build."""
        allocations = BuildItem.objects.select_related(
            "build_line",
            "build_line__build",
            "stock_item",
            "stock_item__part",
            "stock_item__location",
        ).filter(build_line__build=build).order_by("pk")

        lit = []
        skipped = []
        indicators = []
        controller_leds = {}
        location_groups = {}
        allocation_total = 0

        for allocation in allocations:
            allocation_total += 1
            item = allocation.stock_item
            allocation_info = self.get_build_allocation_info(allocation)

            if not item:
                skipped.append({
                    "allocation": allocation_info,
                    "reason": "Build allocation has no StockItem",
                })
                continue

            item_info = self.get_stock_item_info(item)

            if item.location is None:
                skipped.append({
                    "allocation": allocation_info,
                    "reason": "Allocated StockItem has no assigned StockLocation",
                })
                continue

            try:
                plan = self.get_location_led_plan(item.location)
            except ValueError as exc:
                skipped.append({
                    "allocation": allocation_info,
                    "reason": str(exc),
                })
                continue

            for indicator in plan["indicators"]:
                self.add_indicator(controller_leds, indicators, indicator)

            location_id = item.location.pk
            location_info = self.get_location_info(item.location)
            location_group = location_groups.setdefault(
                location_id,
                {
                    "location": location_info,
                    "controller": plan["controller"],
                    "led": plan["led"],
                    "leds": [],
                    "indicators": [],
                    "controller_leds": {},
                    "lit": plan["lit"],
                    "items": [],
                    "allocations": [],
                    "item_count": 0,
                    "allocation_count": 0,
                },
            )

            for indicator in plan["indicators"]:
                self.add_indicator(
                    location_group["controller_leds"],
                    location_group["indicators"],
                    indicator,
                )

            location_group["leds"] = self.compatibility_leds(location_group["indicators"])

            location_group["items"].append(item_info)
            location_group["allocations"].append(allocation_info)
            location_group["item_count"] += 1
            location_group["allocation_count"] += 1

            lit.append({
                "allocation": allocation_info,
                "item": item_info,
                "location": location_info,
                "controller": plan["controller"],
                "led": plan["led"],
                "leds": plan["leds"],
                "indicators": plan["indicators"],
                "lit": plan["lit"],
            })

        return {
            "build": self.get_build_info(build),
            "lit": lit,
            "locations": list(location_groups.values()),
            "leds": self.compatibility_leds(indicators),
            "indicators": indicators,
            "controller_leds": controller_leds,
            "skipped": skipped,
            "summary": {
                "allocations": allocation_total,
                "lit_allocations": len(lit),
                "skipped_allocations": len(skipped),
                "unique_locations": len(location_groups),
                "unique_leds": len(indicators),
            },
        }

    def parse_location_ids(self, ids_text: str) -> list[int]:
        """Parse a comma-separated list of StockLocation IDs."""
        if not ids_text:
            raise ValueError("Query parameter 'ids' is required")

        location_ids = []

        for item in ids_text.split(","):
            item = item.strip()
            if not item:
                continue

            try:
                location_id = int(item)
            except ValueError as exc:
                raise ValueError(f"Invalid StockLocation ID: {item}") from exc

            if location_id not in location_ids:
                location_ids.append(location_id)

        if not location_ids:
            raise ValueError("At least one StockLocation ID is required")

        return location_ids

    def locate_locations(self, location_ids: list[int]) -> dict:
        """Locate multiple StockLocations in one WLED request."""
        locations = {
            location.pk: location
            for location in StockLocation.objects.filter(pk__in=location_ids)
        }
        lit = []
        skipped = []
        indicators = []
        controller_leds = {}

        for location_id in location_ids:
            location = locations.get(location_id)

            if not location:
                skipped.append({"id": location_id, "reason": "Location not found"})
                continue

            try:
                plan = self.get_location_led_plan(location)
            except ValueError as exc:
                skipped.append({"location": self.get_location_info(location), "reason": str(exc)})
                continue

            for indicator in plan["indicators"]:
                self.add_indicator(controller_leds, indicators, indicator)

            lit.append({
                "location": self.get_location_info(location),
                "controller": plan["controller"],
                "led": plan["led"],
                "leds": plan["leds"],
                "indicators": plan["indicators"],
                "lit": plan["lit"],
            })

        wled_result = self.apply_controller_leds(controller_leds)

        return {
            "requested_ids": location_ids,
            "lit": lit,
            "leds": self.compatibility_leds(indicators),
            "indicators": indicators,
            "controller_leds": controller_leds,
            "skipped": skipped,
            "wled": wled_result,
        }

    def get_mapped_locations(self) -> list[dict]:
        """Return StockLocations with WLED metadata for the plugin page."""
        mapped_locations = []

        for location in StockLocation.objects.order_by("pathstring", "name"):
            try:
                indicator = self.get_location_indicator(location)
            except ValueError:
                indicator = None

            if not indicator:
                continue

            mapped_locations.append({
                "location": self.get_location_info(location),
                "controller": indicator["controller"],
                "led": indicator["led"],
                "leds": indicator["leds"],
                "indicators": indicator["indicators"],
                "indicator": indicator,
                "has_children": location.has_children,
                "child_count": location.get_descendant_count() if location.has_children else 0,
            })

        return mapped_locations

    def get_mapping_summary(self) -> dict:
        """Return raw WLED mapping counts for Plugin Configuration cleanup tools."""
        controller_counts = {}
        invalid = []
        mapped = []

        for location in StockLocation.objects.order_by("pathstring", "name"):
            metadata = location.metadata or {}
            indicator = metadata.get(METADATA_INDICATOR_KEY)

            if isinstance(indicator, dict):
                controller = str(indicator.get("controller") or "").strip()

                try:
                    indicator_leds = normalize_led_values(
                        indicator.get("leds", indicator.get("led", None))
                    )
                except (TypeError, ValueError):
                    invalid.append({
                        "location": self.get_location_info(location),
                        "reason": "wled_indicator LED values must be integers",
                    })
                    continue

                if not indicator_leds:
                    invalid.append({
                        "location": self.get_location_info(location),
                        "reason": "wled_indicator needs at least one LED",
                    })
                    continue

                if not controller:
                    invalid.append({
                        "location": self.get_location_info(location),
                        "reason": "wled_indicator controller is missing",
                    })
                    continue

                controller_counts[controller] = controller_counts.get(controller, 0) + 1
                mapped.append({
                    "location": self.get_location_info(location),
                    "controller": controller,
                    "led": indicator_leds[0],
                    "leds": indicator_leds,
                    "indicators": [
                        {"controller": controller, "led": led}
                        for led in indicator_leds
                    ],
                })
                continue

        return {
            "controller_counts": controller_counts,
            "mapped": mapped,
            "invalid": invalid,
            "summary": {
                "controller_mappings": len(mapped),
                "mapped_leds": sum(len(item.get("leds") or []) for item in mapped),
                "invalid": len(invalid),
            },
        }

    def reassign_location_mappings(self, source_controller: str, target_controller: str) -> dict:
        """Move existing mapping metadata to another controller while preserving LED indexes."""
        source_controller = str(source_controller or "").strip()
        target = self.wled.get_controller(target_controller)
        moved = []
        skipped = []

        if not source_controller:
            raise ValueError("Source controller is required")

        for location in StockLocation.objects.order_by("pathstring", "name"):
            if location.has_children:
                continue

            metadata = location.metadata or {}
            indicator = metadata.get(METADATA_INDICATOR_KEY)
            leds = []

            if isinstance(indicator, dict) and indicator.get("controller") == source_controller:
                leds = indicator.get("leds", indicator.get("led"))
            else:
                continue

            try:
                leds = normalize_led_values(leds)
                validated_leds = [
                    self.wled.validate_led_index(led, target["label"])
                    for led in leds
                ]
                if not validated_leds:
                    raise ValueError("wled_indicator needs at least one LED")
            except (TypeError, ValueError) as exc:
                skipped.append({
                    "location": self.get_location_info(location),
                    "reason": str(exc),
                })
                continue

            self.set_metadata_values(
                location,
                {METADATA_INDICATOR_KEY: indicator_payload(target["label"], validated_leds)},
            )
            moved.append({
                "location": self.get_location_info(location),
                "controller": target["label"],
                "led": validated_leds[0],
                "leds": validated_leds,
                "indicators": [
                    {"controller": target["label"], "led": led}
                    for led in validated_leds
                ],
            })

        return {
            "source_controller": source_controller,
            "target_controller": target["label"],
            "moved": moved,
            "skipped": skipped,
            "summary": {
                "moved": len(moved),
                "skipped": len(skipped),
            },
        }

    def clear_location_mappings(
        self,
        source_controller: str = "all",
    ) -> dict:
        """Clear WLED mapping metadata."""
        source_controller = str(source_controller or "all").strip()
        cleared = []

        for location in StockLocation.objects.order_by("pathstring", "name"):
            metadata = location.metadata or {}
            indicator = metadata.get(METADATA_INDICATOR_KEY)
            keys = []

            if source_controller == "all":
                if isinstance(indicator, dict):
                    keys.append(METADATA_INDICATOR_KEY)
            elif isinstance(indicator, dict) and indicator.get("controller") == source_controller:
                keys.append(METADATA_INDICATOR_KEY)

            if not keys:
                continue

            self.delete_metadata_keys(location, keys)
            cleared.append({
                "location": self.get_location_info(location),
                "cleared_keys": keys,
            })

        return {
            "source_controller": source_controller,
            "cleared": cleared,
            "summary": {"cleared": len(cleared)},
        }

    def get_location_choices(self) -> list[dict]:
        """Return StockLocations for page select inputs."""
        choices = []

        for location in StockLocation.objects.order_by("pathstring", "name"):
            info = self.get_location_info(location)
            try:
                indicator = self.get_location_indicator(location)
            except ValueError:
                indicator = None

            choices.append({
                "id": info["id"],
                "path": info["path"],
                "controller": indicator["controller"] if indicator else None,
                "led": indicator["led"] if indicator else None,
                "leds": indicator["leds"] if indicator else [],
                "indicators": indicator["indicators"] if indicator else [],
                "indicator": indicator,
                "has_children": location.has_children,
                "child_count": location.get_descendant_count() if location.has_children else 0,
            })

        return choices

    def get_stock_item_choices(self) -> list[dict]:
        """Return StockItems for page select inputs."""
        choices = []

        for item in StockItem.objects.select_related("part", "location").order_by("pk"):
            choices.append({
                "id": item.pk,
                "label": str(item.part),
                "location": self.get_location_info(item.location) if item.location else None,
                "in_stock": item.in_stock,
            })

        return choices

    def get_part_choices(self) -> list[dict]:
        """Return Parts for page select inputs."""
        choices = []

        for part in Part.objects.order_by("name", "pk"):
            stock_count = StockItem.objects.filter(part=part, location__isnull=False).count()
            choices.append({"id": part.pk, "label": part.full_name, "stock_count": stock_count})

        return choices
