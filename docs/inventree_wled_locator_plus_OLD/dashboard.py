"""Dashboard data preparation for WLED Locator Plus."""

from __future__ import annotations

from stock.models import StockItem, StockLocation

from .mapping import inspect_mapping_metadata, location_path


def build_dashboard(plugin, params) -> dict:
    """Build all dashboard data from StockLocation metadata."""
    controllers = plugin.get_wled_controllers(include_info=False)
    controller_labels = {item["label"] for item in controllers}
    filters = parse_filters(params)
    root_location = get_root_filter(filters["root"])
    root_ids = (
        set(root_location.get_descendants(include_self=True).values_list("pk", flat=True))
        if root_location
        else None
    )
    component_map = build_component_map()
    all_rows = []
    led_usage = {}
    invalid_count = 0

    locations = StockLocation.objects.order_by("pathstring", "name")
    for location in locations:
        if location.has_children:
            continue

        row = build_location_row(plugin, location, controller_labels)
        row.update(component_map.get(location.pk, empty_component_info()))
        all_rows.append(row)

        if row["invalid"]:
            invalid_count += 1

        if row["controller"] and row["led"] is not None:
            led_usage.setdefault((row["controller"], row["led"]), []).append(row)

    conflict_keys = {key for key, rows in led_usage.items() if len(rows) > 1}

    for row in all_rows:
        row["conflict"] = (
            (row["controller"], row["led"]) in conflict_keys
            if row["controller"]
            else False
        )
        row["state"] = row_state(row)

    filtered_rows = sorted(
        (row for row in all_rows if row_matches_filters(row, filters, root_ids)),
        key=dashboard_sort_key,
    )
    selected_leds = {
        (row["controller"], row["led"])
        for row in filtered_rows
        if row["controller"] and row["led"] is not None
    }

    return {
        "controllers": controllers,
        "controller_usage": controller_usage_summary(controllers, led_usage),
        "controller_count": len(controllers),
        "filters": filters,
        "root_location": root_location,
        "root_options": root_options(),
        "rows": filtered_rows,
        "filtered_count": len(filtered_rows),
        "led_usage": led_usage,
        "conflict_keys": conflict_keys,
        "selected_leds": selected_leds,
        "summary": dashboard_summary(
            controllers,
            all_rows,
            filtered_rows,
            led_usage,
            conflict_keys,
            invalid_count,
        ),
    }


def parse_filters(params) -> dict:
    """Return normalized dashboard filters from request query parameters."""
    return {
        "controller": str(params.get("controller", "")).strip(),
        "root": str(params.get("root", "")).strip(),
        "q": str(params.get("q", "")).strip(),
        "state": str(params.get("state", "all")).strip() or "all",
        "led": str(params.get("led", "")).strip(),
    }


def dashboard_sort_key(row: dict) -> tuple:
    """Return stable dashboard row ordering."""
    return (
        row["controller"] or "zzzz",
        row["led"] if row["led"] is not None else 10**9,
        row["path"],
    )


def dashboard_summary(
    controllers: list[dict],
    all_rows: list[dict],
    filtered_rows: list[dict],
    led_usage: dict,
    conflict_keys: set,
    invalid_count: int,
) -> dict:
    """Return dashboard count metrics."""
    return {
        "mapped": sum(
            1
            for row in all_rows
            if row["controller"] and row["led"] is not None
        ),
        "free_leds": count_free_leds(controllers, led_usage),
        "assigned_filtered": sum(
            1 for row in filtered_rows if row["state"] == "assigned"
        ),
        "unassigned_filtered": sum(
            1 for row in filtered_rows if row["state"] == "unassigned"
        ),
        "conflicts": len(conflict_keys),
        "conflict_rows": sum(1 for row in all_rows if row.get("conflict")),
        "needs_led": sum(
            1
            for row in all_rows
            if row["state"] == "unassigned" and int(row.get("component_count") or 0) > 0
        ),
        "invalid": invalid_count,
    }


def build_location_row(plugin, location: StockLocation, controller_labels: set[str]) -> dict:
    """Return one dashboard row for a leaf StockLocation."""
    mapping = inspect_mapping_metadata(
        location,
        controller_labels,
        plugin.validate_led_index,
    )
    path = location_path(location)

    return {
        "id": location.pk,
        "name": location.name,
        "path": path,
        "path_parts": split_location_path(path),
        "location": location,
        **mapping,
    }


