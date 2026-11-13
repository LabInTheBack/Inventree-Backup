"""WLED Locator Plus plugin for InvenTree."""

from __future__ import annotations

from typing import Any

from django.db.utils import OperationalError, ProgrammingError
from django.middleware.csrf import get_token
from django.urls import path
from django.utils.translation import gettext_lazy as _

from build.models import Build
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, UrlsMixin, UserInterfaceMixin
from stock.models import StockLocation

from .constants import BASE_URL, INTERNAL_SETTING_KEYS, PLUGIN_SLUG
from .finder import FinderService
from .locator import LocatorService
from .operations import current_operation, scoped_operation
from .views import PluginViews
from .wled import WledClient


class WledLocatorPlus(
    UrlsMixin,
    LocateMixin,
    UserInterfaceMixin,
    InvenTreePlugin,
):
    """Locate stock locations using a WLED LED strip."""

    NAME = "WledLocatorPlus"
    SLUG = PLUGIN_SLUG
    TITLE = "WLED Locator Plus"
    DESCRIPTION = "Light WLED LEDs to locate InvenTree stock locations"
    VERSION = "0.1.0"
    AUTHOR = "Home Lab"
    ADMIN_SOURCE = "admin_settings.js"

    DEFAULT_SETTINGS = {
        "CLEAR_COLOR": "000000",
        "REQUEST_TIMEOUT": 3,
        "WLED_CONTROLLERS": "",
    }

    def setup_urls(self):
        """Return manual backend and page URLs for this plugin."""
        views = PluginViews(self)
        self._register_web_alias(views)
        return views.urls()

    def _register_web_alias(self, views):
        """Register the frontend-prefixed dashboard URL used by InvenTree nav."""
        try:
            from InvenTree import urls as root_urls
        except Exception:  # pragma: no cover
            return

        alias_names = {
            "wled-locator-plus-web-alias",
            "wled-locator-plus-web-alias-extra",
            "wled-locator-plus-web-finder",
        }
        root_urls.urlpatterns[:] = [
            pattern
            for pattern in root_urls.urlpatterns
            if getattr(pattern, "name", None) not in alias_names
        ]

        aliases = [
            path(
                "web/plugin/wled-locator-plus/",
                views.index,
                name="wled-locator-plus-web-alias",
            ),
            path(
                "web/plugin/wled-locator-plus/finder/",
                views.finder_page,
                name="wled-locator-plus-web-finder",
            ),
            path(
                "web/plugin/wled-locator-plus/<path:extra>",
                views.index,
                name="wled-locator-plus-web-alias-extra",
            ),
        ]

        insert_at = len(root_urls.urlpatterns)
        for index, pattern in enumerate(root_urls.urlpatterns):
            pattern_name = getattr(pattern, "name", None)
            pattern_route = str(getattr(pattern, "pattern", ""))
            if pattern_name in ("web", "web-wildcard", "index") or pattern_route == "web/":
                insert_at = index
                break

        root_urls.urlpatterns[insert_at:insert_at] = aliases

    def _plugin_config_object(self):
        """Return this plugin's database config row, if it is available."""
        from plugin.registry import registry

        try:
            return registry.get_plugin_config(self.plugin_slug(), self.plugin_name())
        except (OperationalError, ProgrammingError):  # pragma: no cover
            return None

    def _internal_setting_key(self, key: str) -> str:
        """Return the internal storage key for a logical plugin setting."""
        return INTERNAL_SETTING_KEYS.get(key, key)

    def _read_plugin_setting(self, key: str):
        """Read one raw plugin setting value without declaring generic settings."""
        from plugin.models import PluginSetting

        plugin_config = self._plugin_config_object()
        if not plugin_config:  # pragma: no cover
            return None

        setting = PluginSetting.objects.filter(plugin=plugin_config, key=key).first()
        return setting.value if setting else None

    def get_setting(
        self,
        key: str,
        cache: bool = False,
        backup_value: Any = None,
    ) -> Any:
        """Return an internal plugin setting value.

        The public generic Plugin Settings UI is intentionally not used for this
        plugin. Runtime options are stored only under internal underscore keys.
        """
        internal_key = self._internal_setting_key(key)
        current = current_operation(self)
        if current is None:
            value = self._read_plugin_setting(internal_key)
        else:
            if internal_key not in current.settings:
                current.settings[internal_key] = self._read_plugin_setting(internal_key)
            value = current.settings[internal_key]

        if value is None:
            value = self.DEFAULT_SETTINGS.get(key, backup_value)

        return backup_value if value is None else value

    def set_setting(self, key: str, value: Any, user=None, **kwargs) -> None:
        """Persist an internal plugin setting value."""
        from plugin.models import PluginSetting

        plugin_config = self._plugin_config_object()
        if not plugin_config:  # pragma: no cover
            return

        PluginSetting.set_setting(
            self._internal_setting_key(key),
            value,
            plugin=plugin_config,
        )
        current = current_operation(self)
        if current is not None:
            current.settings.pop(self._internal_setting_key(key), None)
            controllers_changed = self._internal_setting_key(key) == self._internal_setting_key("WLED_CONTROLLERS")
            if current.wled is not None and controllers_changed:
                current.wled.invalidate_configuration()
                if current.locator is not None:
                    current.locator.invalidate_plans()
                if current.finder is not None:
                    current.finder.locator.invalidate_plans()

    def get_admin_context(self):
        """Return context for the Plugin Configuration settings component."""
        return {
            "controllers_url": self.plugin_url("controllers/"),
            "sync_url": self.plugin_url("controllers/sync/"),
            "save_url": self.plugin_url("controllers/save/"),
            "delete_url": self.plugin_url("controllers/delete/"),
            "settings_url": self.plugin_url("controllers/settings/"),
            "mappings_url": self.plugin_url("controllers/mappings/"),
            "reassign_url": self.plugin_url("controllers/mappings/reassign/"),
            "clear_mappings_url": self.plugin_url("controllers/mappings/clear/"),
        }

    def get_ui_spotlight_actions(self, request, context, **kwargs):
        """Return external indicator quick actions for the InvenTree spotlight menu."""
        return [
            {
                "key": "wled-locator-open-page",
                "title": _("Open External Indicator"),
                "description": _("Open the WLED Locator Plus external indicator page"),
                "icon": "ti:bulb:outline",
                "source": self.plugin_static_file(
                    "locator_actions.js:openLocatorPage"
                ),
            },
            {
                "key": "wled-locator-open-context",
                "title": _("Open External Indicator"),
                "description": _("Open the external indicator panel for the current Part, StockItem, or StockLocation"),
                "icon": "ti:map-pin:outline",
                "source": self.plugin_static_file(
                    "locator_actions.js:openContextPanel"
                ),
            },
            {
                "key": "wled-locator-assign-led",
                "title": _("Assign External Indicator"),
                "description": _("Open the external indicator assignment panel for the current StockItem or StockLocation"),
                "icon": "ti:edit:outline",
                "source": self.plugin_static_file(
                    "locator_actions.js:assignStockItemLed"
                ),
            },
        ]

    def get_ui_navigation_items(self, request, context, **kwargs):
        """Return custom InvenTree navigation entries for the plugin page."""
        return []

    def plugin_url(self, path_suffix: str = "") -> str:
        """Return an absolute backend URL under the plugin URL prefix."""
        return f"{BASE_URL}{str(path_suffix or '').lstrip('/')}"

    @scoped_operation
    def panel_context(self, request=None, **overrides) -> dict:
        """Return shared native panel context."""
        return {
            "csrf_token": get_token(request) if request is not None else "",
            "plugin_page_url": BASE_URL,
            "register_location_url_base": self.plugin_url("register/location/"),
            "register_location_url_suffix": "/led/",
            "register_location_controller_url_base": self.plugin_url("register/location/"),
            "test_url_base": self.plugin_url("test/"),
            "test_controller_url_base": self.plugin_url("test/"),
            **self.get_controller_context(),
            **overrides,
        }

    def panel_definition(
        self,
        *,
        key: str,
        title,
        description,
        source: str,
        context: dict,
    ) -> dict:
        """Return one native InvenTree UI panel definition."""
        return {
            "key": key,
            "title": title,
            "description": description,
            "icon": "ti:bulb:outline",
            "source": source,
            "context": context,
        }

    @scoped_operation
    def get_ui_panels(self, request, context, **kwargs):
        """Return native InvenTree UI panels for supported object pages."""
        context = context or {}

        target_model = context.get("target_model")

        try:
            target_id = int(context.get("target_id"))
        except (TypeError, ValueError):
            return []

        if target_model == "part":
            return [self.panel_definition(
                key="assign-external-indicator-part",
                title=_("Assign External Indicator"),
                description=_("Locate this part using mapped external indicators"),
                source=self.plugin_static_file("locator_panel.js:renderPartPanel"),
                context=self.panel_context(
                    request=request,
                    part_id=target_id,
                    locate_url=self.plugin_url(f"locate/part/{target_id}/"),
                    preview_url=self.plugin_url(f"preview/part/{target_id}/"),
                ),
            )]

        if target_model == "build":
            build = Build.objects.filter(pk=target_id).first()
            build_label = build.reference if build else str(target_id)

            return [self.panel_definition(
                key="assign-external-indicator-build",
                title=_("Assign External Indicator"),
                description=_("Locate this build order using mapped external indicators for allocated stock"),
                source=self.plugin_static_file("locator_panel.js:renderBuildPanel"),
                context=self.panel_context(
                    request=request,
                    build_id=target_id,
                    build_label=build_label,
                    locate_url=self.plugin_url(f"locate/build/{target_id}/"),
                    preview_url=self.plugin_url(f"preview/build/{target_id}/"),
                ),
            )]

        if target_model == "stockitem":
            stock_item_context = self.panel_context(
                request=request,
                stock_item_id=target_id,
                locate_url=self.plugin_url(f"locate/stock-item/{target_id}/"),
                preview_url=self.plugin_url(f"preview/stock-item/{target_id}/"),
            )

            return [self.panel_definition(
                key="assign-external-indicator-stock-item",
                title=_("Assign External Indicator"),
                description=_("Locate this stock item or assign the external indicator for its stock location"),
                source=self.plugin_static_file("stock_item_panel.js:renderStockItemPanel"),
                context=stock_item_context,
            )]

        if target_model == "stocklocation":
            location = StockLocation.objects.filter(pk=target_id).first()
            current_led = None
            current_leds = []
            current_controller = None
            has_children = False
            child_count = 0

            if location:
                has_children = not location.is_leaf_node()
                child_count = location.get_descendant_count()
                if not has_children:
                    try:
                        indicator = self.locator().get_location_indicator(location)
                        current_led = indicator["led"]
                        current_leds = indicator["leds"]
                        current_controller = indicator["controller"]
                    except ValueError:
                        current_led = None
                        current_leds = []
                        current_controller = None

            location_context = self.panel_context(
                request=request,
                stock_location_id=target_id,
                preview_url=self.plugin_url(f"preview/location/{target_id}/"),
                locate_url=self.plugin_url(f"locate/location/{target_id}/"),
                register_url_base=self.plugin_url(
                    f"register/location/{target_id}/led/"
                ),
                register_controller_url_base=self.plugin_url(
                    f"register/location/{target_id}/controller/"
                ),
                current_led=current_led,
                current_leds=current_leds,
                current_controller=current_controller,
                has_children=has_children,
                child_count=child_count,
            )

            return [self.panel_definition(
                key="assign-external-indicator-stock-location",
                title=_("Assign External Indicator"),
                description=_("Locate this stock location or assign its external indicator"),
                source=self.plugin_static_file(
                    "stock_location_indicator_panel.js:renderStockLocationPanel"
                ),
                context=location_context,
            )]

        return []

    @scoped_operation
    def get_controller_context(self) -> dict:
        """Return JSON-safe WLED controller data for UI panels."""
        controllers = []
        default_label = ""
        default_max_led = 0

        for controller in self.get_wled_controllers(include_info=False):
            try:
                max_leds = self.get_controller_max_leds(controller["label"])
                reachable = True
            except Exception:
                max_leds = controller.get("max_leds") or 1
                reachable = False

            panel_max_led = max(0, int(max_leds) - 1)

            if not default_label or controller.get("primary"):
                default_label = controller["label"]
                default_max_led = panel_max_led

            controllers.append({
                "label": controller["label"],
                "max_led": panel_max_led,
                "reachable": reachable,
                "marker_color": controller.get("marker_color") or "FF0000",
            })

        return {
            "controllers": controllers,
            "multi_controller": len(controllers) > 1,
            "default_controller": default_label,
            "primary_controller": default_label,
            "max_led": default_max_led,
        }

    def wled(self) -> WledClient:
        """Share a client within an operation, never across requests."""
        current = current_operation(self)
        if current is None:
            return WledClient(self)
        if current.wled is None:
            current.wled = WledClient(self)
        return current.wled

    def locator(self) -> LocatorService:
        """Share location resolution within an operation."""
        current = current_operation(self)
        if current is None:
            return LocatorService(self)
        if current.locator is None:
            current.locator = LocatorService(self)
        return current.locator

    def finder(self) -> FinderService:
        """Share the finder only within its current request."""
        current = current_operation(self)
        if current is None:
            return FinderService(self)
        if current.finder is None:
            current.finder = FinderService(self)
        return current.finder

    @scoped_operation
    def search_parts(self, queries, *, limit=5, cursor=None) -> dict:
        return self.finder().search(queries, limit=limit, cursor=cursor)

    @scoped_operation
    def preview_parts(self, part_ids) -> dict:
        return self.finder().preview(part_ids)

    @scoped_operation
    def locate_parts(self, part_ids) -> dict:
        return self.finder().locate(part_ids)

    @scoped_operation
    def get_max_leds(self) -> int:
        return self.wled().get_max_leds()

    @scoped_operation
    def get_controller_max_leds(self, controller_label: str | None = None) -> int:
        return self.wled().get_controller_max_leds(controller_label)

    @scoped_operation
    def get_wled_controllers(self, include_info: bool = False) -> list[dict]:
        return self.wled().get_controllers(include_info=include_info)

    @scoped_operation
    def get_wled_controller(self, label: str | None = None) -> dict:
        return self.wled().get_controller(label)

    @scoped_operation
    def get_wled_info(self, controller_label: str | None = None) -> dict:
        return self.wled().get_info(controller_label)

    @scoped_operation
    def sync_wled_controller(
        self,
        label: str,
        address: str,
        marker_color: str | None = None,
        primary: bool = False,
    ) -> dict:
        """Read WLED info for an address and save the controller record."""
        client = self.wled()
        info = client.get_info_for_address(address)
        max_leds = info.get("leds", {}).get("count")

        if not isinstance(max_leds, int) or max_leds < 1:
            raise ValueError("WLED /json/info did not report a usable LED count")

        return client.upsert_controller({
            "label": label,
            "address": address,
            "marker_color": marker_color or "FF0000",
            "max_leds": max_leds,
            "name": info.get("name") or "",
            "version": info.get("ver") or "",
            "primary": primary,
        })

    @scoped_operation
    def save_wled_controller(
        self,
        label: str,
        address: str,
        max_leds: int,
        marker_color: str | None = None,
        primary: bool = False,
    ) -> dict:
        """Save a WLED controller record from manual form data."""
        return self.wled().upsert_controller({
            "label": label,
            "address": address,
            "max_leds": max_leds,
            "marker_color": marker_color or "FF0000",
            "primary": primary,
        })

    @scoped_operation
    def get_admin_options(self) -> dict:
        """Return non-controller options managed by Plugin Configuration."""
        return {
            "clear_color": self.get_setting("CLEAR_COLOR", backup_value="000000"),
            "request_timeout": int(
                self.get_setting("REQUEST_TIMEOUT", backup_value=3) or 3
            ),
        }

    @scoped_operation
    def save_admin_options(
        self,
        *,
        clear_color: str,
        request_timeout: int,
    ) -> dict:
        """Save non-controller options from Plugin Configuration."""
        from .wled import normalize_hex_color

        request_timeout = int(request_timeout)
        if request_timeout < 1:
            raise ValueError("Request timeout must be at least 1")

        self.set_setting("CLEAR_COLOR", normalize_hex_color(clear_color))
        self.set_setting("REQUEST_TIMEOUT", request_timeout)

        return self.get_admin_options()

    @scoped_operation
    def delete_wled_controller(self, label: str) -> list[dict]:
        """Delete a configured WLED controller."""
        return self.wled().delete_controller(label)

    @scoped_operation
    def get_timeout(self) -> int:
        return self.wled().get_timeout()

    @scoped_operation
    def validate_led_index(self, led_index: int, controller_label: str | None = None) -> int:
        return self.wled().validate_led_index(led_index, controller_label)

    @scoped_operation
    def post_wled_state(self, payload: dict, controller_label: str | None = None) -> dict:
        return self.wled().post_state(payload, controller_label=controller_label)

    @scoped_operation
    def get_last_wled_request(self) -> dict | None:
        return self.wled().get_last_request()

    @scoped_operation
    def clear_leds(self, controller_label: str | None = None) -> dict:
        return self.wled().clear_leds(controller_label)

    @scoped_operation
    def clear_all_controllers(self) -> dict:
        return self.wled().clear_all_controllers()

    @scoped_operation
    def set_led(self, led_index: int, controller_label: str | None = None) -> dict:
        return self.wled().set_led(led_index, controller_label)

    @scoped_operation
    def set_leds(self, led_indices: list[int], controller_label: str | None = None) -> dict:
        return self.wled().set_leds(led_indices, controller_label)

    @scoped_operation
    def off(self) -> dict:
        return self.wled().off()

    @scoped_operation
    def get_location_info(self, location) -> dict:
        return self.locator().get_location_info(location)

    @scoped_operation
    def get_stock_item_info(self, item) -> dict:
        return self.locator().get_stock_item_info(item)

    @scoped_operation
    def get_part_info(self, part) -> dict:
        return self.locator().get_part_info(part)

    @scoped_operation
    def get_build_info(self, build) -> dict:
        return self.locator().get_build_info(build)

    @scoped_operation
    def set_location_led(self, location, led: int) -> int:
        return self.locator().set_location_led(location, led)

    @scoped_operation
    def set_location_indicator(self, location, led: int, controller_label: str | None = None) -> dict:
        return self.locator().set_location_indicator(location, led, controller_label)

    @scoped_operation
    def set_location_indicators(self, location, leds: list[int], controller_label: str | None = None) -> dict:
        return self.locator().set_location_indicators(location, leds, controller_label)

    @scoped_operation
    def clear_location_indicator(self, location) -> dict:
        return self.locator().clear_location_indicator(location)

    @scoped_operation
    def get_location_led(self, location) -> int:
        return self.locator().get_location_led(location)

    @scoped_operation
    def locate_location(self, location) -> dict:
        return self.locator().locate_location(location)

    @scoped_operation
    def locate_stock_location(self, location_pk):
        return self.locator().locate_stock_location(location_pk)

    @scoped_operation
    def locate_stock_item_object(self, item) -> dict:
        return self.locator().locate_stock_item_object(item)

    @scoped_operation
    def preview_stock_item_object(self, item) -> dict:
        return self.locator().preview_stock_item_object(item)

    @scoped_operation
    def locate_stock_item(self, item_pk):
        return self.locator().locate_stock_item(item_pk)

    @scoped_operation
    def locate_part_object(self, part) -> dict:
        return self.locator().locate_part_object(part)

    @scoped_operation
    def preview_part_object(self, part) -> dict:
        return self.locator().preview_part_object(part)

    @scoped_operation
    def locate_build_object(self, build) -> dict:
        return self.locator().locate_build_object(build)

    @scoped_operation
    def preview_build_object(self, build) -> dict:
        return self.locator().preview_build_object(build)

    @scoped_operation
    def parse_location_ids(self, ids_text: str) -> list[int]:
        return self.locator().parse_location_ids(ids_text)

    @scoped_operation
    def locate_locations(self, location_ids: list[int]) -> dict:
        return self.locator().locate_locations(location_ids)

    @scoped_operation
    def get_mapped_locations(self) -> list[dict]:
        return self.locator().get_mapped_locations()

    @scoped_operation
    def get_mapping_summary(self) -> dict:
        return self.locator().get_mapping_summary()

    @scoped_operation
    def reassign_location_mappings(
        self,
        source_controller: str,
        target_controller: str,
    ) -> dict:
        return self.locator().reassign_location_mappings(
            source_controller,
            target_controller,
        )

    @scoped_operation
    def clear_location_mappings(
        self,
        source_controller: str = "all",
    ) -> dict:
        return self.locator().clear_location_mappings(source_controller)

    @scoped_operation
    def get_location_choices(self) -> list[dict]:
        return self.locator().get_location_choices()

    @scoped_operation
    def get_stock_item_choices(self) -> list[dict]:
        return self.locator().get_stock_item_choices()

    @scoped_operation
    def get_part_choices(self) -> list[dict]:
        return self.locator().get_part_choices()
