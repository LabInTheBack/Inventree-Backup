"""Read-only assembly component planning; execution reuses the locator transport."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from part.models import BomItem, Part
from stock.models import StockItem

from .finder import SavedControllerConfiguration, SelectionNotLocatable, part_image_urls
from .locator import LocatorService
from .planning import IndicatorCollection
from .picking import picking_selection, remaining_components, with_picking


MAX_PARTS = 1000
MAX_LINES = 2000
MAX_DEPTH = 12
MAX_STOCK_ITEMS = 5000


class ComponentsNotLocatable(SelectionNotLocatable):
    def __init__(self, plan):
        ValueError.__init__(self, "No available component stock has a usable LED mapping")
        self.plan = plan


def component_options(payload):
    """Validate options before loading inventory. Browser LED targets are never used."""
    picking_selection(payload)
    quantity = payload.get("quantity", 1)
    if type(quantity) is not int or not 1 <= quantity <= 10000:
        raise ValueError("Quantity must be a whole number from 1 to 10000")
    expand = payload.get("expand", False)
    optional = payload.get("include_optional", False)
    if type(expand) is not bool or type(optional) is not bool:
        raise ValueError("expand and include_optional must be true or false")
    component_id = payload.get("component_id")
    if component_id is not None and (type(component_id) is not int or not 1 <= component_id <= (1 << 63) - 1):
        raise ValueError("component_id must be a positive integer")
    return quantity, expand, optional, component_id


class BomService:
    def __init__(self, plugin):
        self.plugin = plugin
        self.locator = LocatorService(plugin, wled=SavedControllerConfiguration(plugin.wled()))

    def _graph(self, root, expand, include_optional):
        """Fetch effective BOMs by depth, including native variant inheritance."""
        parts, graph = {root.pk: root}, {}
        frontier = [root]
        line_count = 0
        optional_skipped = 0
        edge_count = 0
        for depth in range(MAX_DEPTH + 1):
            if not frontier:
                break
            query = Q(pk__in=[])
            for part in frontier:
                query |= part.get_bom_item_filter()
            lines = list(BomItem.objects.filter(query).select_related("part", "sub_part").order_by("pk")[:MAX_LINES + 1])
            line_count += len(lines)
            if line_count > MAX_LINES:
                raise ValueError(f"BOM exceeds the {MAX_LINES} line limit; open a smaller subassembly")
            upcoming = {}
            for part in frontier:
                graph[part.pk] = []
                for line in lines:
                    owner = line.part
                    inherited = (line.inherited and owner.tree_id == part.tree_id
                                 and owner.lft < part.lft < owner.rght)
                    if line.part_id != part.pk and not inherited:
                        continue
                    if line.optional and not include_optional:
                        optional_skipped += 1
                        continue
                    graph[part.pk].append(line)
                    edge_count += 1
                    if edge_count > MAX_LINES:
                        raise ValueError(f"BOM exceeds the {MAX_LINES} effective line limit")
                    child = line.sub_part
                    parts[child.pk] = child
                    if len(parts) > MAX_PARTS:
                        raise ValueError(f"BOM exceeds the {MAX_PARTS} part limit; open a smaller subassembly")
                    if expand and (child.assembly or child.virtual) and child.pk not in graph:
                        upcoming[child.pk] = child
            frontier = [part for pk, part in upcoming.items() if pk not in graph]
        if frontier:
            raise ValueError(f"BOM exceeds {MAX_DEPTH} nested levels; open a smaller subassembly")
        return parts, graph, optional_skipped

    def _requirements(self, root, graph, quantity):
        """Topological order aggregates shared subassemblies before expanding them."""
        visited, visiting, ordered = set(), set(), []

        def visit(pk, depth):
            if pk in visiting:
                raise ValueError("BOM contains a circular assembly reference")
            if depth > MAX_DEPTH:
                raise ValueError(f"BOM exceeds {MAX_DEPTH} nested levels")
            if pk in visited:
                return
            visiting.add(pk)
            for line in graph.get(pk, []):
                visit(line.sub_part_id, depth + 1)
            visiting.remove(pk)
            visited.add(pk)
            ordered.append(pk)

        visit(root.pk, 0)
        # A shared node may first be visited through a shorter branch. Check
        # the longest path too, rather than relying only on DFS call depth.
        heights = {}
        for pk in ordered:
            heights[pk] = max((heights[line.sub_part_id] + 1 for line in graph.get(pk, [])), default=0)
        if heights[root.pk] > MAX_DEPTH:
            raise ValueError(f"BOM exceeds {MAX_DEPTH} nested levels")
        required = defaultdict(Decimal, {root.pk: Decimal(quantity)})
        sources = defaultdict(list)
        for pk in reversed(ordered):
            if required[pk] <= 0:
                continue
            for line in graph.get(pk, []):
                amount = line.get_required_quantity(required[pk])
                if not amount.is_finite() or amount < 0 or amount > Decimal("1e12"):
                    raise ValueError("BOM component quantity exceeds the supported range")
                required[line.sub_part_id] += amount
                if required[line.sub_part_id] > Decimal("1e12"):
                    raise ValueError("BOM component quantity exceeds the supported range")
                sources[line.sub_part_id].append({
                    "assembly": self.locator.get_part_info(line.part), "bom_line_id": line.pk,
                    "reference": line.reference, "quantity": str(amount),
                    "optional": line.optional, "consumable": line.is_consumable,
                    "validated": line.validated,
                })
        leaves = [pk for pk in reversed(ordered) if pk != root.pk and not graph.get(pk) and required[pk] > 0]
        return required, sources, leaves

    def preview(self, part_id, payload):
        quantity, expand, optional, _ = component_options(payload)
        root = Part.objects.filter(pk=part_id, assembly=True).first()
        if root is None:
            raise ValueError("Assembly part not found")
        parts, graph, skipped = self._graph(root, expand, optional)
        required, sources, leaves = self._requirements(root, graph, quantity)
        stocks = list(StockItem.objects.filter(
            StockItem.IN_STOCK_FILTER, part_id__in=leaves,
        ).select_related("part", "location").order_by("pk")[:MAX_STOCK_ITEMS + 1]) if leaves else []
        if len(stocks) > MAX_STOCK_ITEMS:
            raise ValueError(f"BOM exceeds the {MAX_STOCK_ITEMS} stock record limit; open a smaller subassembly")
        allocations = StockItem.bulk_allocation_count(stocks) if stocks else {}
        by_part = defaultdict(list)
        for stock in stocks:
            by_part[stock.part_id].append(stock)
        targets, all_locations, rows = IndicatorCollection(), {}, []
        for pk in leaves:
            part = parts[pk]
            locations, stock_total, available_total = {}, Decimal(0), Decimal(0)
            component_targets = IndicatorCollection()
            for stock in by_part[pk]:
                free = max(stock.quantity - allocations.get(stock.pk, 0), Decimal(0))
                stock_total += stock.quantity
                available_total += free
                location = stock.location
                key = stock.location_id
                if key not in locations:
                    indicators, reason = [], "Stock has no assigned location"
                    if location:
                        try:
                            indicators = self.locator.get_location_led_plan(location)["indicators"]
                            reason = "" if indicators else "Location has no mapped LEDs"
                        except ValueError as exc:
                            reason = str(exc)
                    locations[key] = {"location": self.locator.get_location_info(location) if location else None,
                                      "stock_quantity": Decimal(0), "available_quantity": Decimal(0),
                                      "indicators": indicators, "reason": reason}
                group = locations[key]
                group["stock_quantity"] += stock.quantity
                group["available_quantity"] += free
                if free > 0 and group["indicators"] and not part.virtual:
                    component_targets.extend(group["indicators"])
                    all_locations[key] = group["location"]
            for group in locations.values():
                group["can_locate"] = bool(group["indicators"]) and group["available_quantity"] > 0 and not part.virtual
                group["stock_quantity"] = str(group["stock_quantity"])
                group["available_quantity"] = str(group["available_quantity"])
            targets.extend(component_targets.indicators)
            rows.append({
                "part": {**self.locator.get_part_info(part), **part_image_urls(part), "units": getattr(part, "units", "")},
                "required_quantity": str(required[pk]), "stock_quantity": str(stock_total),
                "available_quantity": str(available_total), "shortage": str(max(required[pk] - available_total, Decimal(0))),
                "sources": sources[pk], "locations": list(locations.values()),
                "indicators": component_targets.indicators, "can_locate": bool(component_targets.indicators),
                "virtual": part.virtual, "unexpanded_assembly": bool(expand and part.assembly),
            })
        return with_picking({"assembly": self.locator.get_part_info(root), "quantity": quantity, "expand": expand,
                "include_optional": optional, "components": rows, "can_locate": bool(targets.indicators),
                "controller_leds": targets.controller_leds, "indicators": targets.indicators,
                "summary": {"components": len(rows), "locatable_components": sum(r["can_locate"] for r in rows),
                            "short_components": sum(Decimal(r["shortage"]) > 0 for r in rows),
                            "unique_locations": len(all_locations), "unique_leds": len(targets.indicators),
                            "optional_lines_skipped": skipped}})

    def locate(self, part_id, payload):
        _, _, _, selected = component_options(payload)
        self.locator.invalidate_plans()
        plan = self.preview(part_id, payload)
        return self.execute_plan(plan, selected, picking_selection(payload))

    def execute_plan(self, plan, selected=None, picking=None):
        """Execute a freshly resolved component plan, including an optional subset."""
        rows = remaining_components(plan, picking)
        if selected is not None:
            rows = [row for row in rows if row["part"]["id"] == selected]
            if not rows:
                raise ValueError("Component is not in this assembly or build's current component list")
        targets, locations = IndicatorCollection(), set()
        for row in rows:
            targets.extend(row["indicators"])
            locations.update(g["location"]["id"] for g in row["locations"] if g["can_locate"])
        if not targets.indicators:
            raise ComponentsNotLocatable(plan)
        return {**plan, "highlighted_components": sum(row["can_locate"] for row in rows),
                "highlighted_locations": len(locations), "wled": self.plugin.locator().apply_controller_leds(targets.controller_leds)}
