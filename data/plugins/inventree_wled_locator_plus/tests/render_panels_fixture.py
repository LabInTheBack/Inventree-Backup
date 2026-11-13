"""Export native panel contexts and previews using offline inventory fixtures."""

import json
import sys
from pathlib import Path

from support import Build, Query
from test_facade import FacadeTests


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    case = FacadeTests()
    case.setUp()
    try:
        Build.objects = Query([case.fixture.build])
        views = case.views.PluginViews(case.plugin)
        contexts, previews = {}, {}
        for name, model, pk, callback in (
            ("part", "part", 1, views.preview_part), ("build", "build", 1, views.preview_build),
            ("stock", "stockitem", 1, views.preview_stock_item),
            ("location", "stocklocation", 1, views.preview_location),
            ("parent", "stocklocation", 6, views.preview_location),
        ):
            contexts[name] = case.plugin.get_ui_panels(case.finder_request(method="GET"), {"target_model": model, "target_id": pk})[0]
            previews[name] = json.loads(callback(case.finder_request(method="GET"), pk).content)
        (destination / "fixtures.json").write_text(json.dumps({"contexts": contexts, "previews": previews}, default=str))
        print("Exported fixture-only native panel contexts and previews")
    finally:
        case.doCleanups()


if __name__ == "__main__":
    render(Path(sys.argv[1]))
