"""Export the real HTML and fixture-only preview responses for browser checks.

Run with the container's Python, passing a temporary output directory. This does
not initialize InvenTree or use its database. No controller requests are sent.
"""

import json
import sys
from pathlib import Path

from test_facade import FacadeTests


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    case = FacadeTests()
    case.setUp()
    try:
        views = case.views.PluginViews(case.plugin)
        response = views.finder_page(case.finder_request(method="GET"))
        (destination / "index.html").write_bytes(response.content)
        (destination / "finder_entry.js").write_text(
            (Path(__file__).parent.parent / "static" / "finder_entry.js").read_text())
        previews = {
            ",".join(map(str, ids)): {"success": True, "action": "finder-preview", **case.plugin.preview_parts(ids)}
            for ids in ([1], [2], [1, 2], [2, 1], [1, 999])
        }
        candidates = []
        for pk in (1, 2):
            part = previews[str(pk)]["parts"][0]
            candidates.append({
                "part": {
                    **part["part"], "IPN": "", "description": "Timer IC" if pk == 1 else "10k axial resistor",
                    "image_url": "/media/finder-fixture/chip.png" if pk == 1 else None,
                    "thumbnail_url": "/media/finder-fixture/chip.thumbnail.png" if pk == 1 else None,
                    "specifications": [
                        {"name": "Voltage", "value": "5", "units": "V"},
                        {"name": "Package / Case", "value": "DIP-8", "units": ""},
                    ] if pk == 1 else [{"name": "Resistance", "value": "10000", "units": "ohms"}],
                },
                "availability": part["availability"],
            })
        (destination / "fixtures.json").write_text(json.dumps({"candidates": candidates, "previews": previews}))
        print("Exported finder HTML and fixture responses")
    finally:
        case.doCleanups()


if __name__ == "__main__":
    render(Path(sys.argv[1]))
