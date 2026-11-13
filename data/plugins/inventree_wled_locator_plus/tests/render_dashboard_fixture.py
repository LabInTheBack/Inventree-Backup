"""Export actual dashboard HTML/data from an isolated in-memory ORM fixture."""

import json
import sys
from pathlib import Path

from test_facade import FacadeTests
from test_queries import DatabaseQueryTests
from support import modules


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    facade = FacadeTests()
    facade.setUp()
    try:
        views = facade.views.PluginViews(facade.plugin)
        response = views.index(facade.finder_request(method="GET"))
        (destination / "index.html").write_bytes(response.content)
    finally:
        facade.doCleanups()
    DatabaseQueryTests.setUpClass()
    case = DatabaseQueryTests()
    case.setUp()
    try:
        root = case.root
        for name, metadata, stocked in (
            ("Drawer 2", {"wled_indicator": {"controller": "A", "leds": [147]}}, False),
            ("Drawer 3", {}, True),
            ("Drawer 4", {"wled_indicator": {"controller": "A", "leds": [999]}}, False),
        ):
            location = case.Location.objects.create(name=name, pathstring=f"Root / {name}", parent=root, metadata=metadata)
            if stocked:
                part = case.Part.objects.create(name="10k resistor")
                case.Stock.objects.create(part=part, location=location)
        for index in range(5, 33):
            case.Location.objects.create(name=f"Spare drawer {index:02}", pathstring=f"Root / Spare drawer {index:02}", parent=root)
        with case.dashboard_models():
            first = modules.dashboard.build_dashboard(case.plugin, {})
            second = modules.dashboard.build_dashboard(case.plugin, {"page": "2"})
            tools = {label: [modules.dashboard.build_dashboard(case.plugin, {
                "view": "tools", "controller": label, "led_page": str(page),
            }) for page in (1, 2)] for label in ("A", "B")}
        (destination / "fixtures.json").write_text(json.dumps({
            "first": first, "second": second, "tools": tools,
        }))
        print("Exported dashboard HTML and isolated ORM snapshots")
    finally:
        case.doCleanups()
        DatabaseQueryTests.tearDownClass()


if __name__ == "__main__":
    render(Path(sys.argv[1]))
