"""Django views for WLED Locator Plus."""

from __future__ import annotations

import json
from functools import wraps

from django.core.exceptions import RequestDataTooBig
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from build.models import Build
from part.models import Part
from stock.models import StockItem, StockLocation

from .finder import SelectionNotLocatable
from .bom import ComponentsNotLocatable
from .picking import PickingChanged
from .dashboard import (
    DashboardConflict,
    build_dashboard,
    locate_dashboard_locations,
    positive_integer,
    preview_mapping,
    save_mapping,
    validate_saved_index,
)
from .finder_page import render_finder_page
from .locking import LocatorBusyError
from .operations import scoped_operation
from .page import render_index_page
from .wled import WledRequestError
from .speech import AUDIO_TYPES, MAX_AUDIO_BYTES, SpeechError, get_config, save_config, transcribe
from . import request_interpreter


def native_post(method):
    """Protect native-panel mutations while keeping their existing URL/results."""
    @method_decorator(csrf_protect)
    @wraps(method)
    def wrapped(self, request, *args, **kwargs):
        action = method.__name__.replace("_", "-")
        permission_error = self.require_superuser(request, action)
        if permission_error:
            return permission_error
        if request.method != "POST":
            response = self.json_error(action, "POST required", status=405)
            response["Allow"] = "POST"
            return response
        return method(self, request, *args, **kwargs)
    return wrapped


