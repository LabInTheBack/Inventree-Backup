# WLED Locator Plus

Private InvenTree addon in
[`data/plugins/inventree_wled_locator_plus/`](../data/plugins/inventree_wled_locator_plus/).
InvenTree owns inventory; the addon stores location-to-LED mappings and operates
the locator. See [warehouse.md](warehouse.md) for entry/storage rules and
[inventree-maintenance.md](inventree-maintenance.md) for deployment operations.

## User workflows

| Surface | Use |
|---|---|
| Part Finder: `/plugin/wled-locator-plus/finder/` | Search and locate several parts together. Frontend alias: `/web/plugin/wled-locator-plus/finder/`. |
| Location indicators: `/plugin/wled-locator-plus/` | Inspect/review/edit mappings and use controller tools. This is a maintenance dashboard. |
| Native Part / Build / StockItem / StockLocation panels | Preview, locate and edit mappings appropriate to that object. |
| Plugin Configuration | Add/sync controllers, set LED counts/colours/timeout and manage controller-wide mappings. |

Custom pages/endpoints require an authenticated superuser session. Use direct
links, Spotlight or native-panel dashboard buttons; normal frontend dashboard
navigation is not reliable. Backend pages also have registered `/web/` aliases.

### Find several parts

1. Enter one request per line or separate requests with semicolons, e.g.
   `NE555; 10k resistor; M3 nut`. Search with the button or Ctrl/Cmd+Enter.
2. Review each result group and its existing inventory images. **Load more**
   appends another page for that query. Nothing is selected automatically.
3. **Add** the desired matches. A part appears once in the selection even if
   several queries match it; further searches preserve the selection.
4. Wait for current stock/mapping checks, then **Locate selected**. Each selected
   part needs at least one usable mapped stock location. Other skipped locations
   remain warnings. The backend rechecks before operating hardware.
5. **All off** clears the locator. **Remove** and **Clear list** only edit the list.

Search covers active, non-virtual parts. Literal terms must each match name, IPN,
keywords, description or manufacturer MPN. Exact IPN/name/MPN rank first, followed
by stable name/ID order. This is not fuzzy or semantic search.

Value matching supports one unambiguous primary resistance, capacitance or
inductance per request: `10kΩ` = `10000 ohms`, `100nF` = `0.1uF`, `10uH` = `0.01mH`.
Resistor context permits `10k resistor`, `4k7 resistor`, `4R7 resistor` and `0R`;
unqualified `10k` stays literal. Prefix case matters (`M` mega, `m` milli).
The page displays the interpretation. Supported value text and existing numeric
`Resistance`/`Capacitance`/`Inductance` parameters are searched; unrelated
properties such as ESR are excluded. Structured values use base SI numeric
indexes with only float round-off allowance, not component tolerance.

Remaining terms still constrain text matches. Package, voltage, power and
tolerance are not general structured parameter filters. Unsupported values,
ranges, conflicting hints and multiple values in one query stay literal. This
normalization belongs to Part Finder, not InvenTree core search or the dashboard.

Availability uses native in-stock rules and assigned locations. Quantities are
physical stock, not unallocated availability; build allocations are not deducted
from finder totals. Missing locations/mappings are shown. Search reads stored
image URLs without downloading assets or regenerating thumbnails; failed images
fall back to the original or a placeholder.

### Selection recovery

The current account's selected IDs and exact search text are saved in this
browser's same-origin `localStorage`. Reopening/refreshing restores the list and
performs a fresh preview; Locate stays disabled until that check succeeds.
Missing parts remain removable. **Retry location check** handles read failures.
Restoration does not search, locate or clear lights; search again for result cards.

Only version, IDs and text are stored under
`wled-locator-plus.finder.v1.user.<user ID>`, without quantities, mappings,
credentials, images or action history. Clear list retains search text; clearing
both removes the saved record. Invalid records are discarded and unavailable
storage leaves in-page use working. Tabs keep separate working selections;
latest saved edits are restored, without live cross-tab or cross-device sync.

### Setup and mappings

In Plugin Configuration, add a controller label/address, **Sync** its
`/json/info`, or supply a manual LED count if unavailable. Save a marker colour;
clear colour and request timeout apply globally. Controller-wide reassign keeps
LED numbers; arbitrary remapping uses the dashboard's selected-row editor.

