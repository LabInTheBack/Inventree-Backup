"""Django views for WLED Locator Plus."""

from __future__ import annotations

import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path

from build.models import Build
from part.models import Part
from stock.models import StockItem, StockLocation

from .page import render_index_page
from .wled import WledRequestError


class PluginViews:
    """URL callbacks for the plugin."""

    def __init__(self, plugin):
        self.plugin = plugin

    def urls(self):
        """Return plugin URL patterns."""
        return [
            path("", self.index, name="index"),
            path("status/", self.status, name="status"),
            path("controllers/", self.controllers, name="controllers"),
            path("controllers/sync/", self.sync_controller, name="sync-controller"),
            path("controllers/save/", self.save_controller, name="save-controller"),
            path("controllers/delete/", self.delete_controller, name="delete-controller"),
            path("controllers/settings/", self.controller_settings, name="controller-settings"),
            path("controllers/mappings/", self.controller_mappings, name="controller-mappings"),
            path("controllers/mappings/reassign/", self.reassign_mappings, name="reassign-mappings"),
            path("controllers/mappings/clear/", self.clear_mappings, name="clear-mappings"),
            path("off/", self.off, name="off"),
            path("test/<int:led>/", self.test_led, name="test-led"),
            path("test/<str:controller>/<int:led>/", self.test_led_controller, name="test-led-controller"),
            path(
                "register/location/<int:location_id>/led/<int:led>/",
                self.register_location_led,
                name="register-location-led",
            ),
            path(
                "register/location/<int:location_id>/controller/<str:controller>/led/<int:led>/",
                self.register_location_indicator,
                name="register-location-indicator",
            ),
            path(
                "register/location/<int:location_id>/clear/",
                self.clear_location_indicator,
                name="clear-location-indicator",
            ),
            path("locate/location/<int:location_id>/", self.locate_location, name="locate-location"),
            path("locate/locations/", self.locate_locations, name="locate-locations"),
            path("locate/stock-item/<int:item_id>/", self.locate_stock_item, name="locate-stock-item"),
            path("locate/part/<int:part_id>/", self.locate_part, name="locate-part"),
            path("locate/build/<int:build_id>/", self.locate_build, name="locate-build"),
            path("preview/stock-item/<int:item_id>/", self.preview_stock_item, name="preview-stock-item"),
            path("preview/part/<int:part_id>/", self.preview_part, name="preview-part"),
            path("preview/build/<int:build_id>/", self.preview_build, name="preview-build"),
        ]

    def require_superuser(self, request, action: str = "permission"):
        """Return an error response unless the request user is a superuser."""
        if request.user.is_authenticated and request.user.is_superuser:
            return None

        return self.json_error(action, "Superuser permission required", status=403)

    def json_error(self, action: str, error: Exception | str, status: int = 500, **extra):
        """Return a consistent JSON error response."""
        return JsonResponse(
            {"success": False, "action": action, **extra, "error": str(error)},
            status=status,
        )

    def request_payload(self, request) -> dict:
        """Return request data from JSON or form-encoded input."""
        if request.content_type == "application/json":
            try:
                return json.loads(request.body.decode("utf-8") or "{}")
            except ValueError as exc:
                raise ValueError("Request body must be valid JSON") from exc

        return request.POST.dict()

    def is_wled_request_error(self, error: Exception) -> bool:
        """Return True for WLED request failures across plugin import namespaces."""
        return error.__class__.__name__ == WledRequestError.__name__

    def controller_list_payload(self) -> dict:
        """Return configured controller records without contacting WLED."""
        controllers = []

        for controller in self.plugin.get_wled_controllers(include_info=False):
            controllers.append({
                "label": controller["label"],
                "address": controller["address"],
                "max_leds": controller.get("max_leds") or "",
                "max_leds_source": controller.get("max_leds_source"),
                "marker_color": controller.get("marker_color"),
                "name": controller.get("name") or "",
                "version": controller.get("version") or "",
            })

        return {
            "controllers": controllers,
            "options": self.plugin.get_admin_options(),
            "count": len(controllers),
        }

    def status_payload(self) -> dict:
        """Return current plugin diagnostics."""
        controllers = []
        default_max_leds = None
        default_error = ""

        for controller in self.plugin.get_wled_controllers(include_info=False):
            item = {
                "label": controller["label"],
                "address": controller["address"],
                "configured_max_leds": controller.get("max_leds"),
                "max_leds_source": controller.get("max_leds_source"),
                "marker_color": controller.get("marker_color"),
                "name": controller.get("name"),
                "version": controller.get("version"),
            }

            try:
                info = self.plugin.get_wled_info(controller["label"])
                item["reachable"] = True
                item["max_leds"] = info.get("leds", {}).get("count") or controller.get("max_leds")
                item["max_leds_source"] = "wled_info" if info.get("leds", {}).get("count") else item["max_leds_source"]
                item["name"] = info.get("name")
                item["version"] = info.get("ver")
            except Exception as exc:
                item["reachable"] = False
                item["max_leds"] = controller.get("max_leds")
                item["error"] = str(exc)

            controllers.append(item)

        try:
            default_max_leds = self.plugin.get_max_leds()
        except Exception as exc:
            default_error = str(exc)

        return {
            "plugin_active": True,
            "wled": {
                "address": None,
                "max_leds": default_max_leds,
                "error": default_error,
                "clear_color": self.plugin.get_setting(
                    "CLEAR_COLOR",
                    backup_value="000000",
                ),
                "request_timeout": self.plugin.get_timeout(),
            },
            "controllers": controllers,
            "last_request": self.plugin.get_last_wled_request(),
        }

    def bool_payload_value(self, value) -> bool:
        """Return a bool from a JSON/form payload value."""
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def index(self, request):
        """Render the simple WLED Locator Plus plugin page."""
        permission_error = self.require_superuser(request, "index")
        if permission_error:
            return permission_error

        try:
            message = self.run_page_action(request)
            return render_index_page(self.plugin, request=request, message=message)
        except Exception as exc:
            return render_index_page(self.plugin, request=request, error=str(exc))

    def run_page_action(self, request) -> dict | None:
        """Run a simple action from the plugin page query parameters."""
        action = request.GET.get("action", "").strip()

        if not action:
            return None

        if action == "off":
            return {"label": "Off", "result": self.plugin.off()}

        if action == "test":
            controller = request.GET.get("controller", "").strip() or None
            if request.GET.get("led_display", "").strip():
                led = int(request.GET.get("led_display", "")) - 1
            else:
                led = int(request.GET.get("led", ""))
            led = self.plugin.validate_led_index(led, controller)
            selected_controller = self.plugin.get_wled_controller(controller)
            self.plugin.clear_all_controllers()
            return {
                "label": f"Test {selected_controller['label']} LED {led}",
                "result": self.plugin.set_led(led, selected_controller["label"]),
            }

        if action == "locate":
            location_id = int(request.GET.get("location_id", ""))
            location = get_object_or_404(StockLocation, pk=location_id)
            return {"label": f"Locate location {location_id}", "result": self.plugin.locate_location(location)}

        if action == "locate_multi":
            location_ids = self.plugin.parse_location_ids(request.GET.get("ids", ""))
            return {"label": "Locate multiple locations", "result": self.plugin.locate_locations(location_ids)}

        if action == "locate_stock_item":
            item_id = int(request.GET.get("item_id", ""))
            item = get_object_or_404(StockItem.objects.select_related("part", "location"), pk=item_id)
            return {"label": f"Locate stock item {item_id}", "result": self.plugin.locate_stock_item_object(item)}

        if action == "locate_part":
            part_id = int(request.GET.get("part_id", ""))
            part = get_object_or_404(Part, pk=part_id)
            return {"label": f"Locate part {part_id}", "result": self.plugin.locate_part_object(part)}

        if action == "locate_build":
            build_id = int(request.GET.get("build_id", ""))
            build = get_object_or_404(Build, pk=build_id)
            return {"label": f"Locate build {build_id}", "result": self.plugin.locate_build_object(build)}

        raise ValueError(f"Unknown action: {action}")

    def off(self, request):
        """Clear all WLED LEDs."""
        permission_error = self.require_superuser(request, "off")
        if permission_error:
            return permission_error

        try:
            result = self.plugin.off()
            return JsonResponse({"success": True, "action": "off", "wled": result})
        except PermissionError as exc:
            return self.json_error("off", exc, status=403)
        except WledRequestError as exc:
            return self.json_error("off", exc, status=502, last_request=self.plugin.get_last_wled_request())
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "off",
                    exc,
                    status=502,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("off", exc)

    def status(self, request):
        """Return current WLED Locator Plus configuration status."""
        permission_error = self.require_superuser(request, "status")
        if permission_error:
            return permission_error

        try:
            return JsonResponse({"success": True, **self.status_payload()})
        except Exception as exc:
            return self.json_error("status", exc)

    def controllers(self, request):
        """Return configured WLED controller records for Plugin Configuration."""
        permission_error = self.require_superuser(request, "controllers")
        if permission_error:
            return permission_error

        try:
            return JsonResponse({"success": True, **self.controller_list_payload()})
        except Exception as exc:
            return self.json_error("controllers", exc)

    def controller_settings(self, request):
        """Return or update non-controller options for Plugin Configuration."""
        permission_error = self.require_superuser(request, "controller-settings")
        if permission_error:
            return permission_error

        try:
            if request.method == "GET":
                return JsonResponse({
                    "success": True,
                    "action": "controller-settings",
                    "options": self.plugin.get_admin_options(),
                    **self.controller_list_payload(),
                })

            if request.method != "POST":
                return self.json_error("controller-settings", "GET or POST required", status=405)

            payload = self.request_payload(request)
            options = self.plugin.save_admin_options(
                clear_color=payload.get("clear_color", "000000"),
                request_timeout=int(payload.get("request_timeout", 3)),
            )
            return JsonResponse({
                "success": True,
                "action": "controller-settings",
                "options": options,
                **self.controller_list_payload(),
            })
        except Exception as exc:
            return self.json_error("controller-settings", exc, status=400)

    def controller_mappings(self, request):
        """Return WLED StockLocation mapping summary for Plugin Configuration."""
        permission_error = self.require_superuser(request, "controller-mappings")
        if permission_error:
            return permission_error

        if request.method != "GET":
            return self.json_error("controller-mappings", "GET required", status=405)

        try:
            return JsonResponse({
                "success": True,
                "action": "controller-mappings",
                "mappings": self.plugin.get_mapping_summary(),
                **self.controller_list_payload(),
            })
        except Exception as exc:
            return self.json_error("controller-mappings", exc)

    def reassign_mappings(self, request):
        """Reassign StockLocation mappings to another controller without lighting LEDs."""
        permission_error = self.require_superuser(request, "reassign-mappings")
        if permission_error:
            return permission_error

        if request.method != "POST":
            return self.json_error("reassign-mappings", "POST required", status=405)

        try:
            payload = self.request_payload(request)
            result = self.plugin.reassign_location_mappings(
                source_controller=payload.get("source_controller", ""),
                target_controller=payload.get("target_controller", ""),
            )
            return JsonResponse({
                "success": True,
                "action": "reassign-mappings",
                "result": result,
                "mappings": self.plugin.get_mapping_summary(),
                **self.controller_list_payload(),
            })
        except ValueError as exc:
            return self.json_error("reassign-mappings", exc, status=400)
        except Exception as exc:
            return self.json_error("reassign-mappings", exc)

    def clear_mappings(self, request):
        """Clear StockLocation WLED mapping metadata after explicit confirmation."""
        permission_error = self.require_superuser(request, "clear-mappings")
        if permission_error:
            return permission_error

        if request.method != "POST":
            return self.json_error("clear-mappings", "POST required", status=405)

        try:
            payload = self.request_payload(request)
            if not self.bool_payload_value(payload.get("confirm", False)):
                return self.json_error(
                    "clear-mappings",
                    "Confirmation is required",
                    status=400,
                )

            result = self.plugin.clear_location_mappings(
                source_controller=payload.get("source_controller", "all"),
            )
            return JsonResponse({
                "success": True,
                "action": "clear-mappings",
                "result": result,
                "mappings": self.plugin.get_mapping_summary(),
                **self.controller_list_payload(),
            })
        except Exception as exc:
            return self.json_error("clear-mappings", exc)

    def sync_controller(self, request):
        """Sync one controller from WLED /json/info and save it."""
        permission_error = self.require_superuser(request, "sync-controller")
        if permission_error:
            return permission_error

        if request.method != "POST":
            return self.json_error("sync-controller", "POST required", status=405)

        try:
            payload = self.request_payload(request)
            controller = self.plugin.sync_wled_controller(
                label=payload.get("label", ""),
                address=payload.get("address", ""),
                marker_color=payload.get("marker_color", ""),
            )
            return JsonResponse({
                "success": True,
                "action": "sync-controller",
                "controller": controller,
                **self.controller_list_payload(),
            })
        except ValueError as exc:
            return self.json_error("sync-controller", exc, status=400)
        except WledRequestError as exc:
            return self.json_error(
                "sync-controller",
                exc,
                status=502,
                last_request=self.plugin.get_last_wled_request(),
                manual_fallback=True,
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "sync-controller",
                    exc,
                    status=502,
                    last_request=self.plugin.get_last_wled_request(),
                    manual_fallback=True,
                )
            return self.json_error("sync-controller", exc)

    def save_controller(self, request):
        """Save one WLED controller from manual input."""
        permission_error = self.require_superuser(request, "save-controller")
        if permission_error:
            return permission_error

        if request.method != "POST":
            return self.json_error("save-controller", "POST required", status=405)

        try:
            payload = self.request_payload(request)
            controller = self.plugin.save_wled_controller(
                label=payload.get("label", ""),
                address=payload.get("address", ""),
                max_leds=int(payload.get("max_leds", "")),
                marker_color=payload.get("marker_color", ""),
            )
            return JsonResponse({
                "success": True,
                "action": "save-controller",
                "controller": controller,
                **self.controller_list_payload(),
            })
        except (TypeError, ValueError) as exc:
            return self.json_error("save-controller", exc, status=400)
        except Exception as exc:
            return self.json_error("save-controller", exc)

    def delete_controller(self, request):
        """Delete one configured WLED controller."""
        permission_error = self.require_superuser(request, "delete-controller")
        if permission_error:
            return permission_error

        if request.method != "POST":
            return self.json_error("delete-controller", "POST required", status=405)

        try:
            payload = self.request_payload(request)
            self.plugin.delete_wled_controller(payload.get("label", ""))
            return JsonResponse({
                "success": True,
                "action": "delete-controller",
                **self.controller_list_payload(),
            })
        except ValueError as exc:
            return self.json_error("delete-controller", exc, status=400)
        except Exception as exc:
            return self.json_error("delete-controller", exc)

    def test_led(self, request, led: int):
        """Clear all LEDs and light one test LED."""
        return self.test_led_for_controller(request, led, controller=None)

    def test_led_controller(self, request, controller: str, led: int):
        """Clear and light one LED on a selected controller."""
        return self.test_led_for_controller(request, led, controller=controller)

    def test_led_for_controller(self, request, led: int, controller: str | None):
        """Clear all LEDs and light one test LED."""
        permission_error = self.require_superuser(request, "test")
        if permission_error:
            return permission_error

        try:
            led = self.plugin.validate_led_index(led, controller)
            selected_controller = self.plugin.get_wled_controller(controller)
            self.plugin.clear_all_controllers()
            result = self.plugin.set_led(led, selected_controller["label"])
            return JsonResponse({
                "success": True,
                "action": "test",
                "controller": selected_controller["label"],
                "led": led,
                "wled": result,
            })
        except ValueError as exc:
            return self.json_error("test", exc, status=400, controller=controller, led=led)
        except PermissionError as exc:
            return self.json_error("test", exc, status=403, controller=controller, led=led)
        except WledRequestError as exc:
            return self.json_error(
                "test",
                exc,
                status=502,
                controller=controller,
                led=led,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "test",
                    exc,
                    status=502,
                    controller=controller,
                    led=led,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("test", exc, controller=controller, led=led)

    def register_location_led(self, request, location_id: int, led: int):
        """Register a StockLocation to a WLED LED index."""
        return self.register_location_indicator(request, location_id, led, controller=None)

    def register_location_indicator(self, request, location_id: int, led: int, controller: str | None = None):
        """Register a StockLocation to a WLED controller and LED index."""
        permission_error = self.require_superuser(request, "register-location-led")
        if permission_error:
            return permission_error

        try:
            location = get_object_or_404(StockLocation, pk=location_id)
            indicator = self.plugin.set_location_indicator(location, led, controller)
            return JsonResponse({
                "success": True,
                "action": "register-location-led",
                "location": self.plugin.get_location_info(location),
                "controller": indicator["controller"],
                "led": indicator["led"],
                "indicator": indicator,
                "metadata": {"wled_indicator": indicator},
            })
        except Http404:
            return self.json_error(
                "register-location-led",
                "StockLocation not found",
                status=404,
                location_id=location_id,
                controller=controller,
                led=led,
            )
        except ValueError as exc:
            return self.json_error("register-location-led", exc, status=400, location_id=location_id, controller=controller, led=led)
        except PermissionError as exc:
            return self.json_error("register-location-led", exc, status=403, location_id=location_id, controller=controller, led=led)
        except Exception as exc:
            return self.json_error("register-location-led", exc, location_id=location_id, controller=controller, led=led)

    def clear_location_indicator(self, request, location_id: int):
        """Remove WLED mapping metadata from a StockLocation."""
        permission_error = self.require_superuser(request, "clear-location-indicator")
        if permission_error:
            return permission_error

        try:
            location = get_object_or_404(StockLocation, pk=location_id)
            result = self.plugin.clear_location_indicator(location)
            return JsonResponse({
                "success": True,
                "action": "clear-location-indicator",
                **result,
                "metadata": {"wled_indicator": None},
            })
        except Http404:
            return self.json_error(
                "clear-location-indicator",
                "StockLocation not found",
                status=404,
                location_id=location_id,
            )
        except ValueError as exc:
            return self.json_error(
                "clear-location-indicator",
                exc,
                status=400,
                location_id=location_id,
            )
        except Exception as exc:
            return self.json_error("clear-location-indicator", exc, location_id=location_id)

    def locate_location(self, request, location_id: int):
        """Locate a StockLocation by lighting its mapped WLED LED."""
        permission_error = self.require_superuser(request, "locate-location")
        if permission_error:
            return permission_error

        try:
            location = get_object_or_404(StockLocation, pk=location_id)
            result = self.plugin.locate_location(location)
            return JsonResponse({"success": True, "action": "locate-location", **result})
        except Http404:
            return self.json_error(
                "locate-location",
                "StockLocation not found",
                status=404,
                location_id=location_id,
            )
        except ValueError as exc:
            return self.json_error("locate-location", exc, status=400, location_id=location_id)
        except PermissionError as exc:
            return self.json_error("locate-location", exc, status=403, location_id=location_id)
        except WledRequestError as exc:
            return self.json_error(
                "locate-location",
                exc,
                status=502,
                location_id=location_id,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "locate-location",
                    exc,
                    status=502,
                    location_id=location_id,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("locate-location", exc, location_id=location_id)

    def locate_stock_item(self, request, item_id: int):
        """Locate a StockItem by lighting its StockLocation LED."""
        permission_error = self.require_superuser(request, "locate-stock-item")
        if permission_error:
            return permission_error

        try:
            item = StockItem.objects.select_related("part", "location").get(pk=item_id)
        except StockItem.DoesNotExist:
            return self.json_error("locate-stock-item", "StockItem not found", status=404, item_id=item_id)

        try:
            result = self.plugin.locate_stock_item_object(item)
            return JsonResponse({"success": True, "action": "locate-stock-item", **result})
        except ValueError as exc:
            return self.json_error("locate-stock-item", exc, status=400, item_id=item_id)
        except PermissionError as exc:
            return self.json_error("locate-stock-item", exc, status=403, item_id=item_id)
        except WledRequestError as exc:
            return self.json_error(
                "locate-stock-item",
                exc,
                status=502,
                item_id=item_id,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "locate-stock-item",
                    exc,
                    status=502,
                    item_id=item_id,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("locate-stock-item", exc, item_id=item_id)

    def locate_part(self, request, part_id: int):
        """Locate a Part by lighting LEDs for available StockItems."""
        permission_error = self.require_superuser(request, "locate-part")
        if permission_error:
            return permission_error

        try:
            part = Part.objects.get(pk=part_id)
        except Part.DoesNotExist:
            return self.json_error("locate-part", "Part not found", status=404, part_id=part_id)

        try:
            result = self.plugin.locate_part_object(part)
            return JsonResponse({"success": True, "action": "locate-part", **result})
        except ValueError as exc:
            return self.json_error("locate-part", exc, status=400, part_id=part_id)
        except PermissionError as exc:
            return self.json_error("locate-part", exc, status=403, part_id=part_id)
        except WledRequestError as exc:
            return self.json_error(
                "locate-part",
                exc,
                status=502,
                part_id=part_id,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "locate-part",
                    exc,
                    status=502,
                    part_id=part_id,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("locate-part", exc, part_id=part_id)

    def locate_build(self, request, build_id: int):
        """Locate a Build by lighting LEDs for allocated StockItems."""
        permission_error = self.require_superuser(request, "locate-build")
        if permission_error:
            return permission_error

        try:
            build = Build.objects.get(pk=build_id)
        except Build.DoesNotExist:
            return self.json_error("locate-build", "Build not found", status=404, build_id=build_id)

        try:
            result = self.plugin.locate_build_object(build)
            return JsonResponse({"success": True, "action": "locate-build", **result})
        except ValueError as exc:
            return self.json_error("locate-build", exc, status=400, build_id=build_id)
        except PermissionError as exc:
            return self.json_error("locate-build", exc, status=403, build_id=build_id)
        except WledRequestError as exc:
            return self.json_error(
                "locate-build",
                exc,
                status=502,
                build_id=build_id,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "locate-build",
                    exc,
                    status=502,
                    build_id=build_id,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("locate-build", exc, build_id=build_id)

    def preview_stock_item(self, request, item_id: int):
        """Return the mapped StockLocation and LED for a StockItem without lighting LEDs."""
        permission_error = self.require_superuser(request, "preview-stock-item")
        if permission_error:
            return permission_error

        try:
            item = StockItem.objects.select_related("part", "location").get(pk=item_id)
        except StockItem.DoesNotExist:
            return self.json_error("preview-stock-item", "StockItem not found", status=404, item_id=item_id)

        try:
            result = self.plugin.preview_stock_item_object(item)
            return JsonResponse({"success": True, "action": "preview-stock-item", **result})
        except Exception as exc:
            return self.json_error("preview-stock-item", exc, item_id=item_id)

    def preview_part(self, request, part_id: int):
        """Return the mapped StockLocations and LEDs for a Part without lighting LEDs."""
        permission_error = self.require_superuser(request, "preview-part")
        if permission_error:
            return permission_error

        try:
            part = Part.objects.get(pk=part_id)
        except Part.DoesNotExist:
            return self.json_error("preview-part", "Part not found", status=404, part_id=part_id)

        try:
            result = self.plugin.preview_part_object(part)
            return JsonResponse({"success": True, "action": "preview-part", **result})
        except Exception as exc:
            return self.json_error("preview-part", exc, part_id=part_id)

    def preview_build(self, request, build_id: int):
        """Return the mapped StockLocations and LEDs for a Build without lighting LEDs."""
        permission_error = self.require_superuser(request, "preview-build")
        if permission_error:
            return permission_error

        try:
            build = Build.objects.get(pk=build_id)
        except Build.DoesNotExist:
            return self.json_error("preview-build", "Build not found", status=404, build_id=build_id)

        try:
            result = self.plugin.preview_build_object(build)
            return JsonResponse({"success": True, "action": "preview-build", **result})
        except Exception as exc:
            return self.json_error("preview-build", exc, build_id=build_id)

    def locate_locations(self, request):
        """Locate multiple StockLocations from a comma-separated ids query."""
        permission_error = self.require_superuser(request, "locate-locations")
        if permission_error:
            return permission_error

        ids_text = request.GET.get("ids", "")

        try:
            location_ids = self.plugin.parse_location_ids(ids_text)
            result = self.plugin.locate_locations(location_ids)
            return JsonResponse({"success": True, "action": "locate-locations", **result})
        except ValueError as exc:
            return self.json_error("locate-locations", exc, status=400, ids=ids_text)
        except PermissionError as exc:
            return self.json_error("locate-locations", exc, status=403, ids=ids_text)
        except WledRequestError as exc:
            return self.json_error(
                "locate-locations",
                exc,
                status=502,
                ids=ids_text,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "locate-locations",
                    exc,
                    status=502,
                    ids=ids_text,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("locate-locations", exc, ids=ids_text)
