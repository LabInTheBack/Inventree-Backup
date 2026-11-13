"""Read-only dashboard snapshots and reviewed, atomic mapping changes."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from types import SimpleNamespace

from stock.models import StockItem, StockLocation

from .constants import METADATA_INDICATOR_KEY
from .mapping import indicator_payload, inspect_mapping_metadata
from .planning import IndicatorCollection

PAGE_SIZE = 25
LED_PAGE_SIZE = 128
MAX_LOCATIONS = 100


class DashboardConflict(ValueError):
    """A reviewed assignment no longer matches the current configuration."""


def positive_integer(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if str(number) != str(value) or not 1 <= number <= 2**63 - 1:
        raise ValueError(f"{label} must be a positive integer")
    return number


def location_ids(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LOCATIONS:
        raise ValueError(f"Select between 1 and {MAX_LOCATIONS} locations")
    if any(type(pk) is not int or not 1 <= pk <= 2**63 - 1 for pk in value):
        raise ValueError("Location IDs must be positive integers")
    return list(dict.fromkeys(value))


def validate_saved_index(client, index, controller):
    """Validate zero-based storage while reporting one-based display numbers."""
    count = client.get_controller_max_leds(controller, discover=False)
    if type(index) is not int or not 0 <= index < count:
        raise ValueError(f"LED numbers for {controller} must be between 1 and {count}")
    return index


def mapping_row(record, client, labels):
    """Inspect saved metadata without discovering or contacting controllers."""
    metadata = record["metadata"]
    mapping = inspect_mapping_metadata(
        SimpleNamespace(metadata=metadata if isinstance(metadata, dict) else {}),
        labels,
        lambda led, label: validate_saved_index(client, led, label),
    )
    if not isinstance(metadata, dict) or (
        METADATA_INDICATOR_KEY in metadata and not isinstance(metadata[METADATA_INDICATOR_KEY], dict)
    ):
        mapping["invalid"] = "LED mapping must be an object with a controller and LED numbers"
    return {
        "id": record["pk"], "name": record["name"], "path": record["pathstring"] or record["name"],
        "controller": mapping["controller"], "leds": [led + 1 for led in mapping["leds"]],
        "error": mapping["invalid"], "state": "invalid" if mapping["invalid"] else (
            "mapped" if mapping["controller"] and mapping["leds"] else "unmapped"
        ),
    }


def location_index(plugin):
    records = list(StockLocation.objects.order_by("pathstring", "pk").values(
        "pk", "name", "pathstring", "metadata", "tree_id", "lft", "rght",
    ))
    controllers = plugin.get_wled_controllers(include_info=False)
    client = plugin.wled()
    labels = {item["label"] for item in controllers}
    rows, roots, usage = [], [], defaultdict(list)
    for record in records:
        if record["rght"] - record["lft"] != 1:
            roots.append({"id": record["pk"], "path": record["pathstring"] or record["name"]})
            continue
        row = mapping_row(record, client, labels)
        row["tree_id"], row["lft"] = record["tree_id"], record["lft"]
        rows.append(row)
        if row["state"] == "mapped":
            for led in row["leds"]:
                usage[(row["controller"], led)].append(row)
    for row in rows:
        row["shared_leds"] = [led for led in row["leds"] if len(usage[(row["controller"], led)]) > 1]
        if row["state"] == "mapped" and row["shared_leds"]:
            row["state"] = "shared"
    return records, controllers, rows, roots, usage


def build_dashboard(plugin, params):
    """Return paginated rows; global totals use a slim location/stock index."""
    from django.db.models import Count

    query = str(params.get("q", "")).strip()
    if len(query) > 200:
        raise ValueError("Search must not exceed 200 characters")
    state = str(params.get("state", "all"))
    if state not in {"all", "mapped", "unmapped", "shared", "invalid", "needs-led"}:
        raise ValueError("Unknown location state")
    page = positive_integer(params.get("page", "1"), "Page")
    root_id = positive_integer(params["root"], "Storage area") if params.get("root") else None
    led = positive_integer(params["led"], "LED") if params.get("led") else None
    controller_filter = str(params.get("controller", "")).strip()
    view = str(params.get("view", "locations"))
    if view not in {"locations", "tools"}:
        raise ValueError("Unknown dashboard view")
    records, controllers, rows, roots, usage = location_index(plugin)
    stock = StockItem.objects.filter(StockItem.IN_STOCK_FILTER, location__isnull=False)
    counts = {
        item["location_id"]: item for item in stock.order_by().values("location_id").annotate(
            stock_items=Count("pk"), part_count=Count("part_id", distinct=True),
        )
    }
    for row in rows:
        count = counts.get(row["id"], {})
        row.update(stock_items=count.get("stock_items", 0), part_count=count.get("part_count", 0))
    summary = dict(Counter(row["state"] for row in rows))
    summary.update(total=len(rows), mapped=sum(row["state"] in {"mapped", "shared"} for row in rows),
                   needs_led=sum(row["stock_items"] > 0 and row["state"] in {"unmapped", "invalid"} for row in rows))
    root = next((record for record in records if record["pk"] == root_id), None)
    if root_id and root is None:
        raise ValueError("The selected storage area no longer exists")
    matched_stock_locations = set()
    if query:
        matched_stock_locations = set(stock.filter(part__name__icontains=query).values_list("location_id", flat=True))
    filtered = []
    for row in rows:
        if controller_filter and row["controller"] != controller_filter:
            continue
        if led and led not in row["leds"]:
            continue
        if root and not (row["tree_id"] == root["tree_id"] and root["lft"] <= row["lft"] <= root["rght"]):
            continue
        if query and query.casefold() not in f"{row['id']} {row['path']} {row['controller'] or ''}".casefold() and row["id"] not in matched_stock_locations:
            continue
        if state == "needs-led":
            if not (row["stock_items"] > 0 and row["state"] in {"unmapped", "invalid"}):
                continue
        elif state == "mapped" and row["state"] not in {"mapped", "shared"}:
            continue
        elif state not in {"all", "mapped"} and row["state"] != state:
            continue
        filtered.append(row)
    pages = max(1, math.ceil(len(filtered) / PAGE_SIZE))
    page = min(page, pages)
    visible = filtered[(page - 1) * PAGE_SIZE:page * PAGE_SIZE] if view == "locations" else []
    names = defaultdict(list)
    if visible:
        for item in stock.filter(location_id__in=[row["id"] for row in visible]).order_by(
            "part__name", "part_id",
        ).values("location_id", "part_id", "part__name").distinct():
            if len(names[item["location_id"]]) < 3:
                names[item["location_id"]].append(item["part__name"])
    for row in visible:
        row["part_names"] = names[row["id"]]
    controller_rows = []
    for item in controllers:
        keys = [key for key in usage if key[0] == item["label"] and usage[key]]
        count = int(item.get("max_leds") or 0)
        controller_rows.append({
            "label": item["label"], "name": item.get("name") or "", "max_leds": count,
            "used": len(keys), "free": max(0, count - len(keys)),
            "shared": sum(len(usage[key]) > 1 for key in keys),
        })
    led_map = None
    if view == "tools" and controller_rows:
        selected = next((item for item in controller_rows if item["label"] == controller_filter), None)
        if controller_filter and not selected:
            raise ValueError("The selected controller is no longer configured")
        selected = selected or controller_rows[0]
        led_pages = max(1, math.ceil(selected["max_leds"] / LED_PAGE_SIZE))
        led_page = min(positive_integer(params.get("led_page", "1"), "LED page"), led_pages)
        start = (led_page - 1) * LED_PAGE_SIZE + 1
        stop = min(selected["max_leds"], start + LED_PAGE_SIZE - 1)
        led_map = {"controller": selected["label"], "page": led_page, "pages": led_pages, "cells": [
            {"led": number, "locations": [{"id": row["id"], "path": row["path"]} for row in usage[(selected["label"], number)]]}
            for number in range(start, stop + 1)
        ]}
    return {
        "rows": visible, "roots": roots, "controllers": controller_rows, "summary": summary,
        "total": len(filtered), "page": page, "pages": pages, "page_size": PAGE_SIZE, "led_map": led_map,
    }


def preview_mapping(plugin, payload, *, locked=False):
    """Validate every target and return a deterministic review and version."""
    ids = location_ids(payload.get("location_ids"))
    mode = payload.get("mode", "sequential")
    if mode not in {"sequential", "same", "remove"}:
        raise ValueError("Choose sequential LEDs, the same LEDs, or remove mapping")
    controller, leds = None, []
    if mode != "remove":
        controller = payload.get("controller")
        if not isinstance(controller, str) or not controller:
            raise ValueError("Choose a controller")
        raw_leds = payload.get("leds")
        if not isinstance(raw_leds, list) or not 1 <= len(raw_leds) <= 512:
            raise ValueError("Enter between 1 and 512 LED numbers")
        if any(type(led) is not int or not 1 <= led <= 2**31 - 1 for led in raw_leds):
            raise ValueError("LED numbers must be positive integers")
        leds = list(dict.fromkeys(raw_leds))
        if mode == "sequential" and len(ids) > 1 and len(leds) != 1:
            raise ValueError("Enter one starting LED for sequential assignment")
    queryset = StockLocation.objects.filter(pk__in=ids).order_by("pk")
    if locked:
        queryset = queryset.select_for_update()
    locations = {location.pk: location for location in queryset}
    if len(locations) != len(ids):
        raise ValueError("One or more selected locations no longer exist; refresh the list")
    client = plugin.wled()
    changes, snapshots = [], []
    assigned = defaultdict(list)
    for index, pk in enumerate(ids):
        location = locations[pk]
        if not location.is_leaf_node():
            raise ValueError(f"{location.name} is a parent location; select its drawers or boxes")
        if not isinstance(location.metadata, dict):
            raise ValueError(f"{location.name} has invalid metadata; correct it in InvenTree first")
        target_leds = ([leds[0] + index] if mode == "sequential" and len(ids) > 1 else leds) if mode != "remove" else []
        for led in target_leds:
            validate_saved_index(client, led - 1, controller)
            assigned[(controller, led)].append(pk)
        before = location.metadata.get(METADATA_INDICATOR_KEY)
        snapshots.append([pk, before])
        changes.append({
            "id": pk, "name": location.name, "path": location.pathstring or location.name,
            "before": before, "after": indicator_payload(controller, [led - 1 for led in target_leds]) if target_leds else None,
        })
    others = []
    for record in StockLocation.objects.exclude(pk__in=ids).values("pk", "name", "pathstring", "metadata", "lft", "rght"):
        metadata = record["metadata"]
        if record["rght"] - record["lft"] != 1 or not isinstance(metadata, dict):
            continue
        mapping = metadata.get(METADATA_INDICATOR_KEY)
        if not isinstance(mapping, dict) or mapping.get("controller") != controller:
            continue
        raw = mapping.get("leds", [mapping.get("led")])
        if not isinstance(raw, list):
            raw = [raw]
        for led in raw:
            if type(led) is int and (controller, led + 1) in assigned:
                others.append({"id": record["pk"], "path": record["pathstring"] or record["name"], "led": led + 1})
    shared = [led for (_, led), selected_ids in assigned.items() if len(selected_ids) > 1]
    version = hashlib.sha256(json.dumps(
        {"snapshots": snapshots, "changes": changes, "others": sorted(others, key=lambda item: (item["id"], item["led"]))},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return {"changes": changes, "shared_leds": shared, "shared_with": others, "revision": version}, locations


def save_mapping(plugin, payload):
    """Recheck a review under row locks and commit the entire batch together."""
    from django.db import transaction
    revision = payload.get("revision")
    if not isinstance(revision, str) or len(revision) != 64:
        raise ValueError("Review the mapping changes before saving")
    with transaction.atomic():
        review, locations = preview_mapping(plugin, payload, locked=True)
        if revision != review["revision"]:
            raise DashboardConflict("Mappings changed since your review. Review the changes again before saving.")
        for change in review["changes"]:
            location = locations[change["id"]]
            metadata = dict(location.metadata)
            if change["after"] is None:
                metadata.pop(METADATA_INDICATOR_KEY, None)
            else:
                metadata[METADATA_INDICATOR_KEY] = change["after"]
            location.metadata = metadata
            location.save(update_fields=["metadata"])
    plugin.locator().invalidate_plans()
    return {"saved": len(review["changes"])}


def locate_dashboard_locations(plugin, payload):
    """Resolve every selected leaf before sending any hardware command."""
    ids = location_ids(payload.get("location_ids"))
    locations = {location.pk: location for location in StockLocation.objects.filter(pk__in=ids)}
    if len(locations) != len(ids):
        raise DashboardConflict("A selected location no longer exists. Refresh the dashboard before locating.")
    client = plugin.wled()
    labels = {item["label"] for item in plugin.get_wled_controllers(include_info=False)}
    targets = IndicatorCollection()
    locator = plugin.locator()
    for pk in ids:
        location = locations[pk]
        if not location.is_leaf_node():
            raise DashboardConflict("Select individual drawers or boxes, then try locating again.")
        row = mapping_row({"pk": pk, "name": location.name, "pathstring": location.pathstring, "metadata": location.metadata}, client, labels)
        if row["state"] != "mapped":
            raise DashboardConflict(f"{location.name} needs a valid mapping. Refresh the dashboard before locating.")
        targets.extend(locator.get_location_led_plan(location)["indicators"])
    return {"located": len(ids), "wled": locator.apply_controller_leds(targets.controller_leds)}