The dashboard filters/paginates locations and shows mapped/shared/unmapped/invalid
states. Review changes before saving; a stale review requires a new review.
Batch saves are atomic and update only the mapping metadata. Selection is limited
to the current page. Counts distinguish parts from stock records, not quantities.
Controller tools show saved usage, not live connectivity. Selecting an LED cell
does not operate it; **Test LED**, Locate and All off are explicit commands.

Native panels begin with a preview and offer retry on read failures. They refresh
after writes, validate whole-number LED inputs and lock controls during actions.
StockItem mapping controls follow its current checked location. Parent locations
are locate-only; assignment forms apply to leaves.

## Data and hardware behaviour

- Controllers/options live in database plugin settings `_WLED_CONTROLLERS`,
  `_CLEAR_COLOR`, `_REQUEST_TIMEOUT`; normal setup uses Plugin Configuration.
- Location metadata is `wled_indicator`, for example
  `{"controller":"cabinet","led":0,"leds":[0,1]}`. `led` is the first LED;
  `leds` supports multiple LEDs. Single-LED metadata remains readable.
- Display LEDs start at **1**; metadata, native URL indexes and WLED use **0**.
  Shared LEDs are legitimate, including split drawers and oversized shelf objects.
  Do not renumber or automatically "repair" sharing.
- Leaves have direct assignments. Locating a parent expands mapped descendant
  leaves. Parts use available StockItems; Builds use allocated stock.
- All configured controllers form one locator system. Locate/test clears the
  system once, then lights the deduplicated controller/LED union. Segment zero is
  normalized to span the strip before physical indexes are used.
- Finder/dashboard validate the whole selection before clearing. Native locate
  workflows retain their existing clear-on-unresolved behaviour. Failed hardware
  execution can leave partial results; success must not be inferred from a timeout.
- Search/finder preview/dashboard reads use saved counts and do not contact WLED.
  A missing count needs sync/manual setup. Native setup/single-object workflows
  can discover counts. WLED uses `/json/info` and `/json/state`.
- Hardware writes share a nonblocking Unix lock at
  `MEDIA_ROOT/.wled-locator-plus.lock` on the shared server/worker volume. Do not
  unlink it during operation. The OS releases the lock when its holder exits.

## Finder and dashboard APIs

Prefix: `/plugin/wled-locator-plus/`. JSON POSTs require a superuser session,
`Content-Type: application/json` and Django CSRF token in `X-CSRFToken`.
Pages/preview reads are not cached. Native mutation URLs also require protected
POST; old GET-based action links are rejected. Direct LocateMixin entrypoints
remain available to InvenTree.

| Endpoint | Request / purpose |
|---|---|
| POST `finder/search/` | `{"queries":["NE555","100nF capacitor"],"limit":5}`. Separate result groups, stock/images, `has_more`, `next_cursor`, `value_match`. |
| POST `finder/search/` with cursor | `{"queries":["NE555"],"cursor":"<returned cursor>"}`. One query, query-bound signed cursor, one-hour expiry. |
| POST `finder/preview/` | `{"part_ids":[12,34]}`. Current parts, missing IDs, availability and combined target plan. |
| POST `finder/locate/` | Same IDs; resolves fresh data and operates only a valid selection. IDs here are placeholders. |
| POST `finder/off/` | `{}`. Clear the locator system. |
| GET `dashboard/data/` | Filtered/paginated snapshot and mapping/controller usage. |
| POST `dashboard/action/` | Command `preview`, `save`, `locate`, `test` or `off`; mapping review/save includes revision validation. |
| GET `preview/location/<id>/` | Native location readiness; other native previews cover Parts, Builds and StockItems. |

Limits: 64 KiB JSON; 1–20 queries, 200 characters/12 terms each; default five,
maximum ten matches per query per page; 1–100 selected positive integer IDs.
Cursor paging uses `(rank,name,ID)` rather than OFFSET. Live catalog edits can
move results; the UI deduplicates and cancels superseded requests.

Errors include 400 validation, 403 authentication/CSRF, 405 method, 413 size,
415 media type, 409 stale/invalid selection, 502 WLED transport and 503
`locator_busy` with `Retry-After: 1`. Finder 409 includes
`code: selection_not_locatable` and corrective `preview`; dashboard conflicts use
`mapping_changed`. Responses use `success`, `action` and error/result fields.

## Source map

All paths below are relative to the plugin directory; no frontend build,
external runtime dependency or plugin database migration is required.

