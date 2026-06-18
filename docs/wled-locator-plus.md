# WLED Locator Plus Context

## Purpose

`WLED Locator Plus` is a private InvenTree plugin for locating stored electronic components with WLED LED controllers.

The core flow is:

```text
Part / StockItem / StockLocation -> StockLocation metadata -> WLED controller + LED index
```

The plugin does not replace InvenTree stock management. InvenTree remains the source of truth for Parts, StockItems, and StockLocations. The plugin only stores the LED mapping needed to physically locate a StockLocation.

## Current Stack

The project uses:

* InvenTree running from the local Docker deployment.
* A local InvenTree plugin package in `inventree-data/plugins/inventree_wled_locator_plus/`.
* Django views and InvenTree plugin mixins: `UrlsMixin`, `LocateMixin`, and `UserInterfaceMixin`.
* StockLocation metadata for LED assignments.
* Internal plugin settings for WLED controller configuration.
* Plain JavaScript static files with no frontend build step.
* WLED JSON endpoints:
  * `/json/info` for read-only sync.
  * `/json/state` for test, locate, clear, and off actions.

No plugin database migrations, external Python packages, PyPI packaging, CI, pytest setup, or frontend build tools are currently used.

## Transfer Unit

The plugin is intended to move as one folder:

```text
inventree-data/plugins/inventree_wled_locator_plus/
```

Optional handoff documentation lives in:

```text
docs/wled-locator-plus.md
```

Do not copy unrelated InvenTree project files when transferring only the plugin. In particular, do not copy `Caddyfile`, `.env`, Docker volumes, generated static files, database files, or unrelated Markdown notes unless the server migration specifically requires them.

Exclude generated cache directories:

```text
__pycache__/
```

Important transfer distinction:

* Copying the plugin folder transfers plugin code only.
* WLED controller records live in InvenTree plugin settings.
* LED assignments live in InvenTree StockLocation metadata.
* If the InvenTree database is migrated, settings and mappings should move with it.
* If installing into a fresh InvenTree database, WLED controllers and StockLocation LED mappings must be recreated.

## Architecture

Runtime configuration is stored in internal plugin settings:

```text
_WLED_CONTROLLERS
_CLEAR_COLOR
_REQUEST_TIMEOUT
```

StockLocation mapping data is stored in one metadata key:

```text
StockLocation.metadata["wled_indicator"] = {"controller": "<label>", "led": <zero_based_index>}
```

There is no separate LED-only metadata key. Do not reintroduce `wled_led` or similar legacy mapping data.

Locate flow:

```text
UI action or InvenTree locate API
-> plugin view or LocateMixin method
-> LocatorService resolves mapped StockLocations
-> LEDs are grouped by WLED controller
-> all configured WLED controllers are cleared
-> only the target LEDs are lit
```

All configured WLED controllers act as one locator system. More controllers can be added without a fixed controller limit.

LED numbering rule:

* UI displays LED numbers as 1-based for humans.
* WLED and stored metadata use zero-based indexes.

StockLocation rule:

* Leaf StockLocations can receive direct LED assignments.
* Parent StockLocations are locate-only containers and should not receive direct LED assignments.
* Locating a parent StockLocation lights mapped child locations.

## User Interfaces

### Plugin Configuration

Plugin Configuration is the normal setup surface for WLED controllers and maintenance actions.

Supported setup flow:

1. Add a WLED controller label and address.
2. Click Sync to read WLED `/json/info`.
3. If sync fails, manually enter LED count and marker color.
4. Save the controller.

Plugin Configuration also manages:

* Clear color.
* WLED request timeout.
* Controller deletion.
* Mapping summary.
* Controller-wide mapping reassign that preserves LED numbers.
* Confirmed mapping clear.

The generic InvenTree Plugin Settings rows are intentionally not used for normal WLED setup.

### Native InvenTree Panels

Native panels are registered on:

* Part pages.
* Build Order pages.
* StockItem pages.
* StockLocation pages.

The panels can preview, locate, test, assign, or clear mappings depending on the object type. Actions display concise human-readable results instead of raw JSON dumps.

