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

Custom pages/endpoints require an authenticated superuser session. **Part Finder**
is available in InvenTree's main navigation and Spotlight. An optional **Part
Finder** widget is available through the home dashboard's **Add widget** menu;
it opens Finder directly and is not added to saved dashboard layouts automatically.
The registered frontend route bridges SPA navigation to the standalone Finder.
Direct links and `/web/` aliases remain available.

### Finder workspace

Search and voice controls share one card. **Record request** captures English
audio; **Type or paste request** opens the same expandable review area without
using a microphone. Request/transcript and prepared search lines are shown beside
each other on wide screens and stacked on smaller screens. **Add to parts to
find** still adds reviewed lines before an explicit **Search parts** action.

**Clear searches** clears query text, results, interpreted-line modes, voice
drafts and last-request text. It cancels browser waits for searches, pagination,
transcription and interpretation, and ignores late replies. Selected parts remain
available and the empty search is saved for browser recovery. **Clear list**
separately removes selected parts. Neither clear action changes the lights.

Transcription and interpretation have separate elapsed-time badges. The badges
measure browser request time, including transport and service waits, and retain
the final duration after completion or failure. **Cancel request** stops waiting
and preserves an available transcript for editing; backend inference already
submitted may continue. No model or speech settings are changed by these controls.

Selected parts include images and current stock/location checks. The selection
stays alongside results on desktop and can be collapsed on mobile. Finder follows
the system light/dark preference. Workspace help is folded away, while recovery
problems automatically expand their message. Shared native-panel button/preview
styles and indicator-page spacing follow the same visual conventions.

Part names in matches and the selection open the native InvenTree part page in a
new tab. Thumbnails with an image open an accessible larger-image dialog; the
original image is requested on opening the preview, or when a thumbnail URL is
missing or its image fails to load. If the original fails, the dialog tries the thumbnail and
labels that fallback. Close or Escape returns to the workspace without changing
selection or lights.

Result cards show up to four stored part parameters, prioritizing electrical
values, ratings, materials, dimensions and package/mounting information. Template
units are shown with the label; values are displayed as stored, without inferred
specifications or new unit conversions. Long labels/values are visibly shortened
with an ellipsis; the native part page has the complete parameter list. A single
batched SQL window query reads at most four rows per distinct matched part. Empty
results skip both parameter and stock reads. These summaries do not introduce
additional parameter search filters. Selection recovery also uses current stored
image URLs, without generating image files.

Availability badges distinguish **No stock**, **Stock location missing**,
**Indicator setup needed**, partial setup and **Ready to locate**. The stock
quantity remains physically in-stock quantity, not quantity after allocations.
Parts without a usable indicator stay unavailable for Add; their part links
remain available for inspection and correction in InvenTree.

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

Only version, IDs, search text and interpreted-line indexes are stored under
`wled-locator-plus.finder.v1.user.<user ID>`, without quantities, mappings,
credentials, images or action history. Clear list retains search text; clearing
both removes the saved record. Invalid records are discarded and unavailable
storage leaves in-page use working. Tabs keep separate working selections;
latest saved edits are restored, without live cross-tab or cross-device sync.

### Record a request

Open Part Finder over HTTPS. **Record request** captures an English request;
allow microphone access when prompted. The addon requests English transcription
from the existing Whisper model. There is no language selector or translation step.
**Stop and transcribe** releases the microphone and sends the recording through
the authenticated addon backend to Speaches. **Discard recording** cancels capture
without uploading it. Capture stops automatically after 60 seconds. Unsupported
browsers and denied microphone permission leave typed search available.

The transcript appears with automatically prepared **Search lines**. Correct a
transcription mistake and press **Interpret request** again, or edit the search
lines directly. **Type or paste request** opens the same interpreter without a
microphone. Review the lines and notes, then choose **Add to parts to find**.
This appends to existing text; it does not search, select matches or operate LEDs.
Press **Search parts** when ready. Editing the original request invalidates its
previous interpretation; failed interpretation also permits manually entered lines.
After adding, **Last request and added search lines** retains the transcript and
the exact added lines for comparison on this page. It disappears on reload.

Lines added through **Record request** or **Type or paste request** use component
type filtering for supported, explicit families. A note under the search box
shows how many interpreted lines are present; results display the applied family
and category paths. For example, `magnet` searches `Mechanical/Magnets` and its
children, while `battery` searches `Electronics/Batteries`. An absent family
category returns no matches, without substituting charger ICs or other related
parts. Parts without the correct category will need their classification reviewed.

