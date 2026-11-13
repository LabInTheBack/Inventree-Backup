"""Multi-query part search and explicit multi-part selection planning."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.core import signing
from django.db.models import BooleanField, Case, Exists, IntegerField, OuterRef, Q, Value, When

from common.models import Parameter
from company.models import ManufacturerPart
from part.models import Part
from stock.models import StockItem

from .locator import LocatorService
from .planning import IndicatorCollection
from .search_terms import SPECS, parse_value_search, unit_aliases


MAX_QUERIES = 20
MAX_QUERY_LENGTH = 200
MAX_QUERY_TERMS = 12
MAX_MATCHES = 10
CURSOR_SALT = "wled-locator-plus.finder-page"
CURSOR_MAX_AGE = 3600
MAX_SELECTED_PARTS = 100


def part_image_urls(part) -> dict:
    """Read stored image URLs without generating thumbnail files during search."""
    image = getattr(part, "image", None)
    if not image:
        return {"image_url": None, "thumbnail_url": None}
    thumbnail = getattr(image, "thumbnail", None)
    original_url = image.url
    return {
        "image_url": original_url,
        "thumbnail_url": thumbnail.url if thumbnail else original_url,
    }


class SelectionNotLocatable(ValueError):
    """The selection needs correction before any hardware may be changed."""

    def __init__(self, plan):
        super().__init__("Every selected part must exist and have at least one locatable stock location")
        self.plan = plan


class SavedControllerConfiguration:
    """Let new finder previews validate mappings without controller HTTP reads."""

    def __init__(self, wled):
        self.wled = wled

    def get_controller(self, label):
        return self.wled.get_controller(label)

    def validate_led_index(self, led, label):
        return self.wled.validate_led_index(led, label, discover=False)


def validate_part_ids(part_ids) -> list[int]:
    """Require explicit database IDs; preserve selection order and deduplicate."""
    if not isinstance(part_ids, list) or not 1 <= len(part_ids) <= MAX_SELECTED_PARTS:
        raise ValueError(f"part_ids must contain between 1 and {MAX_SELECTED_PARTS} positive integer IDs")
    if any(type(pk) is not int or not 1 <= pk <= (1 << 63) - 1 for pk in part_ids):
        raise ValueError("part_ids must contain positive integer IDs")
    return list(dict.fromkeys(part_ids))


def validate_queries(queries, limit):
    """Bound search work and keep separate requested parts separate."""
    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
        raise ValueError(f"queries must contain between 1 and {MAX_QUERIES} search strings")
    if type(limit) is not int or not 1 <= limit <= MAX_MATCHES:
        raise ValueError(f"limit must be an integer between 1 and {MAX_MATCHES}")
    normalized = []
    for query in queries:
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Each query must be a non-empty string of at most {MAX_QUERY_LENGTH} characters")
        if any(ord(char) < 32 and not char.isspace() for char in query):
            raise ValueError("Search strings must not contain control characters")
        query = " ".join(query.split())
        if len(query.split()) > MAX_QUERY_TERMS:
            raise ValueError(f"Each query may contain at most {MAX_QUERY_TERMS} search terms")
        normalized.append(query)
    return normalized, limit


class FinderService:
    """Resolve candidates and selections; hardware execution is a separate step."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.locator = LocatorService(plugin, wled=SavedControllerConfiguration(plugin.wled()))

    @staticmethod
    def _text_match(term):
        manufacturer_match = ManufacturerPart.objects.filter(part_id=OuterRef("pk"), MPN__icontains=term)
        return (Q(name__icontains=term) | Q(IPN__icontains=term) | Q(keywords__icontains=term)
                | Q(description__icontains=term) | Q(Exists(manufacturer_match)))

    @staticmethod
    def _value_match(value):
        spec = SPECS[value.kind]
        explicit, bare = value.patterns()
        family = (Q(name__iregex=value.family_pattern) | Q(keywords__iregex=value.family_pattern)
                  | Q(description__iregex=value.family_pattern) | Q(category__name__iregex=value.family_pattern)
                  | Q(category__pathstring__iregex=value.family_pattern))
        explicit_text = Q(name__regex=explicit) | Q(keywords__regex=explicit) | Q(description__regex=explicit)
        bare_text = Q(name__regex=bare) | Q(keywords__regex=bare) | Q(description__regex=bare)
        units = [alias for prefix in spec["prefixes"] for alias in unit_aliases(value.kind, prefix)]
        number = float(value.value)
        rounding = abs(number) * 1e-12  # Float storage round-off, not component tolerance.
        parameter = Parameter.objects.filter(
            model_type__app_label="part", model_type__model="part", model_id=OuterRef("pk"),
            template__name__iexact=spec["template"], template__units__in=units,
            data_numeric__gte=number - rounding, data_numeric__lte=number + rounding,
        )
        result = explicit_text | (bare_text & family) | Q(Exists(parameter))
        return result & family if value.require_family else result

    def _find_candidates(self, query: str, limit: int, after=None):
        parts = Part.objects.filter(active=True, virtual=False)
        value = parse_value_search(query)
        if value:
            normalized = self._value_match(value)
            for term in value.terms:
                normalized &= self._text_match(term)
            # Exact identifiers remain searchable without treating their fragments
            # as measurements. Case matters here because M and m are different.
            exact_mpn = ManufacturerPart.objects.filter(part_id=OuterRef("pk"), MPN__exact=query)
            parts = parts.filter(normalized | Q(IPN__exact=query) | Q(name__exact=query) | Q(Exists(exact_mpn)))
        else:
            for term in query.split():
                parts = parts.filter(self._text_match(term))
        exact_mpn = ManufacturerPart.objects.filter(part_id=OuterRef("pk"), MPN__iexact=query)
        parts = parts.annotate(_finder_rank=Case(
            When(IPN__iexact=query, then=Value(0)),
            When(name__iexact=query, then=Value(1)),
            When(Exists(exact_mpn), then=Value(2)),
            default=Value(3), output_field=IntegerField(),
        ))
        if after:
            parts = parts.filter(
                Q(_finder_rank__gt=after["rank"]) |
                Q(_finder_rank=after["rank"], name__gt=after["name"]) |
                Q(_finder_rank=after["rank"], name=after["name"], pk__gt=after["id"])
            )
        return list(parts.order_by("_finder_rank", "name", "pk")[:limit + 1])

    @staticmethod
    def _read_cursor(cursor, queries):
        if cursor is None:
            return None
        if not isinstance(cursor, str) or not cursor or len(cursor) > 4096 or len(queries) != 1:
            raise ValueError("A page cursor requires exactly one search query")
        try:
            page = signing.loads(cursor, salt=CURSOR_SALT, max_age=CURSOR_MAX_AGE)
        except signing.BadSignature as exc:
            raise ValueError("This search page expired or is invalid. Search again to refresh the matches.") from exc
        if (not isinstance(page, dict) or page.get("query") != queries[0] or type(page.get("rank")) is not int
                or not 0 <= page["rank"] <= 3 or not isinstance(page.get("name"), str) or len(page["name"]) > 1024
                or type(page.get("id")) is not int or not 1 <= page["id"] <= (1 << 63) - 1):
            raise ValueError("This search page does not match the requested query. Search again.")
        return page

    def _availability(self, items) -> dict:
        """Summarize physically in-stock quantities; allocations are not deducted."""
        total = Decimal(0)
        locations = {}
        stock_items = 0
        for item in items:
            if not self.locator.stock_item_in_stock(item):
                continue
            quantity = Decimal(str(item.quantity))
            total += quantity
            stock_items += 1
            key = item.location_id
            if key not in locations:
                info = self.locator.get_location_info(item.location) if item.location else None
                targets, reason = {}, "StockItem has no assigned StockLocation"
                if item.location:
                    try:
                        targets = self.locator.get_location_led_plan(item.location)["controller_leds"]
                        reason = ""
                    except ValueError as exc:
                        reason = str(exc)
                locations[key] = {
                    "location": info, "stock_items": 0, "_quantity": Decimal(0),
                    "can_locate": bool(targets), "reason": reason, "controller_leds": targets,
                }
            locations[key]["stock_items"] += 1
            locations[key]["_quantity"] += quantity
        for location in locations.values():
            location["in_stock_quantity"] = self.locator.format_quantity(location.pop("_quantity"))
        return {
            "in_stock_quantity": self.locator.format_quantity(total),
            "stock_items": stock_items,
            "locations": list(locations.values()),
        }

    def search(self, queries, *, limit=5, cursor=None) -> dict:
        queries, limit = validate_queries(queries, limit)
        after = self._read_cursor(cursor, queries)
        searches, unique_parts, cached_queries = [], {}, {}
        for query in queries:
            if query not in cached_queries:
                cached_queries[query] = self._find_candidates(query, limit, after)
            found = cached_queries[query]
            matches = found[:limit]
            for part in matches:
                unique_parts[part.pk] = part
            searches.append((query, matches, len(found) > limit))

        stocks = defaultdict(list)
        if unique_parts:
            # Use InvenTree's native availability filter; no stock consumption,
            # reservation, or custom interpretation of stock status codes.
            for item in StockItem.objects.filter(
                StockItem.IN_STOCK_FILTER, part_id__in=unique_parts,
            ).select_related("part", "location").order_by("pk"):
                stocks[item.part_id].append(item)
        candidates = {
            pk: {
                "part": {
                    **self.locator.get_part_info(part), "IPN": part.IPN or "", "description": part.description,
                    **part_image_urls(part),
                },
                "availability": self._availability(stocks[pk]),
            }
            for pk, part in unique_parts.items()
        }
        results = []
        for query, matches, has_more in searches:
            results.append({
                "query": query,
                "matches": [candidates[part.pk] for part in matches],
                "has_more": has_more,
                "next_cursor": signing.dumps({"query": query, "rank": matches[-1]._finder_rank,
                                              "name": matches[-1].name, "id": matches[-1].pk}, salt=CURSOR_SALT) if has_more else None,
                "value_match": ({"quantity": value.kind, "value": str(value.value), "unit": SPECS[value.kind]["symbol"],
                                 "display": value.display} if (value := parse_value_search(query)) else None),
                "match_status": "multiple" if after or len(matches) > 1 or has_more else "single" if matches else "no_match",
            })
        return {"results": results, "summary": {
            "queries": len(results), "matched_queries": sum(bool(row["matches"]) for row in results),
            "candidate_parts": len(candidates),
        }}

    def preview(self, part_ids) -> dict:
        part_ids = validate_part_ids(part_ids)
        parts = {part.pk: part for part in Part.objects.filter(pk__in=part_ids)}
        stocks = defaultdict(list)
        if parts:
            items = StockItem.objects.filter(part_id__in=parts).annotate(
                _wled_finder_in_stock=Case(
                    When(StockItem.IN_STOCK_FILTER, then=Value(True)),
                    default=Value(False), output_field=BooleanField(),
                ),
            ).select_related("part", "location").order_by("pk")
            for item in items:
                stocks[item.part_id].append(item)

        targets, previews, missing = IndicatorCollection(), [], []
        location_ids = set()
        for pk in part_ids:
            if pk not in parts:
                missing.append(pk)
                continue
            preview = self.locator.preview_part_stock(parts[pk], (item for item in stocks[pk] if item.location_id))
            targets.extend(preview["indicators"])
            location_ids.update(row["location"]["id"] for row in preview["locations"])
            previews.append({
                **preview, "can_locate": bool(preview["indicators"]),
                "availability": self._availability(stocks[pk]),
            })

        return {
            "part_ids": part_ids, "parts": previews, "missing_part_ids": missing,
            "can_locate": not missing and all(part["can_locate"] for part in previews),
            "leds": targets.leds, "indicators": targets.indicators, "controller_leds": targets.controller_leds,
            "summary": {
                "selected_parts": len(part_ids), "found_parts": len(previews),
                "locatable_parts": sum(part["can_locate"] for part in previews),
                "unique_locations": len(location_ids), "unique_leds": len(targets.indicators),
            },
        }

    def locate(self, part_ids) -> dict:
        # Resolve fresh IDs instead of accepting controller/LED targets supplied
        # by the browser or a future speech interpreter.
        self.locator.invalidate_plans()
        plan = self.preview(part_ids)
        if not plan["can_locate"]:
            raise SelectionNotLocatable(plan)
        return {**plan, "wled": self.plugin.locator().apply_controller_leds(plan["controller_leds"])}