class PluginViews:
    """URL callbacks for the plugin."""

    def __init__(self, plugin):
        self.plugin = plugin

    def urls(self):
        """Return plugin URL patterns."""
        return [
            path("", self.index, name="index"),
            path("dashboard/data/", self.dashboard_data, name="dashboard-data"),
            path("dashboard/action/", self.dashboard_action, name="dashboard-action"),
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
            path("test/leds/<str:leds>/", self.test_leds, name="test-leds"),
            path("test/<str:controller>/leds/<str:leds>/", self.test_leds_controller, name="test-leds-controller"),
            path("test/<int:led>/", self.test_led, name="test-led"),
            path("test/<str:controller>/<int:led>/", self.test_led_controller, name="test-led-controller"),
            path(
                "register/location/<int:location_id>/led/<int:led>/",
                self.register_location_led,
                name="register-location-led",
            ),
            path(
                "register/location/<int:location_id>/leds/<str:leds>/",
                self.register_location_leds,
                name="register-location-leds",
            ),
            path(
                "register/location/<int:location_id>/controller/<str:controller>/led/<int:led>/",
                self.register_location_indicator,
                name="register-location-indicator",
            ),
            path(
                "register/location/<int:location_id>/controller/<str:controller>/leds/<str:leds>/",
                self.register_location_indicators,
                name="register-location-indicators",
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
            path("preview/location/<int:location_id>/", self.preview_location, name="preview-location"),
            path("preview/stock-item/<int:item_id>/", self.preview_stock_item, name="preview-stock-item"),
            path("preview/part/<int:part_id>/", self.preview_part, name="preview-part"),
            path("preview/build/<int:build_id>/", self.preview_build, name="preview-build"),
            path("finder/search/", self.finder_search, name="finder-search"),
            path("finder/transcribe/", self.finder_transcribe, name="finder-transcribe"),
            path("finder/interpret/", self.finder_interpret, name="finder-interpret"),
            path("speech/settings/", self.speech_settings, name="speech-settings"),
            path("interpreter/settings/", self.interpreter_settings, name="interpreter-settings"),
            path("finder/", self.finder_page, name="finder-page"),
            path("finder/preview/", self.finder_preview, name="finder-preview"),
            path("finder/locate/", self.finder_locate, name="finder-locate"),
            path("finder/off/", self.finder_off, name="finder-off"),
            path("components/part/<int:part_id>/preview/", self.component_preview, name="component-preview"),
            path("components/part/<int:part_id>/locate/", self.component_locate, name="component-locate"),
            path("components/build/<int:build_id>/preview/", self.build_component_preview, name="build-component-preview"),
            path("components/build/<int:build_id>/locate/", self.build_component_locate, name="build-component-locate"),
        ]

    def require_superuser(self, request, action: str = "permission"):
        """Return an error response unless the request user is a superuser."""
        if request.user.is_authenticated and request.user.is_superuser:
            return None

        return self.json_error(action, "Superuser permission required", status=403)

    def json_error(self, action: str, error: Exception | str, status: int = 500, **extra):
        """Return a consistent JSON error response."""
        busy = isinstance(error, LocatorBusyError) or error.__class__.__name__ == LocatorBusyError.__name__
        if busy:
            status = 503
            extra["code"] = "locator_busy"
        response = JsonResponse(
            {"success": False, "action": action, **extra, "error": str(error)},
            status=status,
        )
        if busy:
            response["Retry-After"] = "1"
        return response

    def json_request(self, request, action, callback):
        """Keep the new JSON API bounded, authenticated, and POST-only."""
        permission_error = self.require_superuser(request, action)
        if permission_error:
            return permission_error
        if request.method != "POST":
            response = self.json_error(action, "POST required", status=405)
            response["Allow"] = "POST"
            return response
        if request.content_type != "application/json":
            return self.json_error(action, "Content-Type must be application/json", status=415)
        try:
            if len(request.body) > 65536:
                return self.json_error(action, "Request body must not exceed 64 KiB", status=413)
            payload = json.loads(request.body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            result = callback(payload)
            return JsonResponse({"success": True, "action": action, **result})
        except PickingChanged as exc:
            return self.json_error(action, exc, status=409, code="picking_changed", preview=exc.plan)
        except ComponentsNotLocatable as exc:
            return self.json_error(action, exc, status=409, code="components_not_locatable", preview=exc.plan)
        except SelectionNotLocatable as exc:
            return self.json_error(action, exc, status=409, code="selection_not_locatable", preview=exc.plan)
        except DashboardConflict as exc:
            return self.json_error(action, exc, status=409, code="mapping_changed")
        except RequestDataTooBig:
            return self.json_error(action, "Request body must not exceed 64 KiB", status=413)
        except ValueError as exc:
            return self.json_error(action, exc, status=400)
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(action, exc, status=502, last_request=self.plugin.get_last_wled_request())
            return self.json_error(action, exc)

    @scoped_operation
    @method_decorator(ensure_csrf_cookie)
    def finder_page(self, request):
        """Open the typed part finder without loading stock or contacting WLED."""
        permission_error = self.require_superuser(request, "finder-page")
        if permission_error:
            return permission_error
        if request.method not in ("GET", "HEAD"):
            response = self.json_error("finder-page", "GET required", status=405)
            response["Allow"] = "GET, HEAD"
            return response
        return render_finder_page(request)

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_transcribe(self, request):
        """Accept a bounded raw audio body, separate from the existing JSON API."""
        action = "finder-transcribe"
        response = self.require_superuser(request, action)
        if response is None:
            if request.method != "POST":
                response = self.json_error(action, "POST required", status=405)
                response["Allow"] = "POST"
            else:
                try:
                    if request.headers.get("X-Speech-Language") not in (None, "en"):
                        raise SpeechError("Part Finder voice uses English only. Refresh the page.", 400, "speech_language")
                    if request.content_type not in AUDIO_TYPES:
                        raise SpeechError("Unsupported recording format. Try another browser.", 415, "speech_format")
                    length = request.META.get("CONTENT_LENGTH", "")
                    if length and (not length.isascii() or not length.isdigit() or len(length) > 20):
                        raise SpeechError("Invalid recording length.", 400, "speech_size")
                    if length and int(length) > MAX_AUDIO_BYTES:
                        raise SpeechError("The recording exceeds 4 MiB. Make a shorter recording.", 413, "speech_size")
                    audio = request.read(MAX_AUDIO_BYTES + 1)
                    result = transcribe(self.plugin, audio, request.content_type)
                    response = JsonResponse({"success": True, "action": action, **result})
                except SpeechError as exc:
                    response = self.json_error(action, exc, status=exc.status, code=exc.code)
                    if exc.code == "speech_busy":
                        response["Retry-After"] = "2"
                except (OSError, RequestDataTooBig):
                    response = self.json_error(action, "Could not read the recording. Try again.", status=400)
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_interpret(self, request):
        """Prepare reviewed English queries without reading stock or running search."""
        def prepare(payload):
            if set(payload) - {"text"}:
                raise ValueError("Supply English request text only")
            return request_interpreter.prepare_requests(self.plugin, payload.get("text"))
        response = self.json_request(request, "finder-interpret", prepare)
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def speech_settings(self, request):
        """Read/save speech configuration without contacting the speech service."""
        response = self.require_superuser(request, "speech-settings")
        if response is None:
            if request.method == "GET":
                response = JsonResponse({"success": True, "speech": get_config(self.plugin)})
            else:
                response = self.json_request(request, "speech-settings", lambda payload: {
                    "speech": save_config(self.plugin, payload),
                })
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def interpreter_settings(self, request):
        """Read/save the optional local parser without contacting either service."""
        response = self.require_superuser(request, "interpreter-settings")
        if response is None:
            if request.method == "GET":
                response = JsonResponse({"success": True, "interpreter": request_interpreter.get_config(self.plugin)})
            else:
                response = self.json_request(request, "interpreter-settings", lambda payload: {
                    "interpreter": request_interpreter.save_config(self.plugin, payload),
                })
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_search(self, request):
        """Return candidates and physical availability for separate part queries."""
        return self.json_request(request, "finder-search", lambda payload: self.plugin.search_parts(
            payload.get("queries"), limit=payload.get("limit", 5), cursor=payload.get("cursor"),
            component_queries=payload.get("component_queries"),
        ))

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_preview(self, request):
        """Preview explicitly selected parts without contacting controllers."""
        return self.json_request(request, "finder-preview", lambda payload: self.plugin.preview_parts(
            payload.get("part_ids"),
        ))

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_locate(self, request):
        """Resolve selected IDs again, then execute their combined target plan."""
        return self.json_request(request, "finder-locate", lambda payload: self.plugin.locate_parts(
            payload.get("part_ids"),
        ))

    @scoped_operation
    @method_decorator(csrf_protect)
    def finder_off(self, request):
        """Clear the locator system from the typed finder with a CSRF-protected POST."""
        return self.json_request(request, "finder-off", lambda payload: {"wled": self.plugin.off()})

    @scoped_operation
    @method_decorator(csrf_protect)
    def component_preview(self, request, part_id):
        response = self.json_request(request, "component-preview", lambda payload: self.plugin.preview_components(part_id, payload))
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def component_locate(self, request, part_id):
        response = self.json_request(request, "component-locate", lambda payload: self.plugin.locate_components(part_id, payload))
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def build_component_preview(self, request, build_id):
        response = self.json_request(request, "build-component-preview", lambda payload: self.plugin.preview_build_components(build_id, payload))
        response["Cache-Control"] = "no-store"
        return response

    @scoped_operation
    @method_decorator(csrf_protect)
    def build_component_locate(self, request, build_id):
        response = self.json_request(request, "build-component-locate", lambda payload: self.plugin.locate_build_components(build_id, payload))
        response["Cache-Control"] = "no-store"
        return response

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

    def parse_leds_path(self, leds: str) -> list[int]:
        """Return unique zero-based LED indexes from a comma-separated URL path."""
        raw = str(leds or "")
        if len(raw) > 4096 or len(raw.split(",")) > 512:
            raise ValueError("Enter at most 512 LED numbers")
        values = []

        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue

            if not item.isascii() or not item.isdigit():
                raise ValueError("LED numbers must be whole, non-negative indexes")
            led = int(item)

            if led not in values:
                values.append(led)

        if not values:
            raise ValueError("At least one LED index is required")

        return values

    @scoped_operation
    @method_decorator(ensure_csrf_cookie)
    def index(self, request):
        """Render the dashboard shell without inventory or controller access."""
        permission_error = self.require_superuser(request, "index")
        if permission_error:
            return permission_error
        if request.method not in {"GET", "HEAD"}:
            response = self.json_error("index", "GET required", status=405)
            response["Allow"] = "GET, HEAD"
            return response
        return render_index_page(self.plugin, request=request)

    @scoped_operation
    def dashboard_data(self, request):
        """Read the dashboard using saved configuration only."""
        permission_error = self.require_superuser(request, "dashboard-data")
        if permission_error:
            return permission_error
        if request.method != "GET":
            response = self.json_error("dashboard-data", "GET required", status=405)
            response["Allow"] = "GET"
            return response
        try:
            response = JsonResponse({"success": True, **build_dashboard(self.plugin, request.GET)})
            response["Cache-Control"] = "no-store"
            return response
        except ValueError as exc:
            return self.json_error("dashboard-data", exc, status=400)
        except Exception as exc:
            return self.json_error("dashboard-data", exc)

    @scoped_operation
    @method_decorator(csrf_protect)
    def dashboard_action(self, request):
        """Dashboard edits and hardware actions require an explicit JSON POST."""
        return self.json_request(request, "dashboard-action", self.run_dashboard_action)

    def run_dashboard_action(self, payload):
        command = payload.get("command")
        if command == "preview":
            review, _ = preview_mapping(self.plugin, payload)
            return {"review": review}
        if command == "save":
            return save_mapping(self.plugin, payload)
        if command == "off":
            return {"wled": self.plugin.off()}
        if command == "locate":
            return locate_dashboard_locations(self.plugin, payload)
        if command == "test":
            controller = payload.get("controller")
            if not isinstance(controller, str) or not controller:
                raise ValueError("Choose a controller")
            led = positive_integer(payload.get("led"), "LED number")
            validate_saved_index(self.plugin.wled(), led - 1, controller)
            with self.plugin.wled().execution():
                self.plugin.clear_all_controllers()
                return {"wled": self.plugin.set_led(led - 1, controller)}
        raise ValueError("Unknown dashboard action")

    @scoped_operation
    @native_post
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

    @scoped_operation
    def status(self, request):
        """Return current WLED Locator Plus configuration status."""
        permission_error = self.require_superuser(request, "status")
        if permission_error:
            return permission_error

        try:
            return JsonResponse({"success": True, **self.status_payload()})
        except Exception as exc:
            return self.json_error("status", exc)

    @scoped_operation
    def controllers(self, request):
        """Return configured WLED controller records for Plugin Configuration."""
        permission_error = self.require_superuser(request, "controllers")
        if permission_error:
            return permission_error

        try:
            return JsonResponse({"success": True, **self.controller_list_payload()})
        except Exception as exc:
            return self.json_error("controllers", exc)

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
    def test_led(self, request, led: int):
        """Clear all LEDs and light one test LED."""
        return self.test_led_for_controller(request, led, controller=None)

    @scoped_operation
    def test_led_controller(self, request, controller: str, led: int):
        """Clear and light one LED on a selected controller."""
        return self.test_led_for_controller(request, led, controller=controller)

    @scoped_operation
    def test_leds(self, request, leds: str):
        """Clear all LEDs and light multiple test LEDs."""
        return self.test_leds_for_controller(request, leds, controller=None)

    @scoped_operation
    def test_leds_controller(self, request, controller: str, leds: str):
        """Clear and light multiple LEDs on a selected controller."""
        return self.test_leds_for_controller(request, leds, controller=controller)

    def test_led_for_controller(self, request, led: int, controller: str | None):
        """Clear all LEDs and light one test LED."""
        return self.test_leds_for_controller(request, str(led), controller=controller)

    @native_post
    def test_leds_for_controller(self, request, leds: str, controller: str | None):
        """Clear all LEDs and light one or more test LEDs."""
        permission_error = self.require_superuser(request, "test")
        if permission_error:
            return permission_error

        try:
            led_values = [
                self.plugin.validate_led_index(led, controller)
                for led in self.parse_leds_path(leds)
            ]
            selected_controller = self.plugin.get_wled_controller(controller)
            with self.plugin.wled().execution():
                self.plugin.clear_all_controllers()
                result = self.plugin.set_leds(led_values, selected_controller["label"])
            return JsonResponse({
                "success": True,
                "action": "test",
                "controller": selected_controller["label"],
                "led": led_values[0],
                "leds": led_values,
                "indicators": [
                    {"controller": selected_controller["label"], "led": led}
                    for led in led_values
                ],
                "wled": result,
            })
        except ValueError as exc:
            return self.json_error("test", exc, status=400, controller=controller, leds=leds)
        except PermissionError as exc:
            return self.json_error("test", exc, status=403, controller=controller, leds=leds)
        except WledRequestError as exc:
            return self.json_error(
                "test",
                exc,
                status=502,
                controller=controller,
                leds=leds,
                last_request=self.plugin.get_last_wled_request(),
            )
        except Exception as exc:
            if self.is_wled_request_error(exc):
                return self.json_error(
                    "test",
                    exc,
                    status=502,
                    controller=controller,
                    leds=leds,
                    last_request=self.plugin.get_last_wled_request(),
                )
            return self.json_error("test", exc, controller=controller, leds=leds)

    @scoped_operation
    def register_location_led(self, request, location_id: int, led: int):
        """Register a StockLocation to a WLED LED index."""
        return self.register_location_indicator(request, location_id, led, controller=None)

    @scoped_operation
    def register_location_indicator(self, request, location_id: int, led: int, controller: str | None = None):
        """Register a StockLocation to a WLED controller and LED index."""
        return self.register_location_indicators(request, location_id, str(led), controller=controller)

    @scoped_operation
    def register_location_leds(self, request, location_id: int, leds: str):
        """Register a StockLocation to multiple WLED LED indexes."""
        return self.register_location_indicators(request, location_id, leds, controller=None)

    @scoped_operation
    @native_post
    def register_location_indicators(self, request, location_id: int, leds: str, controller: str | None = None):
        """Register a StockLocation to a WLED controller and one or more LED indexes."""
        permission_error = self.require_superuser(request, "register-location-led")
        if permission_error:
            return permission_error

        try:
            location = get_object_or_404(StockLocation, pk=location_id)
            indicator = self.plugin.set_location_indicators(
                location,
                self.parse_leds_path(leds),
                controller,
            )
            return JsonResponse({
                "success": True,
                "action": "register-location-led",
                "location": self.plugin.get_location_info(location),
                "controller": indicator["controller"],
                "led": indicator["led"],
                "leds": indicator["leds"],
                "indicators": indicator["indicators"],
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
                leds=leds,
            )
        except ValueError as exc:
            return self.json_error("register-location-led", exc, status=400, location_id=location_id, controller=controller, leds=leds)
        except PermissionError as exc:
            return self.json_error("register-location-led", exc, status=403, location_id=location_id, controller=controller, leds=leds)
        except Exception as exc:
            return self.json_error("register-location-led", exc, location_id=location_id, controller=controller, leds=leds)

    @scoped_operation
    @native_post
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

    @scoped_operation
    @native_post
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

    @scoped_operation
    @native_post
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

    @scoped_operation
    @native_post
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

    @scoped_operation
    @native_post
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

    @scoped_operation
    def preview_location(self, request, location_id: int):
        """Refresh a location mapping and readiness without changing LEDs."""
        permission_error = self.require_superuser(request, "preview-location")
        if permission_error:
            return permission_error
        if request.method != "GET":
            response = self.json_error("preview-location", "GET required", status=405)
            response["Allow"] = "GET"
            return response
        try:
            location = StockLocation.objects.get(pk=location_id)
        except StockLocation.DoesNotExist:
            return self.json_error("preview-location", "StockLocation not found", status=404)
        try:
            result = {"location": self.plugin.get_location_info(location), "has_children": not location.is_leaf_node(),
                      "child_count": location.get_descendant_count(), "can_locate": False, "reason": "", "leds": [], "indicators": []}
            try:
                plan = self.plugin.locator().get_location_led_plan(location)
                result.update(plan, can_locate=bool(plan["indicators"]))
            except ValueError as exc:
                result["reason"] = str(exc)
            response = JsonResponse({"success": True, "action": "preview-location", **result})
            response["Cache-Control"] = "no-store"
            return response
        except Exception as exc:
            return self.json_error("preview-location", exc)

    @scoped_operation
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
            result["mapping_editable"] = item.location is not None and item.location.is_leaf_node()
            return JsonResponse({"success": True, "action": "preview-stock-item", **result})
        except Exception as exc:
            return self.json_error("preview-stock-item", exc, item_id=item_id)

    @scoped_operation
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

    @scoped_operation
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

    @scoped_operation
    @native_post
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