| Files | Responsibility |
|---|---|
| `__init__.py`, `plugin.py`, `constants.py` | Plugin registration, settings/facade, native panels, routes and shared identifiers. |
| `views.py` | Authenticated HTTP endpoints, validation and responses. |
| `wled.py`, `mapping.py`, `locator.py` | Controller transport/configuration, metadata helpers, inventory resolution and previews/plans. |
| `operations.py`, `planning.py`, `execution.py`, `locking.py` | Per-operation caches, ordered target union, hardware execution and cross-process serialization. |
| `finder.py`, `search_terms.py` | Search/availability/paging/selection and conservative value normalization. |
| `dashboard.py` | Mapping snapshots, sharing and reviewed transactional edits. |
| `page.py`, `finder_page.py` | Dashboard/finder rendering and CSRF bootstrap. |
| `templates/dashboard.html`, `templates/finder.html` | Page layouts. |
| `static/dashboard_page.js`, `static/dashboard_page.css` | Dashboard editor, filters and controller tools. |
| `static/finder_page.js`, `static/finder_page.css` | Search/results, images, selection recovery and locate controls. |
| `static/admin_settings.js` | Plugin Configuration UI. |
| `static/panel_common.js`, `static/locator_panel.js` | Shared native-panel helpers and Part/Build panels. |
| `static/stock_item_panel.js`, `static/stock_location_indicator_panel.js` | StockItem and StockLocation panels. |
| `static/locator_actions.js` | Spotlight/navigation actions. |
| `tests/support.py`, `tests/test_refactor.py`, `tests/test_facade.py` | Offline fixtures, backend regressions and protected callback checks. |
| `tests/test_queries.py`, `tests/test_search_terms.py`, `tests/test_locking.py` | Disposable ORM queries, value parsing and process locking. |
| `tests/render_{finder,dashboard,panels}_fixture.py` | Export synthetic browser fixtures. |
| `tests/browser_{finder,dashboard,panels}.py` | Optional Playwright checks with intercepted HTTP. |

## Development, activation and transfer

Run backend regressions with the container's installed dependencies:

```bash
cd /home/den/server-data/inventree
docker compose exec -T inventree-server python3 -B -m unittest discover \
  -s /home/inventree/data/plugins/inventree_wled_locator_plus/tests
```

Tests use fixture settings/inventory, mocked controller HTTP and disposable
in-memory ORM models, without initializing production InvenTree. Optional browser
checks use development-only Playwright/Chromium; export fixtures first, e.g.:

```bash
docker compose exec -T inventree-server python3 -B \
  /home/inventree/data/plugins/inventree_wled_locator_plus/tests/render_finder_fixture.py \
  /tmp/wled-finder-fixtures
docker cp inventree-server:/tmp/wled-finder-fixtures /tmp/
WLED_FINDER_FIXTURES=/tmp/wled-finder-fixtures python3 -B \
  data/plugins/inventree_wled_locator_plus/tests/browser_finder.py
```

Dashboard/panel exporters and browser scripts follow the same pattern. These
fixture checks do not prove physical controller/network behaviour; live hardware
tests require a specifically authorized action. Test results belong to the run,
not a permanently maintained milestone counter.

For authorized source deployment, restart server/worker to load Python changes.
Finder/dashboard scripts/styles are inline: refresh their pages. Native panels
and Plugin Configuration use collected static assets; startup updates normally
collect them in this deployment. If collection is needed explicitly, run
`docker compose exec -T inventree-server invoke static`, then hard-refresh the
browser. This task collects application/plugin assets, without compiling a
frontend by default. Documentation-only edits need none of these actions.

Transfer the whole `data/plugins/inventree_wled_locator_plus/` folder, excluding
`__pycache__`, into the destination's configured plugin directory. Include this
guide as handoff documentation, activate the plugin, load/collect its assets and
verify setup. Code transfer alone does not carry controller settings or location
mappings: they follow a database migration or must be configured in the new
database.

## Planned voice integration

Voice capture, transcription, spoken-number/request interpretation and general
structured parameter filters are not implemented. The proposed flow is browser
recording → authenticated addon backend → local speech service → editable text
and interpreted requests → existing finder/preview/explicit Locate.

Whisper is a pretrained speech recognition model. Speaches and whisper.cpp server
are alternative ways to host it. A separate conversational LLM is optional; speech
recognition alone does not query inventory or interpret every parameter. Choose
the service/model through actual component-value/identifier tests before full
integration. Local models can transcribe offline after initial downloads; the
browser still needs network access to InvenTree. No speech service has been
introduced by the addon changes documented here.