### External Dashboard

The dashboard is available at:

```text
/plugin/wled-locator-plus/
```

It is a plain plugin-rendered HTML page for overview and maintenance. It supports:

* Filtering by WLED controller, parent StockLocation, search text, state, and LED number.
* A full LED map for every configured WLED controller.
* Used/free/conflict counts per controller.
* Conflict detection.
* Stocked-without-LED detection.
* Single-location locate actions.
* Filtered locate.
* Selected-row locate.
* Selected-row reassign to any WLED and Start LED.
* Selected-row clear with browser confirmation.

The normal InvenTree main navigation entry is disabled because InvenTree's React frontend routes plugin links under `/web/` in a way that breaks direct backend plugin pages. Use the direct dashboard URL, the Spotlight action, or the `Open Indicator Dashboard` button in native plugin panels.

## Implemented Behavior

Current implemented features:

* Multiple WLED controllers with no hard-coded controller limit.
* WLED controller Sync from `/json/info`.
* Manual fallback for WLED LED count when Sync is unavailable.
* Marker color per WLED controller.
* Global clear color and request timeout.
* StockLocation mapping to a controller label and LED index.
* Clear mapping for a StockLocation.
* Locate Part by lighting mapped locations for available StockItems.
* Locate Build Order by lighting mapped locations for allocated StockItems.
* Locate StockItem through its StockLocation.
* Locate leaf or parent StockLocation.
* Clear all controllers before locate/test so stale LEDs are not left on other controllers.
* Clear all controllers when a locate target cannot be resolved.
* Dashboard filters and maintenance tools for larger inventories.
* Concise UI messages instead of raw WLED JSON output.

## Decisions Already Made

Keep these decisions unless the user explicitly changes direction:

* Keep plugin code inside `inventree_wled_locator_plus/`.
* Keep transferable plugin documentation under `docs/`.
* Leave the original top-level `README.md` untouched.
* Do not create top-level milestone or feature Markdown files.
* Use StockLocation metadata instead of adding database migrations.
* Use internal plugin settings instead of generic Plugin Settings rows.
* Do not hard-code WLED addresses or LED counts in code.
* Do not set a fixed number of WLED controllers.
* Keep controller setup in Plugin Configuration.
* Keep StockLocation assignment in native InvenTree panels.
* Keep the dashboard as an overview and bulk-maintenance surface.
* Keep hardware writes behind explicit user actions.
* Do not introduce external dependencies or build tooling without approval.

There is still an internal `primary` or default-controller flag in the WLED client for compatibility and default panel selection. It is not exposed as a user workflow and should not be expanded into one.

## Problems Solved

The current implementation already resolved these project issues:

* Replaced single-controller assumptions with controller-aware mappings.
* Removed the fixed controller limit.
* Removed separate LED-only mapping metadata from the active design.
* Moved WLED setup into one custom Plugin Configuration UI.
* Added Sync plus manual fallback for controller LED count.
* Replaced raw JSON UI output with concise summaries.
* Added clear mapping actions.
* Fixed stale LED behavior by clearing all controllers before locate/test and on locate failures.
* Added a dashboard for filtering, conflicts, stocked-without-LED checks, and bulk actions.
* Kept plugin transfer simple by containing code in the plugin package and documentation in `docs/`.

## Known Limitations

Current limitations and risks:

* Plugin URLs require an authenticated InvenTree superuser session.
* The external dashboard is plain plugin-rendered HTML, not part of the InvenTree React frontend.
* A normal InvenTree main navigation item for the dashboard is not reliable without changing InvenTree frontend/core or proxy behavior.
* WLED Sync depends on network access to the controller; manual LED count exists as fallback.
* Live test, locate, clear, and off actions write to real WLED hardware.
* Runtime may recreate `__pycache__/`; exclude it from transferred plugin packages.
* There is no dedicated automated regression test suite yet.
* Plugin Configuration controller-wide reassign preserves existing LED numbers. Use the dashboard selected-row reassign when moving locations to arbitrary target LEDs.

## File Map