Category membership supplies the family name, so a correctly categorized O-ring
does not also need “O-ring” in its keywords. Remaining words, such as `silicone`,
and existing R/C/L value rules still constrain matches. DC motors use the DC motor
and vibration motor categories; PNP/NPN transistors use their distinct BJT categories.
Generic resistors exclude the Variable branch; an explicit `variable resistor`
uses that branch. Expand **Category filter** beside a result to inspect its paths
and exclusions.
Unknown families, identifiers and compound requests such as `motor driver` retain
full literal matching and display a notice that no type filter was applied.

Directly typed search lines keep normal Finder semantics, including when mixed
with interpreted lines having identical text. Editing a line in **Parts to find**
makes that line a normal text search; unchanged lines retain their mode through
insertions/deletions. Edits in the voice review before **Add** remain interpreted.
The added line modes are remembered with the search text and retained during
paging. Existing saved lists without modes restore as ordinary typed searches.
Category mappings are explicit paths in `component_types.py`, not database IDs;
renaming or moving a family category requires updating that mapping.

The standard interpreter removes known English request phrases, splits explicit part
lists, recognizes basic part names and normalizes spoken numbers/units. For example,
“Find a ten kilo ohm resistor and a ten microfarad capacitor” prepares `10kΩ resistor`
and `10uF capacitor` as separate lines.

Decimal words and English thousands separators are supported: “zero point one
microfarad” becomes `0.1uF`, while `1,000 ohms` means 1,000 ohms. Unrecognized comma
numbers are retained with a review warning. Clear value lists such as “10k and 20k
resistors” share the explicit family. Basic electronic parts, motors, O-rings,
batteries, magnets, tape and common fasteners have English aliases. Quantities
before modifiers, such as “two silicone O-rings”, become quantity notes rather
than literal search terms. Common spellings such as `orings`, `D.C. motor` and
`P N P transistors` are normalized. This is a finite ruleset.
Unknown wording is retained for editing. Phrases
such as “orderings” or “micro thread” receive correction warnings, not guesses.
Known mishearings, unresolved lists and unparsed spoken numbers disable **Add**
until the transcript is corrected/reinterpreted or the search lines are edited
manually. An incompatible interpreter response requires a restart and page refresh.

### Local model request grouping

An optional Ollama model groups natural-language requests before the standard
number/unit interpreter prepares the search lines. It is used by both recording
and **Type or paste request**; directly typed Finder searches do not call it.
The model extracts source phrases, rather than generating part IDs, SQL, values
or inventory changes. Each phrase must be an exact substring, in order, with only
request boilerplate/separators omitted between phrases. Invented wording, changed
values, missing qualifiers, overlapping/reordered phrases and incomplete replies
are rejected. The server builds queries using the existing deterministic parser.

The reviewed warehouse category mapping still controls matching; the model is
not trained on the inventory and receives no stock records or location mappings.
It can group `silicone, O-rings` together. A narrow material-comma repair retains
both words and adds a review note. It does not silently turn `orderings` into
O-rings, fix material names, or implement general parameter filtering. Unknown
or orphaned phrases require editing before Add. Review remains necessary even
after a schema-valid response: these checks do not prove semantic correctness.

