"""Read-only picking suggestions and validation of browser checklist state."""

from collections import OrderedDict
from decimal import Decimal
import hashlib
import json
import re

from .finder import SelectionNotLocatable


MAX_PICKING_PARTS = 1000


class PickingChanged(SelectionNotLocatable):
    def __init__(self, plan):
        ValueError.__init__(self, "Component requirements changed. Review the refreshed picking checklist before highlighting")
        self.plan = plan


def picking_selection(payload):
    if "remaining_component_ids" not in payload and "picking_revision" not in payload:
        return None
    ids, revision = payload.get("remaining_component_ids"), payload.get("picking_revision")
    if not isinstance(ids, list) or len(ids) > MAX_PICKING_PARTS:
        raise ValueError(f"remaining_component_ids must be a list of at most {MAX_PICKING_PARTS} IDs")
    if any(type(pk) is not int or not 1 <= pk <= (1 << 53) - 1 for pk in ids) or len(set(ids)) != len(ids):
        raise ValueError("Remaining components need unique positive integer IDs")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise ValueError("Remaining components need a valid picking_revision")
    return ids, revision


def remaining_components(plan, selection):
    if selection is None:
        return plan["components"]
    ids, revision = selection
    current = {row["part"]["id"] for row in plan["components"]}
    selected = set(ids)
    if revision != plan["picking"]["revision"] or not selected.issubset(current):
        raise PickingChanged(plan)
    return [row for row in plan["components"] if row["part"]["id"] in selected]


def with_picking(plan):
    """Suggest quantities once per location; build plans supply source-aware picks."""
    groups, shortages = OrderedDict(), []
    for row in plan["components"]:
        requirement = Decimal(row["required_quantity"])
        sources = [{"bom_line": source.get("bom_line_id"), "build_line": source.get("build_line_id"),
                    "assembly": source["assembly"]["id"], "build": source.get("build", {}).get("id"),
                    "quantity": str(Decimal(source["quantity"]).normalize()), "reference": source["reference"]}
                   for source in row["sources"]]
        sources.sort(key=lambda source: json.dumps(source, sort_keys=True))
        identity = {"part": row["part"]["id"], "quantity": str(requirement.normalize()), "units": row["part"].get("units", ""), "sources": sources}
        row["picking_fingerprint"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        left = requirement
        locations = sorted(row["locations"], key=lambda g: (not g["can_locate"], g["location"] is None))
        for location in locations:
            pick = Decimal(location["pick_quantity"]) if "pick_quantity" in location else min(left, Decimal(location["available_quantity"]))
            if pick < 0 or pick > left:
                raise ValueError("Picking quantities do not match component requirements")
            left -= pick
            location["pick_quantity"] = str(pick)
            if not pick:
                continue
            key = location["location"]["id"] if location["location"] else None
            group = groups.setdefault(key, {"location": location["location"], "items": []})
            group["items"].append({"part_id": row["part"]["id"], "quantity": str(pick),
                                   "can_locate": location["can_locate"], "reason": location["reason"]})
        if left > 0:
            shortages.append({"part_id": row["part"]["id"], "quantity": str(left)})
    revision = hashlib.sha256("".join(sorted(row["picking_fingerprint"] for row in plan["components"])).encode()).hexdigest()
    locations = sorted(groups.values(), key=lambda group: (group["location"] is None, (group["location"] or {}).get("path", "").casefold()))
    plan["picking"] = {"version": 1, "revision": revision, "locations": locations, "shortages": shortages}
    return plan