Plugin code:

```text
inventree-data/plugins/inventree_wled_locator_plus/
```

Main files:

```text
plugin.py      # plugin class, internal settings, URLs, native panels, locate wrappers
views.py       # Django endpoints for controllers, mappings, locate, preview, test, clear
wled.py        # WLED validation and /json/info, /json/state HTTP requests
locator.py     # Part, Build, StockItem, StockLocation lookup and locate planning
mapping.py     # StockLocation metadata read/write helpers for wled_indicator
dashboard.py   # dashboard filtering, row construction, usage/conflict summaries
page.py        # plain HTML external dashboard renderer
constants.py   # shared constants and internal setting keys
```

Static UI files:

```text
static/admin_settings.js                   # Plugin Configuration WLED setup and mapping tools
static/panel_common.js                     # shared native-panel helpers
static/locator_panel.js                    # Part and Build panels
static/stock_item_panel.js                 # StockItem panel
static/stock_location_indicator_panel.js   # StockLocation panel
static/locator_actions.js                  # Spotlight actions
```

## Installation On Another InvenTree Instance

For a plugin-only install:

1. Copy `inventree-data/plugins/inventree_wled_locator_plus/` to the target InvenTree plugin directory.
2. Exclude `__pycache__/`.
3. Restart the InvenTree server and worker.
4. Enable `WLED Locator Plus` in InvenTree if it is not active.
5. Open Plugin Configuration and add or verify WLED controllers.
6. Recreate StockLocation LED mappings if the InvenTree database was not migrated.
7. Open `/plugin/wled-locator-plus/` and verify that the dashboard loads.
8. Test one safe LED only when ready to intentionally write to WLED hardware.

Example archive command from the current host:

```bash
tar --exclude='__pycache__' -czf wled-locator-plus-plugin.tar.gz -C /home/denys/inventree/inventree-data/plugins inventree_wled_locator_plus
```

## Useful Verification

For code changes, use checks that do not write generated files into the plugin package:

```bash
PYTHONPYCACHEPREFIX=/tmp/inventree-wled-pycache python3 -m py_compile /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/*.py
```

Check JavaScript syntax:

```bash
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/admin_settings.js
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/panel_common.js
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/locator_actions.js
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/locator_panel.js
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/stock_item_panel.js
node --check /home/denys/inventree/inventree-data/plugins/inventree_wled_locator_plus/static/stock_location_indicator_panel.js
```

After plugin code changes, restart:

```bash
cd /home/denys/inventree
docker compose restart inventree-server inventree-worker
```

Do not run live WLED state-changing tests unless the user approves that specific action.

## Next Work

Recommended next steps:

1. Prepare transfer validation.
   Package the plugin folder, install it on a separate InvenTree instance, confirm the plugin loads, then verify controller setup and dashboard rendering. This proves the copy-paste deployment model before adding larger features.

2. Add focused regression checks.
   Keep them lightweight. Useful targets are mapping metadata parsing, dashboard row generation, LED display conversion, controller validation, and locate planning. Avoid introducing a full test framework unless approved.

3. Design LLM integration.
   The preferred safe model is for the LLM or voice layer to talk only to InvenTree APIs, not directly to WLED, the database, or plugin code. The LLM should search for candidate Parts, StockItems, or StockLocations, present or confirm the best match, then call InvenTree's locate API for `wled-locator-plus`.

   Example target flow:

   ```text
   Voice: "Find 10k resistor"
   Speech-to-text: converts voice to text
   LLM/search layer: searches InvenTree for matching Part or StockItem
   Confirmation: user confirms the intended result when ambiguous
   InvenTree API: calls locate for the selected item or location
   Plugin: clears all configured WLED controllers, then lights the mapped LEDs
   ```

   n8n can simplify orchestration, but a small custom API service is also viable. Either approach should keep credentials outside the LLM prompt and restrict the LLM to search and locate actions.

4. Improve dashboard refresh behavior after bulk edits.
   Current selected-row actions update the visible table immediately. A later refinement could refresh LED map colors and controller counts without a full page reload.