Configure **Part Finder Request Parser** in Plugin Configuration with the Ollama
base URL and installed model ID. Blank URL disables the model. Its independent
`_INTERPRETER_CONFIG` setting does not alter speech settings, WLED or inventory.
This deployment uses `http://ollama:11434` and `qwen3.5:2b-q4_K_M` in the existing
Debian VM. Ollama joins `inventree_default`; its host port binds only to localhost.
See [maintenance](inventree-maintenance.md#local-ollama-service) for storage and
service commands. The browser never connects to Ollama directly.

JSON-schema output, disabled thinking, temperature 0, two CPU threads, a 2,048-token
context and 512 output tokens are per-request options, keeping Compose minimal.
The model remains loaded for five minutes after use. Requests over 2,000 characters
use the standard parser; its existing 8,192-character input limit still applies.
One addon model request runs at a time using a separate shared-volume file lock.
Busy, disconnected, timed-out, invalid or truncated model responses fall back to
the standard parser with a visible notice. Service connection/read timeouts are
3/30 seconds; the browser waits at most 40 seconds. A client timeout does not
guarantee that Ollama immediately stops an already submitted generation.
The addon does not persist transcripts or model replies; normal explicit Add and
browser recovery rules still apply.

Only the existing resistance/capacitance/inductance value matching is structured.
Voltage, torque, dimensions, ranges, tolerances and other specifications remain
literal text with review warnings; the interpreter does not relax those constraints
to return more results. Recognized quantities appear as notes and are not stock
filters, picking quantities or reservations. “A few” stays unspecified. The
ordinary typed search box still accepts short queries rather than conversational
requests; use **Type or paste request** to interpret natural language.

Audio, draft transcripts and prepared search lines stay in memory; the addon does
not save recordings or these drafts. A failed upload can be retried while the page remains open.
Text explicitly added to the search box follows normal browser recovery rules.
The addon limits uploads to 4 MiB and accepts WebM, Ogg, MP4, WAV or MP3 audio;
browser capture chooses a supported WebM/Opus, Ogg/Opus or MP4 encoder. One addon
transcription request runs at a time, independently of the WLED hardware lock.
Connection/read timeouts are 3/60 seconds; the browser stops waiting after 70
seconds. The current InvenTree Gunicorn timeout is 90 seconds. A disconnected or
timed-out client does not guarantee cancellation of work already sent to Speaches.

Configure **Part Finder Voice** in Plugin Configuration: service URL and installed
model ID. Transcription always sends `language=en` to Speaches.
It also sends a short technical-vocabulary prompt (O-rings, component names and
units). This guides recognition without post-editing what Whisper returned;
improvement must be checked against real recordings. The installed service's
`prompt` field is supported by its transcription API.
Blank service URL disables transcription. Settings use one `_SPEECH_CONFIG` JSON
plugin setting; they do not modify WLED settings or mappings. No API key or cloud
speech provider is used by this integration. An authenticated Speaches deployment
would need backend credential support before use.

This installation uses `Systran/faster-whisper-small`. Speaches currently publishes
host port 18000 and has its own Docker network. The verified backend route is
`http://172.20.0.1:18000`, through the InvenTree network's host gateway. This address
is deployment-specific: update the setting if the Docker subnet/port changes.
The browser's Speaches UI remains `https://speaches.skipbit.net/`; the addon does
not depend on that hostname resolving inside InvenTree. No Compose/network change
is needed. A future shared network could instead use `http://speaches:8000`.

### Locate assembly components

Assembly Part pages have a separate **Locate Components** panel. Set the assembly
quantity (default one), optionally expand subassemblies into their raw components,
and include optional BOM lines when needed. Expanded mode replaces each
subassembly with its component requirements; it does not also select finished
subassembly stock. A subassembly without a BOM remains a visible component.

The preview shows images, BOM references, required/physical/available quantities,
shortages and stock locations. Available quantities subtract build, sales and
transfer reservations using InvenTree's native allocation calculation. Optional
lines are excluded by default; consumables remain visible. Inherited BOM lines
and native setup/attrition/piece/rounding calculations are respected. Only exact
BOM parts are selected; variants and substitutes are not chosen automatically.

**Highlight available component locations** combines all mapped locations with
unallocated stock, even when other components are missing, short or unmapped.
Individual **Highlight** buttons locate one component; **All off** clears the
system. Fully reserved stock is listed but excluded from highlighting. Previewing,
changing options and refreshing never operate LEDs. Highlighting rechecks current
requirements, stock and mappings; it never allocates, consumes or moves stock.

This panel uses the assembly BOM independently of build-order parent/child links.
Existing Part locating still finds finished stock; Build locating still finds
allocated stock.

### Locate build requirements

Build Order pages have a separate **Locate Required Components** panel. It uses
saved build lines and subtracts quantities already consumed; the build quantity
is displayed and cannot be overridden here. Optional/consumable lines already
present in the build are respected. It does not regenerate requirements from a
possibly edited BOM or create allocations.

The preview includes stock allocated to the outstanding lines and unreserved
stock for uncovered requirements. Reservations for other work remain excluded.
Free stock must match the exact BOM part and the build's source location or its
descendants; explicitly allocated stock keeps its actual location and part,
including already allocated alternatives. Closed builds and fully consumed lines
are excluded. Missing/unavailable allocated stock and overallocations cannot
inflate usable quantities. Shared physical stock is counted once across included
requirements; shortage estimates respect each build's source restrictions.

**Include active sub-build requirements** follows the actual build-order tree,
using each active descendant's saved lines and consumption. It does not multiply
child quantities by the parent quantity or expand unrelated BOMs. The finished
subassembly remains a parent requirement; planned child outputs are labelled and
are not counted as physical stock. This differs from the assembly panel's raw
component expansion. Availability is a read-only estimate, not a stock reservation.

Combined/individual highlighting and **All off** behave like the assembly panel.
Highlighting rechecks current build status, requirements, allocations, stock and
mappings. Missing or unmapped components do not block the usable subset.

### Picking checklist

Both component panels group suggested quantities by drawer/box under **Pick by
storage location**. Suggestions never exceed the requirement; split stock gets
separate quantities at each location. Build suggestions follow the same source
and allocation rules as its preview. **Still needed** lists the uncovered amount.
Each picking entry has a part image on the right, falling back to the original
image or a placeholder when a thumbnail is unavailable.
Suggestions do not reserve stock. **Component details and stock** expands the
full availability, references, warnings and individual highlight controls.

Check **Collected** only after gathering the full component quantity across its
locations. Repeated checkboxes for one component move together. **Highlight
remaining components** excludes checked components; it does not operate LEDs
when nothing highlightable remains. Checking/unchecking and **Reset picking
progress** never change inventory, allocations or lights.

Progress is personal to the current account, browser and assembly/build. Local
storage uses `wled-locator-plus.picking.v1.user.<user ID>.<part|build>.<object ID>`
and contains only version, selected quantity/scope options, collected IDs and
requirement fingerprints. Reload restores options and checks a fresh preview
before enabling highlighting. Changing quantity/scope resets the checklist;
changed requirements reset affected marks. Stock/mapping/allocation changes alone
preserve marks. The server rejects a stale requirement revision before operating
hardware. Missing/corrupt/blocked storage leaves a usable in-page checklist.
There is no cross-device or live cross-tab synchronization.

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
  leaves. Existing Part locating uses in-stock StockItems; Builds use allocated
  stock. Assembly component locating additionally excludes reserved quantities.
  Build requirement locating includes allocations for its outstanding lines and
  free stock for the uncovered requirements.
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
| POST `finder/search/` | `{"queries":["NE555","100nF capacitor"],"limit":5}`. Optional `"component_queries":[1]` supplies unique zero-based interpreted-line indexes; omitted means ordinary typed matching. Groups include `component_query` and applied `type_filter` (name, included/excluded category paths or null), plus stock/images, `has_more`, `next_cursor`, `value_match`. |
| POST `finder/search/` with cursor | `{"queries":["NE555"],"cursor":"<returned cursor>"}`. One query, signed cursor bound to query and interpreted/typed mode, one-hour expiry. For an interpreted line also send `"component_queries":[0]`. |
| POST `finder/preview/` | `{"part_ids":[12,34]}`. Current parts, missing IDs, availability and combined target plan. |
| POST `finder/locate/` | Same IDs; resolves fresh data and operates only a valid selection. IDs here are placeholders. |
| POST `finder/off/` | `{}`. Clear the locator system. |
| POST `finder/transcribe/` | Raw audio body with its audio `Content-Type`, session and `X-CSRFToken`; returns English `text`. Separate from the 64 KiB JSON API. No inventory/hardware actions. |
| POST `finder/interpret/` | `{"text":"Find a 10k resistor and a 10 microfarad capacitor."}`; returns `version`, `requests` with `query`, `warnings`, `notes`, `needs_edit`, and `interpreter` (`ollama` or `rules`). Fallback includes `notice`. Reads parser configuration and optionally calls Ollama; performs no inventory/search/speech/hardware operations. |
| GET / POST `speech/settings/` | Read/save `{"url":"http://speech-host:8000","model":"Systran/faster-whisper-small"}`; superuser session, CSRF-protected JSON writes. No speech-service requests. |
| GET / POST `interpreter/settings/` | Read/save `{"url":"http://ollama:11434","model":"qwen3.5:2b-q4_K_M"}`; same superuser/CSRF rules. Blank URL disables model grouping. No upstream calls. |
| POST `components/part/<id>/preview/` | `{"quantity":3,"expand":true,"include_optional":false}`. Assembly BOM component availability; no controller requests. |
| POST `components/part/<id>/locate/` | Same options, optionally `component_id` for one current component. Highlight the available mapped subset, resolving fresh data. |
| POST `components/build/<id>/preview/` | `{"include_subbuilds":false}`. Saved remaining build requirements, allocations and available stock. |
| POST `components/build/<id>/locate/` | Same option, optionally `component_id`; resolves and highlights the usable subset. Quantity/BOM-expansion overrides are rejected. |
| GET `dashboard/data/` | Filtered/paginated snapshot and mapping/controller usage. |
| POST `dashboard/action/` | Command `preview`, `save`, `locate`, `test` or `off`; mapping review/save includes revision validation. |
| GET `preview/location/<id>/` | Native location readiness; other native previews cover Parts, Builds and StockItems. |

Limits: 64 KiB JSON; 1–20 queries, 200 characters/12 terms each; default five,
maximum ten matches per query per page; 1–100 selected positive integer IDs.
Cursor paging uses `(rank,name,ID)` rather than OFFSET. Live catalog edits can
move results; the UI deduplicates and cancels superseded requests.

Assembly limits: quantity 1–10,000; 1,000 parts, 2,000 BOM/effective lines,
12 nested levels and 5,000 in-stock records. Oversized or circular BOMs fail
before hardware execution; results are never silently truncated. An empty
highlightable subset returns 409 `components_not_locatable` with a fresh preview.
Build limits: 100 orders including the root, 2,000 saved lines, 1,000 component
parts, 5,000 allocations and 5,000 in-stock records. Oversized trees/plans fail
before hardware execution. Completed/cancelled orders have no highlightable plan.
Component previews include `picking` (revision, suggested location quantities and
shortages) and per-component requirement fingerprints. Locate accepts
`remaining_component_ids` (0–1,000 unique IDs) together with `picking_revision`;
the server resolves targets again and returns 409 `picking_changed` plus a fresh
preview if requirements changed. Empty subsets never clear or light hardware.

Errors include 400 validation, 403 authentication/CSRF, 405 method, 413 size,
415 media type, 409 stale/invalid selection, 502 WLED transport and 503
`locator_busy` with `Retry-After: 1`. Finder 409 includes
`code: selection_not_locatable` and corrective `preview`; dashboard conflicts use
`mapping_changed`. Responses use `success`, `action` and error/result fields.
Speech errors include 413 size, 415 format, 422 empty recognition, 502 service or
response failure, 503 `speech_busy`/`speech_not_configured` and 504 timeout.
Speech responses and settings reads/writes are not cached.
Interpretation accepts 1–8,192 characters and at most 20 requests. Oversized lines
are shown without truncation and must be shortened to the normal finder limits
before adding. The browser gives interpretation requests a forty-second timeout.
Ordinary Finder text search also matches related components by keywords/descriptions.
Interpreted lines restrict recognized explicit families by catalogue category;
they do not infer unknown types, correct misclassification, or guarantee the
requested specifications or physical stock exist. Review result cards.

## Source map

All paths below are relative to the plugin directory; no frontend build,
new Python dependency or plugin database migration is required. Optional speech
and model grouping use the separately deployed Speaches and Ollama services.

| Files | Responsibility |
|---|---|
| `__init__.py`, `plugin.py`, `constants.py` | Plugin registration, settings/facade, native panels, routes and shared identifiers. |
| `views.py` | Authenticated HTTP endpoints, validation and responses. |
| `wled.py`, `mapping.py`, `locator.py` | Controller transport/configuration, metadata helpers, inventory resolution and previews/plans. |
| `operations.py`, `planning.py`, `execution.py`, `locking.py` | Per-operation caches, ordered target union, hardware execution and cross-process serialization. |
| `finder.py`, `search_terms.py` | Search/availability/paging/selection and conservative value normalization. |
| `component_types.py`, `tests/test_component_types.py` | Pure family recognition, explicit warehouse category scopes and literal fallback for compound/unknown intents. |
| `speech.py`, `static/finder_voice.js` | Bounded server-side Speaches transport, configuration and separate voice recording/transcript UI. |
| `voice_requests.py`, `tests/test_voice_requests.py` | Pure English vocabulary, number/unit normalization, conservative request grouping, quantity notes and boundary regressions. |
| `request_interpreter.py`, `tests/test_request_interpreter.py` | Optional local Ollama extraction, exact source coverage validation, independent settings/lock, bounded transport and visible standard-parser fallback. |
| `bom.py`, `static/bom_panel.js` | Bounded assembly BOM expansion, component availability and native assembly panel. |
| `build_components.py` | Saved build requirements, allocation/source-aware availability and sub-build scope; shares the component panel and executor. |
| `picking.py`, `static/picking_checklist.js` | Suggested pick quantities, requirement revisions, personal checklist recovery and remaining-component selection. |
| `dashboard.py` | Mapping snapshots, sharing and reviewed transactional edits. |
| `page.py`, `finder_page.py` | Dashboard/finder rendering and CSRF bootstrap. |
| `templates/dashboard.html`, `templates/finder.html` | Page layouts. |
| `static/dashboard_page.js`, `static/dashboard_page.css` | Dashboard editor, filters and controller tools. |
| `static/finder_page.js`, `static/finder_page.css` | Search/results, images, selection recovery and locate controls. |
| `static/admin_settings.js` | Plugin Configuration UI. |
| `static/panel_common.js`, `static/locator_panel.js` | Shared native-panel helpers and Part/Build panels. |
| `static/stock_item_panel.js`, `static/stock_location_indicator_panel.js` | StockItem and StockLocation panels. |
| `static/locator_actions.js` | Spotlight/navigation actions. |
| `static/finder_entry.js` | Finder menu route bridge, Spotlight action and optional home dashboard shortcut. |
| `tests/support.py`, `tests/test_refactor.py`, `tests/test_facade.py` | Offline fixtures, backend regressions and protected callback checks. |
| `tests/test_queries.py`, `tests/test_search_terms.py`, `tests/test_locking.py` | Disposable ORM queries, value parsing and process locking. |
| `tests/test_speech.py`, `tests/browser_voice.py` | Mocked voice API boundaries/transport and browser recording, failure recovery and existing finder regressions. Browser checks use the finder fixture exporter. |
| `tests/browser_speech_settings.py` | Voice setup/disable/error and mobile checks against the real Plugin Configuration module; `WLED_SPEECH_STATIC_DIR` can point to collected assets. |
| `tests/render_{finder,dashboard,panels,bom}_fixture.py` | Export synthetic browser fixtures. |
| `tests/browser_{finder,dashboard,panels,bom}.py` | Optional Playwright checks with intercepted HTTP. |

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
and Plugin Configuration use collected static assets. After changing those assets,
explicitly recollect them; a container restart alone does not ensure the served
copies are current:

```bash
docker compose exec -T -w /home/inventree/src/backend/InvenTree \
  inventree-server python3 -B manage.py collectplugins
```

Compare the source and collected files under
`data/static/plugins/wled-locator-plus/`, verify the served asset, then hard-refresh
the browser. The component browser checks accept `WLED_BOM_STATIC_DIR` to test
collected assets instead of source assets. For a full application/plugin asset
collection, `docker compose exec -T inventree-server invoke static` is also
available; it does not compile a frontend by default. Documentation-only edits
need none of these actions.

Transfer the whole `data/plugins/inventree_wled_locator_plus/` folder, excluding
`__pycache__`, into the destination's configured plugin directory. Include this
guide as handoff documentation, activate the plugin, load/collect its assets and
verify setup. Code transfer alone does not carry controller settings or location
mappings: they follow a database migration or must be configured in the new
database.

## Next voice stage

Continue checking English accuracy using real failures: compare intended wording,
Whisper transcript, prepared lines and scoped catalogue matches. General structured
parameter filters and catalogue-aware speech corrections remain unimplemented.
Expand parameters against actual stored templates after basic recognition is
reliable. Keep uncertain interpretations visible for review.

A read-only comparison on 2026-11-16 used three example requests with the current
2B model, a 2,048-token context and a 512-token generation limit. Non-thinking
mode returned two source-valid extractions in 8–11 seconds; the longer example
was rejected for changed wording after 12 seconds. Thinking mode produced no
final answer within a 30-second budget on any example. This small comparison is
not an accuracy estimate; production settings remain unchanged. Use real failed
transcripts to tune extraction before enabling thinking or replacing the model.

Speaches is installed independently; the addon does not start containers, download
models or alter its configuration. Transport follows the
[Speaches transcription API](https://speaches.ai/usage/speech-to-text/); browser
capture uses [MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder).

## Deferred model work

Model comparison, prompt refinement and possible fine-tuning are deferred while
the addon is polished. The Finder workspace and direct access improvements are
implemented; see the user workflows above.

When implementation work is idle, explain LLM fundamentals using open-weight
models: parameters, quantization, tokens and context, RAM requirements, prompts,
reasoning modes, limitations and the difference between context and training.
