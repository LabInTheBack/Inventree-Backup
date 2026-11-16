"""Export assembly previews from disposable ORM fixtures; no InvenTree startup."""

import json
import sys
from pathlib import Path
from django.test import override_settings

from test_queries import DatabaseQueryTests


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    case = DatabaseQueryTests()
    case.setUpClass()
    try:
        case.setUp()
        root, board, missing = case.assembly_fixture()
        case.Bom.objects.create(part=root, sub_part=missing, optional=True, reference="Optional accessory")
        case.Part.objects.filter(pk=case.part.pk).update(image="parts/chip.png")
        previews = {}
        for quantity in (1, 3):
            for expand in (False, True):
                for optional in (False, True):
                    key = f"{quantity}-{int(expand)}-{int(optional)}"
                    with override_settings(MEDIA_URL="/media/"):
                        previews[key] = case.bom_module.BomService(case.plugin).preview(root.pk, {
                            "quantity": quantity, "expand": expand, "include_optional": optional,
                        })
        context = {"part_id": root.pk, "csrf_token": "a" * 64,
                   "picking_storage_key": f"wled-locator-plus.picking.v1.user.1.part.{root.pk}",
                   "preview_url": f"/plugin/wled-locator-plus/components/part/{root.pk}/preview/",
                   "locate_url": f"/plugin/wled-locator-plus/components/part/{root.pk}/locate/",
                   "off_url": "/plugin/wled-locator-plus/finder/off/"}
        build, child, line, _ = case.build_fixture()
        allocated_location = case.Location.objects.create(name="Allocated stock", pathstring="Allocated stock", metadata={"wled_indicator": {"controller": "B", "led": 27}})
        stock = case.Stock.objects.create(part=case.part, location=allocated_location, quantity=3)
        case.Allocation.objects.create(build_line=line, stock_item=stock, quantity=3)
        with override_settings(MEDIA_URL="/media/"):
            build_previews = {str(int(include)): case.build_module.BuildComponentService(case.plugin).preview(build.pk, {"include_subbuilds": include}) for include in (False, True)}
        build_context = {"build_id": build.pk, "csrf_token": "a" * 64,
                         "picking_storage_key": f"wled-locator-plus.picking.v1.user.1.build.{build.pk}",
                         "preview_url": f"/plugin/wled-locator-plus/components/build/{build.pk}/preview/",
                         "locate_url": f"/plugin/wled-locator-plus/components/build/{build.pk}/locate/",
                         "off_url": "/plugin/wled-locator-plus/finder/off/"}
        (destination / "fixtures.json").write_text(json.dumps({"context": context, "previews": previews,
            "build_context": build_context, "build_previews": build_previews}, default=str))
        print("Exported assembly previews from disposable in-memory inventory")
    finally:
        case.doCleanups()
        case.tearDownClass()


if __name__ == "__main__":
    render(Path(sys.argv[1]))