def build_component_map() -> dict[int, dict]:
    """Return component counts and names grouped by leaf StockLocation ID."""
    grouped = {}
    items = (
        StockItem.objects.select_related("part", "location")
        .filter(location__isnull=False)
        .order_by("part__name", "pk")
    )

    for item in items:
        if not item.location_id:
            continue

        entry = grouped.setdefault(item.location_id, empty_component_info())
        entry["component_count"] += 1

        part_name = item.part.name if item.part else f"StockItem {item.pk}"
        if part_name not in entry["component_names"]:
            entry["component_names"].append(part_name)

    for entry in grouped.values():
        entry["component_text"] = component_text(entry)

    return grouped


def empty_component_info() -> dict:
    """Return empty component summary fields for a StockLocation row."""
    return {
        "component_count": 0,
        "component_names": [],
        "component_text": "No components",
    }


def component_text(entry: dict) -> str:
    """Return compact component/count text for dashboard rows."""
    count = int(entry.get("component_count") or 0)
    names = entry.get("component_names") or []

    if not count:
        return "No components"

    if len(names) <= 2:
        return f"{count} component(s): {', '.join(names)}"

    return f"{count} component(s): {', '.join(names[:2])}, +{len(names) - 2} more"


def split_location_path(path: str) -> dict:
    """Split an InvenTree path into parent location and bin/sub-location labels."""
    parts = [item.strip() for item in str(path or "").split("/") if item.strip()]

    if not parts:
        return {"location": "Location", "bin": ""}

    if len(parts) == 1:
        return {"location": parts[0], "bin": ""}

    return {"location": " / ".join(parts[:-1]), "bin": parts[-1]}


def row_state(row: dict) -> str:
    """Return a user-facing state key for a dashboard row."""
    if row["invalid"]:
        return "invalid"

    if row.get("conflict"):
        return "conflict"

    if row["controller"] and row["led"] is not None:
        return "assigned"

    if row["led"] is not None and not row["controller"]:
        return "led-only"

    return "unassigned"


def row_matches_filters(row: dict, filters: dict, root_ids: set[int] | None) -> bool:
    """Return True if a location row matches selected dashboard filters."""
    if filters["controller"] and row["controller"] != filters["controller"]:
        return False

    if filters["led"]:
        try:
            if row["led"] != int(filters["led"]) - 1:
                return False
        except ValueError:
            return False

    if root_ids is not None and row["id"] not in root_ids:
        return False

    text = filters["q"].lower()
    if text:
        searchable = (
            f"{row['id']} {row['path']} {row['name']} {row['controller'] or ''} "
            f"{display_led(row['led'])} {row.get('component_text', '')} "
            f"{' '.join(row.get('component_names', []))}"
        ).lower()
        if text not in searchable:
            return False

    state = filters["state"]
    if state == "needs-led":
        return row["state"] == "unassigned" and int(row.get("component_count") or 0) > 0

    if state != "all" and row["state"] != state:
        return False

    return True


def controller_usage_summary(controllers: list[dict], led_usage: dict) -> list[dict]:
    """Return compact usage metrics for each configured controller."""
    summary = []

    for controller in controllers:
        label = controller["label"]
        max_leds = int(controller.get("max_leds") or 0)
        used = {
            led
            for (controller_label, led), rows in led_usage.items()
            if controller_label == label and rows
        }
        conflicts = sum(
            1
            for (controller_label, _led), rows in led_usage.items()
            if controller_label == label and len(rows) > 1
        )
        summary.append({
            "label": label,
            "name": controller.get("name") or "",
            "max_leds": max_leds,
            "used": len(used),
            "free": max(0, max_leds - len(used)),
            "conflicts": conflicts,
        })

    return summary


def count_free_leds(controllers: list[dict], led_usage: dict) -> int:
    """Return total unassigned LEDs for configured controller records."""
    total = 0

    for controller in controllers:
        label = controller["label"]
        max_leds = int(controller.get("max_leds") or 0)
        used = {
            led
            for (controller_label, led), rows in led_usage.items()
            if controller_label == label and rows
        }
        total += max(0, max_leds - len(used))

    return total


def get_root_filter(root_id: str):
    """Return selected StockLocation root filter, or None."""
    if not root_id:
        return None

    try:
        return StockLocation.objects.get(pk=int(root_id))
    except (TypeError, ValueError, StockLocation.DoesNotExist):
        return None


def root_options() -> list[dict]:
    """Return StockLocations for the parent-location filter."""
    options = []

    for location in StockLocation.objects.order_by("pathstring", "name"):
        if not location.has_children:
            continue

        options.append({
            "id": location.pk,
            "path": location_path(location),
        })

    return options


def display_led(led) -> str:
    """Return 1-based LED display text for a zero-based internal LED index."""
    if led is None or led == "":
        return ""

    try:
        return str(int(led) + 1)
    except (TypeError, ValueError):
        return ""
