"""Plan picking for saved build requirements without allocating or consuming stock."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from build.models import Build, BuildItem, BuildLine
from stock.models import StockItem

from .bom import BomService, MAX_LINES, MAX_PARTS, MAX_STOCK_ITEMS, component_options
from .finder import part_image_urls
from .planning import IndicatorCollection
from .picking import picking_selection, with_picking


MAX_BUILDS = 100
MAX_ALLOCATIONS = 5000


def build_options(payload):
    _, _, _, selected = component_options(payload)
    if any(key in payload for key in ("quantity", "expand", "include_optional")):
        raise ValueError("Build quantities and component choices come from saved build lines")
    include = payload.get("include_subbuilds", False)
    if type(include) is not bool:
        raise ValueError("include_subbuilds must be true or false")
    return include, selected


class BuildComponentService(BomService):
    def preview(self, build_id, payload):
        include, _ = build_options(payload)
        root = Build.objects.select_related("part", "take_from").filter(pk=build_id).first()
        if root is None:
            raise ValueError("Build order not found")
        builds = [root] if root.is_active else []
        if include and root.is_active:
            descendants = list(root.get_descendants().select_related("part", "take_from").order_by("pk")[:MAX_BUILDS])
            if len(descendants) >= MAX_BUILDS:
                raise ValueError(f"Build tree exceeds the {MAX_BUILDS} order limit; open a sub-build")
            builds += [b for b in descendants if b.is_active]
        lines = list(BuildLine.objects.filter(build_id__in=[b.pk for b in builds]).select_related(
            "bom_item__sub_part", "build__part", "build__take_from",
        ).order_by("pk")[:MAX_LINES + 1]) if builds else []
        if len(lines) > MAX_LINES:
            raise ValueError(f"Build requirements exceed the {MAX_LINES} line limit")
        lines = [line for line in lines if line.quantity > line.consumed]
        parts = {line.bom_item.sub_part_id: line.bom_item.sub_part for line in lines}
        if len(parts) > MAX_PARTS:
            raise ValueError(f"Build requirements exceed the {MAX_PARTS} part limit")
        allocations = list(BuildItem.objects.filter(build_line_id__in=[line.pk for line in lines]).order_by("pk")[:MAX_ALLOCATIONS + 1]) if lines else []
        if len(allocations) > MAX_ALLOCATIONS:
            raise ValueError(f"Build requirements exceed the {MAX_ALLOCATIONS} allocation limit")
        stocks = list(StockItem.objects.filter(StockItem.IN_STOCK_FILTER).filter(
            Q(part_id__in=parts) | Q(pk__in=[a.stock_item_id for a in allocations]),
        ).select_related("part", "location").order_by("pk")[:MAX_STOCK_ITEMS + 1]) if lines else []
        if len(stocks) > MAX_STOCK_ITEMS:
            raise ValueError(f"Build requirements exceed the {MAX_STOCK_ITEMS} stock record limit")
        by_id = {stock.pk: stock for stock in stocks}
        stocks_by_part = defaultdict(list)
        for stock in stocks:
            stocks_by_part[stock.part_id].append(stock)
        reservations = StockItem.bulk_allocation_count(stocks) if stocks else {}
        owned, by_line = defaultdict(Decimal), defaultdict(list)
        for allocation in allocations:
            owned[allocation.stock_item_id] += allocation.quantity
            by_line[allocation.build_line_id].append(allocation)
        # Other work keeps its reservations. Cap this scope's allocations at
        # physical stock too, even if stale/overallocated records exist.
        owned_pool = {s.pk: min(owned[s.pk], max(s.quantity - max(reservations.get(s.pk, 0) - owned[s.pk], 0), 0)) for s in stocks}
        free = {s.pk: max(s.quantity - reservations.get(s.pk, 0), Decimal(0)) for s in stocks}
        scratch = dict(free)
        remaining, assigned = {}, defaultdict(Decimal)
        contributions = defaultdict(dict)
        totals = defaultdict(lambda: {"required": Decimal(0), "allocated": Decimal(0), "consumed": Decimal(0), "shortage": Decimal(0), "sources": []})

        def contribution(part_id, stock):
            return contributions[part_id].setdefault(stock.pk, {"stock": stock, "allocated": Decimal(0), "free": Decimal(0), "pick": Decimal(0)})

        for line in lines:
            pk = line.bom_item.sub_part_id
            remaining[line.pk] = line.quantity - line.consumed
            total = totals[pk]
            total["required"] += remaining[line.pk]
            total["consumed"] += line.consumed
            total["allocated"] += sum((a.quantity for a in by_line[line.pk]), Decimal(0))
            for allocation in by_line[line.pk]:
                stock = by_id.get(allocation.stock_item_id)
                if stock is None:
                    continue
                used = min(allocation.quantity, owned_pool[stock.pk], remaining[line.pk] - assigned[line.pk])
                assigned[line.pk] += used
                owned_pool[stock.pk] -= used
                contribution(pk, stock)["allocated"] += used
                contribution(pk, stock)["pick"] += used

        # Scarcer source locations go first. This is a read-only availability
        # estimate; a shared stock record is never counted twice across builds.
        ordered = sorted(lines, key=lambda line: (-(line.build.take_from.level + 1) if line.build.take_from_id else 0, line.pk))
        for line in ordered:
            pk = line.bom_item.sub_part_id
            need = remaining[line.pk] - assigned[line.pk]
            source = line.build.take_from
            if need > 0:
                for stock in stocks_by_part[pk]:
                    location = stock.location
                    if source and (not location or source.tree_id != location.tree_id or not source.lft <= location.lft <= source.rght):
                        continue
                    contribution(pk, stock)["free"] = free[stock.pk]
                    used = min(need, scratch[stock.pk])
                    need -= used
                    scratch[stock.pk] -= used
                    contribution(pk, stock)["pick"] += used
            total = totals[pk]
            total["shortage"] += need
            total["sources"].append({
                "assembly": self.locator.get_part_info(line.build.part), "build_line_id": line.pk,
                "build": self.locator.get_build_info(line.build), "reference": line.bom_item.reference,
                "quantity": str(remaining[line.pk]), "consumed_quantity": str(line.consumed),
                "allocated_quantity": str(sum((a.quantity for a in by_line[line.pk]), Decimal(0))),
                "shortage": str(need), "validated": line.bom_item.validated,
            })

        rows, targets, location_ids = [], IndicatorCollection(), set()
        for pk, part in parts.items():
            total = totals[pk]
            groups, component_targets = {}, IndicatorCollection()
            stock_quantity, available, allocated_available = Decimal(0), Decimal(0), Decimal(0)
            for entry in contributions[pk].values():
                stock = entry["stock"]
                stock_quantity += stock.quantity
                usable = entry["allocated"] + entry["free"]
                available += usable
                allocated_available += entry["allocated"]
                location = stock.location
                key = stock.location_id
                if key not in groups:
                    indicators, reason = [], "Stock has no assigned location"
                    if location:
                        try:
                            indicators = self.locator.get_location_led_plan(location)["indicators"]
                            reason = "" if indicators else "Location has no mapped LEDs"
                        except ValueError as exc:
                            reason = str(exc)
                    groups[key] = {"location": self.locator.get_location_info(location) if location else None,
                                   "available_quantity": Decimal(0), "allocated_quantity": Decimal(0),
                                   "pick_quantity": Decimal(0),
                                   "indicators": indicators, "reason": reason, "stock_parts": set()}
                group = groups[key]
                group["stock_parts"].add(stock.part.full_name)
                group["available_quantity"] += usable
                group["allocated_quantity"] += entry["allocated"]
                group["pick_quantity"] += entry["pick"]
                if usable > 0 and group["indicators"] and not part.virtual:
                    component_targets.extend(group["indicators"])
                    location_ids.add(key)
            for group in groups.values():
                group["can_locate"] = bool(group["indicators"]) and group["available_quantity"] > 0 and not part.virtual
                group["available_quantity"] = str(group["available_quantity"])
                group["allocated_quantity"] = str(group["allocated_quantity"])
                group["pick_quantity"] = str(group["pick_quantity"])
                group["stock_parts"] = sorted(group["stock_parts"])
            targets.extend(component_targets.indicators)
            rows.append({"part": {**self.locator.get_part_info(part), **part_image_urls(part), "units": getattr(part, "units", "")},
                         "required_quantity": str(total["required"]), "stock_quantity": str(stock_quantity),
                         "available_quantity": str(available), "allocated_quantity": str(total["allocated"]),
                         "allocated_available_quantity": str(allocated_available), "consumed_quantity": str(total["consumed"]),
                         "shortage": str(total["shortage"]), "sources": total["sources"], "locations": list(groups.values()),
                         "indicators": component_targets.indicators, "can_locate": bool(component_targets.indicators), "virtual": part.virtual,
                         "planned_outputs": [{"build": b.reference, "quantity": max(b.quantity - b.completed, 0)} for b in builds if b.pk != root.pk and b.part_id == pk]})
        return with_picking({"build": {**self.locator.get_build_info(root), "quantity": root.quantity, "completed": root.completed, "active": root.is_active},
                "quantity": root.quantity, "include_subbuilds": include, "components": rows, "can_locate": bool(targets.indicators),
                "controller_leds": targets.controller_leds, "indicators": targets.indicators,
                "summary": {"components": len(rows), "locatable_components": sum(r["can_locate"] for r in rows),
                            "short_components": sum(Decimal(r["shortage"]) > 0 for r in rows), "unique_locations": len(location_ids),
                            "unique_leds": len(targets.indicators), "builds": len(builds)}})

    def locate(self, build_id, payload):
        _, selected = build_options(payload)
        self.locator.invalidate_plans()
        return self.execute_plan(self.preview(build_id, payload), selected, picking_selection(payload))
