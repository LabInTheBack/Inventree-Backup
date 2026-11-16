"""Offline fixtures: no InvenTree startup, database, or controller access."""

from __future__ import annotations

import importlib
import json
import sys
import types
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def attribute(obj, path):
    for name in path.split("__"):
        obj = getattr(obj, name)
    return obj


class Query:
    """Only the queryset operations used by these regression fixtures."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def select_related(self, *fields):
        return self

    def annotate(self, **expressions):
        if not self.rows:
            return self
        if set(expressions) != {"_wled_finder_in_stock"}:
            raise NotImplementedError(expressions)
        # Plain fixtures already carry their availability. The real SQL
        # expression and filter semantics are exercised in test_queries.py.
        for row in self.rows:
            row._wled_finder_in_stock = row.in_stock
        return self

    def filter(self, **filters):
        def matches(row):
            for key, value in filters.items():
                if key.endswith("__isnull"):
                    if (attribute(row, key[:-8]) is None) != value:
                        return False
                elif key.endswith("__in"):
                    if attribute(row, key[:-4]) not in value:
                        return False
                elif attribute(row, key) != value:
                    return False
            return True
        return Query(row for row in self.rows if matches(row))

    def order_by(self, *fields):
        return Query(sorted(self.rows, key=lambda row: tuple(attribute(row, key) for key in fields)))

    def exclude(self, **filters):
        excluded = self.filter(**filters).rows
        return Query(row for row in self.rows if row not in excluded)

    def values(self, *fields):
        return [{key: attribute(row, key) for key in fields} for row in self.rows]

    def values_list(self, field, flat=False):
        values = [attribute(row, field) for row in self.rows]
        return values if flat else [(value,) for value in values]

    def get(self, **filters):
        result = self.filter(**filters).rows
        if len(result) != 1:
            raise LookupError(filters)
        return result[0]

    def first(self):
        return self.rows[0] if self.rows else None

    def count(self):
        return len(self.rows)


class Location:
    objects = Query()
    DoesNotExist = LookupError

    def __init__(self, pk, name, controller=None, leds=None, children=()):
        self.pk, self.name, self.pathstring = pk, name, f"Cabinet / {name}"
        self.metadata = {"unrelated": {"keep": True}}
        if controller:
            self.metadata["wled_indicator"] = {"controller": controller, "leds": leds, "led": leds[0]}
        self.children = list(children)
        self.metadata_reads = 0
        self.child_checks = 0
        self.descendant_reads = 0
        self.saves = 0

    @property
    def has_children(self):
        self.child_checks += 1
        return bool(self.children)

    def is_leaf_node(self):
        return not self.children

    def get_descendant_count(self):
        return len(self.children)

    def get_descendants(self, include_self=False):
        self.descendant_reads += 1
        return Query(([self] if include_self else []) + self.children)

    def get_metadata(self, key, backup_value=None):
        self.metadata_reads += 1
        return self.metadata.get(key, backup_value)

    def save(self):
        self.saves += 1


class Part:
    objects = Query()

    def __init__(self, pk, name):
        self.pk, self.name, self.full_name = pk, name, name
        self.assembly = False

    def __str__(self):
        return self.name


class StockItem:
    objects = Query()
    DoesNotExist = LookupError

    def __init__(self, pk, part, location, quantity="2.000", in_stock=True):
        self.pk, self.part, self.location = pk, part, location
        self.part_id = part.pk
        self.location_id = location.pk if location else None
        self.quantity, self.in_stock = quantity, in_stock


class BuildItem:
    objects = Query()

    def __init__(self, pk, build, stock_item):
        self.pk, self.stock_item, self.quantity = pk, stock_item, "1.000"
        self.build_line_id = 1
        self.build_line = types.SimpleNamespace(build=build)


class Parameter:
    objects = Query()


class BomItem:
    objects = Query()


class ManufacturerPart:
    objects = Query()


class Build:
    def __init__(self, pk, part):
        self.pk, self.part, self.reference, self.title = pk, part, f"BO-{pk}", "Test build"


class BuildLine:
    objects = Query()


def module(name, **attributes):
    result = types.ModuleType(name)
    result.__dict__.update(attributes)
    return result


def load_modules(package="locator_under_test", directory=PLUGIN_DIR):
    """Load addon modules without executing the InvenTree plugin entrypoint."""
    package_module = module(package, __path__=[str(directory)])
    dependencies = {
        package: package_module,
        "build.models": module("build.models", Build=Build, BuildItem=BuildItem, BuildLine=BuildLine),
        "part.models": module("part.models", Part=Part, BomItem=BomItem),
        "stock.models": module("stock.models", StockItem=StockItem, StockLocation=Location),
    }
    with patch.dict(sys.modules, dependencies):
        loaded = types.SimpleNamespace(**{
            name: importlib.import_module(f"{package}.{name}")
            for name in ("wled", "mapping", "locator", "dashboard", "operations", "planning", "execution", "locking")
        })
    return loaded


modules = load_modules()


class FakePlugin:
    def __init__(self, controllers=None):
        if controllers is None:
            controllers = [
                {"label": "A", "address": "http://controller-a.invalid", "max_leds": 200, "primary": True},
                {"label": "B", "address": "http://controller-b.invalid", "max_leds": 60},
            ]
        self.settings = {
            "WLED_CONTROLLERS": json.dumps(controllers),
            "CLEAR_COLOR": "000000",
            "REQUEST_TIMEOUT": 3,
        }
        self.client = RecordingClient(self)

    def get_setting(self, key, backup_value=None):
        return self.settings.get(key, backup_value)

    def set_setting(self, key, value):
        self.settings[key] = value

    def wled(self):
        return self.client

    def locator(self):
        return modules.locator.LocatorService(self)

    def get_wled_controllers(self, include_info=False):
        return self.client.get_controllers(include_info)

    def validate_led_index(self, led, controller):
        return self.client.validate_led_index(led, controller)


class RecordingClient(modules.wled.WledClient):
    """Simulate WLED HTTP responses, recording every attempted operation."""

    def __init__(self, plugin):
        super().__init__(plugin)
        self.requests = []
        self.states = {}
        self.failures = set()

    def request_json(self, controller_label, path, payload=None, method="GET"):
        label = self.get_controller(controller_label)["label"]
        self.requests.append((label, method, path, deepcopy(payload)))
        if (label, method, path) in self.failures:
            raise modules.wled.WledRequestError("simulated offline controller")
        if path == "/json/info":
            return {"leds": {"count": 200}}
        if method == "GET":
            return deepcopy(self.states.get(label, {"seg": [{"id": 0, "start": 0, "stop": self.get_controller_max_leds(label)}]}))
        segments = payload.get("seg", [])
        if isinstance(segments, list) and segments and "start" in segments[0]:
            self.states[label] = {"seg": [deepcopy(segments[0])]}
        return {"success": True}


def inventory_fixture():
    part, other = Part(1, "NE555"), Part(2, "Resistor")
    first = Location(1, "Drawer 1", "A", [147, 148])
    shared = Location(2, "Drawer 2", "A", [147])
    second = Location(3, "Drawer 3", "B", [147 % 60])
    missing = Location(4, "Unmapped")
    invalid = Location(5, "Invalid", "A", [200])
    root = Location(6, "Parent", children=[first, shared, second, missing, invalid])
    items = [
        StockItem(1, part, first), StockItem(2, part, first),
        StockItem(3, part, shared), StockItem(4, part, second),
        StockItem(5, part, missing), StockItem(6, part, invalid),
        StockItem(7, part, first, in_stock=False), StockItem(8, part, None),
        StockItem(9, other, first),
    ]
    Location.objects = Query([first, shared, second, missing, invalid, root])
    StockItem.objects = Query(items)
    Part.objects = Query([part, other])
    build = Build(1, part)
    BuildItem.objects = Query([
        BuildItem(1, build, items[0]), BuildItem(2, build, items[1]),
        BuildItem(3, build, items[4]), BuildItem(4, build, items[7]),
        BuildItem(5, build, None),
    ])
    return types.SimpleNamespace(part=part, other=other, first=first, shared=shared, second=second,
                                 missing=missing, invalid=invalid, root=root, items=items, build=build)
