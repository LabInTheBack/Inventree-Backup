"""Plain HTML page rendering for WLED Locator Plus."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from django.http import HttpResponse

from .constants import BASE_URL
from .dashboard import build_dashboard, display_led, split_location_path


def render_index_page(plugin, request=None, message: dict | None = None, error: str | None = None):
    """Render the external indicator dashboard page."""
    params = request.GET if request else {}
    dashboard = build_dashboard(plugin, params)
    result_html = render_result(None, error)
    controller_select_options = render_controller_options(plugin)
    bulk_controller_options = render_bulk_controller_options(dashboard)
    max_led = max((int(controller.get("max_leds") or 1) for controller in dashboard["controllers"]), default=1)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>External Indicator Dashboard</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ background: #f4f6f8; color: #202124; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.45; margin: 0; }}
    main {{ margin: 0 auto; max-width: 1480px; padding: 1.25rem; }}
    header {{ align-items: flex-start; display: flex; gap: 1rem; justify-content: space-between; margin-bottom: 1rem; }}
    h1, h2, h3 {{ line-height: 1.2; margin: 0; }}
    h1 {{ font-size: 1.5rem; }}
    h2 {{ font-size: 1.05rem; margin-bottom: 0; }}
    h3 {{ font-size: 0.95rem; }}
    .muted, .note {{ color: #5f6368; }}
    .note {{ font-size: 0.86rem; margin: 0; }}
    .status, .summary {{ display: flex; flex-wrap: wrap; gap: 0.45rem; }}
    .status {{ color: #5f6368; margin-top: 0.4rem; }}
    .summary {{ margin-top: 0.9rem; }}
    .pill {{ background: #ffffff; border: 1px solid #d7d9dc; border-radius: 999px; padding: 0.2rem 0.55rem; }}
    a.pill {{ text-decoration: none; }}
    .pill.strong {{ border-color: #2364aa; color: #174a83; }}
    .pill.warn {{ border-color: #c77700; color: #7a4b00; }}
    .top-actions {{ display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: flex-end; }}
    section {{ background: #ffffff; border: 1px solid #d7d9dc; border-radius: 8px; margin-bottom: 1rem; padding: 1rem; }}
    .section-head {{ align-items: center; display: flex; gap: 0.75rem; justify-content: space-between; margin-bottom: 0.85rem; }}
    .section-head h2 {{ margin: 0; }}
    .stack {{ display: grid; gap: 0.75rem; }}
    .overview {{ display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .overview-card {{ background: #ffffff; border: 1px solid #d7d9dc; border-radius: 8px; padding: 0.85rem; }}
    .overview-card h3 {{ margin-bottom: 0.35rem; }}
    .overview-card strong {{ display: block; font-size: 1.2rem; }}
    .filters {{ align-items: end; display: grid; gap: 0.75rem; grid-template-columns: minmax(160px, 1fr) minmax(180px, 1fr) minmax(210px, 1.2fr) minmax(160px, 1fr) minmax(110px, 0.6fr) auto auto; }}
    .tools-grid {{ display: grid; gap: 0.75rem; grid-template-columns: minmax(360px, 1.2fr) minmax(260px, 0.8fr); }}
    .tool-card {{ border: 1px solid #e2e3e5; border-radius: 8px; display: grid; gap: 0.65rem; padding: 0.85rem; }}
    .bulk-bar {{ align-items: end; background: #f8f9fa; border: 1px solid #e2e3e5; border-radius: 8px; display: grid; gap: 0.7rem; grid-template-columns: minmax(120px, auto) minmax(190px, 1fr) minmax(120px, 0.6fr) auto auto auto; margin-bottom: 0.8rem; padding: 0.75rem; }}
    form {{ align-items: end; display: grid; gap: 0.6rem; }}
    form.service-form {{ grid-template-columns: minmax(190px, 1fr) minmax(110px, 140px) auto; }}
    label {{ color: #3c4043; display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.25rem; }}
    input, select {{ border: 1px solid #c6c9ce; border-radius: 6px; box-sizing: border-box; font: inherit; height: 2.35rem; min-height: 2.35rem; padding: 0.35rem 0.45rem; width: 100%; }}
    button, .button, .link-button {{ align-items: center; background: #2364aa; border: 0; border-radius: 6px; box-sizing: border-box; color: #ffffff; cursor: pointer; display: inline-flex; font: inherit; height: 2.35rem; justify-content: center; min-height: 2.35rem; padding: 0 0.75rem; text-align: center; text-decoration: none; white-space: nowrap; }}
    .secondary {{ background: #50565e; }}
    .ghost {{ background: #ffffff; border: 1px solid #c6c9ce; color: #202124; }}
    .danger {{ background: #a43d2f; }}
    .map-stack {{ display: grid; gap: 0.8rem; }}
    .grid-card {{ border: 1px solid #e2e3e5; border-radius: 8px; overflow: hidden; }}
    .grid-head {{ align-items: center; background: #f8f9fa; border-bottom: 1px solid #e2e3e5; display: flex; gap: 0.7rem; justify-content: space-between; padding: 0.7rem 0.85rem; }}
    .led-grid {{ display: grid; gap: 4px; grid-template-columns: repeat(auto-fill, minmax(34px, 34px)); padding: 0.85rem; }}
    .led-cell {{ align-items: center; aspect-ratio: 1 / 1; background: #eef1f4; border: 1px solid #d7d9dc; border-radius: 6px; color: #3c4043; display: flex; font-size: 0.75rem; justify-content: center; min-width: 0; text-decoration: none; }}
    .led-cell.used {{ background: #e4f4ec; border-color: #46a071; color: #14532d; font-weight: 600; }}
    .led-cell.conflict {{ background: #fff1e0; border-color: #c77700; color: #7a4b00; font-weight: 700; }}
    .led-cell.active {{ outline: 2px solid #2364aa; outline-offset: 1px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #e2e3e5; padding: 0.55rem; text-align: left; vertical-align: middle; }}
    th {{ color: #5f6368; font-size: 0.85rem; font-weight: 600; }}
    .select-col {{ min-width: 36px; width: 36px; }}
    .select-col input {{ height: 1rem; min-height: 1rem; width: 1rem; }}
    td.actions {{ white-space: nowrap; }}
    .path {{ min-width: 220px; }}
    .bin, .controller, .led-number, .state {{ white-space: nowrap; }}
    .controller {{ min-width: 110px; }}
    .led-number {{ min-width: 80px; }}
    .state {{ min-width: 90px; }}
    .component-summary {{ display: block; max-width: 440px; }}
    .component-count {{ display: block; font-weight: 600; }}
    .component-list {{ color: #3c4043; display: block; font-size: 0.86rem; margin-top: 0.15rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .action-status {{ color: #3c4043; font-size: 0.9rem; min-height: 1.35rem; }}
    .result-detail {{ background: #f7f8f9; border: 1px solid #d8dde2; border-radius: 6px; padding: 0.75rem; }}
    .result {{ margin-bottom: 1rem; }}
    @media (max-width: 1180px) {{ .filters, .tools-grid, .bulk-bar, form.service-form {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 720px) {{ header {{ display: block; }} .top-actions {{ justify-content: flex-start; margin-top: 0.75rem; }} button, .button {{ width: 100%; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>External Indicator</h1>
        <div class="status">
          <span class="pill">{dashboard['controller_count']} WLED controllers</span>
          <span class="pill">{dashboard['summary']['mapped']} mapped locations</span>
          <span class="pill">{dashboard['summary']['free_leds']} free LEDs</span>
        </div>
      </div>
      <div class="top-actions">
        <a class="button danger" href="{BASE_URL}?action=off">All Off</a>
      </div>
    </header>

    {result_html}

    <section>
      <div class="section-head">
        <h2>Controllers</h2>
      </div>
      <div class="overview">{render_controller_overview(dashboard)}</div>
    </section>

    <section>
      <div class="section-head">
        <h2>Filter</h2>
      </div>
      {render_filter_form(dashboard)}
      <div class="summary">
        <span class="pill">{dashboard['filtered_count']} rows shown</span>
        <span class="pill">{dashboard['summary']['assigned_filtered']} assigned in filter</span>
        <span class="pill">{dashboard['summary']['unassigned_filtered']} unassigned in filter</span>
        <a class="pill warn" href="{BASE_URL}?state=conflict">{dashboard['summary']['conflict_rows']} conflict rows</a>
        <a class="pill warn" href="{BASE_URL}?state=needs-led">{dashboard['summary']['needs_led']} stocked without LED</a>
        <span class="pill warn">{dashboard['summary']['invalid']} invalid mappings</span>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>Service Tools</h2>
      </div>
      <div class="tools-grid">
        <div class="tool-card">
          <h3>Controller Test</h3>
          <form class="service-form" method="get" action="{BASE_URL}">
            <input type="hidden" name="action" value="test">
            {controller_select_options}
            <label>LED number <input name="led_display" type="number" min="1" max="{max_led}" step="1" required></label>
            <button type="submit">Test LED</button>
          </form>
        </div>
        <div class="tool-card">
          <h3>Filtered Locate</h3>
          <p class="note">Locate the assigned StockLocations currently shown by the filters.</p>
          <button type="button" class="button" data-locate-url="{render_locate_filtered_url(dashboard)}" data-location-label="filtered Stock Locations">Locate Filtered</button>
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <h2>LED Map</h2>
        <span class="note">All configured WLED controllers are shown.</span>
      </div>
      {render_led_maps(dashboard)}
    </section>

    <section>
      <div class="section-head">
        <h2>Stock Location</h2>
      </div>
      <div class="action-status" data-action-status></div>
      <div class="bulk-bar">
        <span class="muted"><strong data-selected-count>0</strong> selected</span>
        <label>Reassign to WLED
          <select data-bulk-controller>{bulk_controller_options}</select>
        </label>
        <label>Start LED
          <input data-bulk-led type="number" min="1" step="1" placeholder="LED">
        </label>
        <button type="button" class="button" data-bulk-action="locate">Locate Selected</button>
        <button type="button" class="button secondary" data-bulk-action="reassign">Reassign Selected</button>
        <button type="button" class="button danger" data-bulk-action="clear">Clear Selected</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th class="select-col"><input type="checkbox" data-select-all aria-label="Select all rows"></th><th>Location</th><th>Bin</th><th>WLED</th><th>LED number</th><th>Component/count</th><th>State</th><th>Actions</th></tr></thead>
          <tbody>{render_assignment_rows(dashboard)}</tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    (() => {{
      const status = document.querySelector("[data-action-status]");
      const filterForm = document.querySelector("form.filters");
      const rows = Array.from(document.querySelectorAll("[data-location-row]"));
      const selectedCount = document.querySelector("[data-selected-count]");
      const selectAll = document.querySelector("[data-select-all]");
      const bulkController = document.querySelector("[data-bulk-controller]");
      const bulkLed = document.querySelector("[data-bulk-led]");

      function setStatus(message, isError = false) {{
        if (!status) {{
          return;
        }}
        status.textContent = message || "";
        status.style.color = isError ? "#8a2f24" : "#3c4043";
      }}

      function selectedRows() {{
        return rows.filter((row) => {{
          const checkbox = row.querySelector("[data-row-select]");
          return checkbox && checkbox.checked && !row.hidden;
        }});
      }}

      function updateSelectedCount() {{
        if (selectedCount) {{
          selectedCount.textContent = String(selectedRows().length);
        }}

        if (selectAll) {{
          const visibleRows = rows.filter((row) => !row.hidden);
          const selectedVisible = visibleRows.filter((row) => row.querySelector("[data-row-select]")?.checked);
          selectAll.checked = visibleRows.length > 0 && selectedVisible.length === visibleRows.length;
          selectAll.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visibleRows.length;
        }}
      }}

      function applyLedFilter(controller, led) {{
        if (filterForm) {{
          const controllerInput = filterForm.querySelector("[name='controller']");
          const ledInput = filterForm.querySelector("[name='led']");
          const stateInput = filterForm.querySelector("[name='state']");

          if (controllerInput) controllerInput.value = controller;
          if (ledInput) ledInput.value = led;
          if (stateInput) stateInput.value = "all";
        }}

        let shown = 0;
        rows.forEach((row) => {{
          const match = row.dataset.controller === controller && row.dataset.led === led;
          row.hidden = !match;
          if (match) shown += 1;
        }});
        setStatus(`${{shown}} Stock Location row${{shown === 1 ? "" : "s"}} shown for ${{controller}} LED ${{led}}.`);
        updateSelectedCount();
      }}

      async function requestJson(url) {{
        const response = await fetch(url, {{
          credentials: "same-origin",
          headers: {{ "Accept": "application/json" }},
        }});
        const payload = await response.json().catch(() => ({{}}));

        if (!response.ok || payload.success === false) {{
          throw new Error(payload.error || `Request failed with HTTP ${{response.status}}`);
        }}

        return payload;
      }}

      async function locateRows(targetRows, label) {{
        const ids = targetRows
          .filter((row) => row.dataset.controller && row.dataset.controller !== "-" && row.dataset.led)
          .map((row) => row.dataset.locationId);

        if (!ids.length) {{
          setStatus("No selected rows have assigned LEDs.", true);
          return;
        }}

        setStatus(`Locating ${{label}}...`);
        await requestJson(`${{window.location.pathname}}locate/locations/?ids=${{ids.join(",")}}`);
        setStatus(`Located ${{label}}.`);
      }}

      async function reassignRows(targetRows) {{
        const targetController = bulkController ? bulkController.value : "";
        const targetOption = bulkController ? bulkController.selectedOptions[0] : null;
        const targetMax = targetOption ? Number(targetOption.dataset.maxLeds || 0) : 0;
        const startLed = bulkLed ? Number(bulkLed.value || 0) : 0;
        const rowsToAssign = targetRows.slice();

        if (!targetController) {{
          setStatus("Choose a target WLED controller first.", true);
          return;
        }}

        if (!Number.isInteger(startLed) || startLed < 1) {{
          setStatus("Enter a target Start LED number.", true);
          return;
        }}

        const lastLed = startLed + rowsToAssign.length - 1;
        if (targetMax > 0 && lastLed > targetMax) {{
          setStatus(`Cannot reassign: selected rows need LEDs ${{startLed}}-${{lastLed}}, but ${{targetController}} has ${{targetMax}} LEDs.`, true);
          return;
        }}

        const confirmed = window.confirm(
          rowsToAssign.length === 1
            ? `Reassign selected Stock Location to ${{targetController}} LED ${{startLed}}?`
            : `Reassign ${{rowsToAssign.length}} selected Stock Locations to ${{targetController}} LEDs ${{startLed}}-${{lastLed}}?`
        );
        if (!confirmed) {{
          return;
        }}

        setStatus(`Reassigning ${{rowsToAssign.length}} Stock Location row${{rowsToAssign.length === 1 ? "" : "s"}}...`);

        for (const [index, row] of rowsToAssign.entries()) {{
          const targetLed = startLed + index;
          const zeroBasedLed = targetLed - 1;
          await requestJson(`${{window.location.pathname}}register/location/${{row.dataset.locationId}}/controller/${{encodeURIComponent(targetController)}}/led/${{zeroBasedLed}}/`);
          row.dataset.controller = targetController;
          row.dataset.led = String(targetLed);
          row.querySelector("[data-controller-cell]").textContent = targetController;
          row.querySelector("[data-led-cell]").textContent = String(targetLed);
          row.querySelector("[data-state-cell]").textContent = "assigned";
        }}

        setStatus(`Reassigned ${{rowsToAssign.length}} Stock Location row${{rowsToAssign.length === 1 ? "" : "s"}} to ${{targetController}}. Reload the page to refresh the LED map colors.`);
      }}

      async function clearRows(targetRows) {{
        if (!targetRows.length) {{
          setStatus("Select at least one Stock Location row first.", true);
          return;
        }}

        const confirmed = window.confirm(`Clear WLED mappings from ${{targetRows.length}} selected Stock Location row${{targetRows.length === 1 ? "" : "s"}}?`);
        if (!confirmed) {{
          return;
        }}

        setStatus(`Clearing ${{targetRows.length}} mapping${{targetRows.length === 1 ? "" : "s"}}...`);

        for (const row of targetRows) {{
          await requestJson(`${{window.location.pathname}}register/location/${{row.dataset.locationId}}/clear/`);
          row.dataset.controller = "-";
          row.dataset.led = "";
          row.dataset.state = "unassigned";
          row.querySelector("[data-controller-cell]").textContent = "-";
          row.querySelector("[data-led-cell]").textContent = "";
          row.querySelector("[data-state-cell]").textContent = "unassigned";
          row.querySelector("[data-locate-url]")?.remove();
        }}

        setStatus(`Cleared ${{targetRows.length}} mapping${{targetRows.length === 1 ? "" : "s"}}. Reload the page to refresh the LED map colors.`);
      }}

      document.querySelectorAll("[data-led-filter]").forEach((link) => {{
        link.addEventListener("click", (event) => {{
          event.preventDefault();
          applyLedFilter(link.dataset.controller, link.dataset.led);
        }});
      }});

      document.querySelectorAll("[data-locate-url]").forEach((button) => {{
        button.addEventListener("click", async (event) => {{
          event.preventDefault();
          const label = button.dataset.locationLabel || "Stock Location";
          const locateUrl = button.dataset.locateUrl;

          if (!locateUrl) {{
            setStatus("No assigned Stock Locations are available for this locate action.", true);
            return;
          }}

          setStatus(`Locating ${{label}}...`);
          button.disabled = true;

          try {{
            await requestJson(locateUrl);
            setStatus(`Located ${{label}}.`);
          }} catch (error) {{
            setStatus(error.message || "Locate failed.", true);
          }} finally {{
            button.disabled = false;
          }}
        }});
      }});

      document.querySelectorAll("[data-row-select]").forEach((checkbox) => {{
        checkbox.addEventListener("change", updateSelectedCount);
      }});

      if (selectAll) {{
        selectAll.addEventListener("change", () => {{
          rows.filter((row) => !row.hidden).forEach((row) => {{
            const checkbox = row.querySelector("[data-row-select]");
            if (checkbox) checkbox.checked = selectAll.checked;
          }});
          updateSelectedCount();
        }});
      }}

      document.querySelectorAll("[data-bulk-action]").forEach((button) => {{
        button.addEventListener("click", async () => {{
          const targetRows = selectedRows();

          if (!targetRows.length) {{
            setStatus("Select at least one Stock Location row first.", true);
            return;
          }}

          button.disabled = true;

          try {{
            if (button.dataset.bulkAction === "locate") {{
              await locateRows(targetRows, "selected Stock Locations");
            }} else if (button.dataset.bulkAction === "reassign") {{
              await reassignRows(targetRows);
            }} else if (button.dataset.bulkAction === "clear") {{
              await clearRows(targetRows);
            }}
          }} catch (error) {{
            setStatus(error.message || "Bulk action failed.", true);
          }} finally {{
            button.disabled = false;
            updateSelectedCount();
          }}
        }});
      }});

      updateSelectedCount();
    }})();
  </script>
</body>
</html>"""
    return HttpResponse(html)


def render_filter_form(dashboard: dict) -> str:
    """Render WLED, StockLocation, sub-location, and state filters."""
    filters = dashboard["filters"]
    controller_options = ["<option value=''>All WLEDs</option>"]

    for controller in dashboard["controllers"]:
        label = controller["label"]
        selected = " selected" if filters["controller"] == label else ""
        controller_options.append(f"<option value='{escape(label)}'{selected}>{escape(label)}</option>")

    root_options_html = ["<option value=''>All StockLocations</option>"]
    for option in dashboard["root_options"]:
        selected = " selected" if filters["root"] == str(option["id"]) else ""
        root_options_html.append(
            f"<option value='{option['id']}'{selected}>{escape(option['path'])}</option>"
        )

    state_options = [
        ("all", "All states"),
        ("assigned", "Assigned"),
        ("unassigned", "Unassigned"),
        ("needs-led", "Stocked without LED"),
        ("led-only", "Missing WLED"),
        ("conflict", "Conflicts"),
        ("invalid", "Invalid"),
    ]
    state_html = []
    for value, label in state_options:
        selected = " selected" if filters["state"] == value else ""
        state_html.append(f"<option value='{value}'{selected}>{label}</option>")

    return f"""
      <form class="filters" method="get" action="{BASE_URL}">
        <label>WLED
          <select name="controller">{''.join(controller_options)}</select>
        </label>
        <label>Stock Location
          <select name="root">{''.join(root_options_html)}</select>
        </label>
        <label>Search
          <input name="q" value="{escape(filters['q'])}" placeholder="Part, bin, location, ID">
        </label>
        <label>State
          <select name="state">{''.join(state_html)}</select>
        </label>
        <label>LED
          <input name="led" value="{escape(filters['led'])}" type="number" min="1" step="1" inputmode="numeric" placeholder="Any">
        </label>
        <button type="submit">Filter</button>
        <a class="button ghost" href="{BASE_URL}">Reset</a>
      </form>
    """


def render_controller_overview(dashboard: dict) -> str:
    """Render compact cards for configured controller usage."""
    cards = []

    for item in dashboard["controller_usage"]:
        query = dashboard_query(dashboard, controller=item["label"], state="all", led="")
        conflict_query = dashboard_query(dashboard, controller=item["label"], state="conflict", led="")
        conflict_html = (
            f"<a class='pill warn' href='{BASE_URL}?{escape(conflict_query)}'>{item['conflicts']} conflicts</a>"
            if item["conflicts"]
            else "<span class='pill'>0 conflicts</span>"
        )
        cards.append(
            "<div class='overview-card'>"
            f"<h3>{escape(item['label'])}</h3>"
            f"<strong>{item['used']} used / {item['max_leds']} LEDs</strong>"
            f"<div class='status'><span class='pill'>{item['free']} free</span>{conflict_html}</div>"
            f"<a class='button ghost' href='{BASE_URL}?{escape(query)}'>Show rows</a>"
            "</div>"
        )

    return "".join(cards) or "<p class='note'>No WLED controllers are configured.</p>"


def render_bulk_controller_options(dashboard: dict) -> str:
    """Render target controller options for bulk reassignment."""
    options = ["<option value=''>Choose WLED</option>"]

    for controller in dashboard["controllers"]:
        label = controller["label"]
        max_leds = int(controller.get("max_leds") or 0)
        options.append(f"<option value='{escape(label)}' data-max-leds='{max_leds}'>{escape(label)}</option>")

    return "".join(options)


def render_led_maps(dashboard: dict) -> str:
    """Render compact LED grids for all configured controllers."""
    cards = []

    for controller in dashboard["controllers"]:
        label = controller["label"]
        max_leds = int(controller.get("max_leds") or 0)
        used_count = sum(
            1
            for (controller_label, _led), rows in dashboard["led_usage"].items()
            if controller_label == label and rows
        )
        cells = []

        for led in range(max_leds):
            rows = dashboard["led_usage"].get((label, led), [])
            classes = ["led-cell"]
            title = f"{label} LED {display_led(led)}"

            if rows:
                classes.append("used")
                title = "; ".join(row["path"] for row in rows[:3])

            if (label, led) in dashboard["conflict_keys"]:
                classes.append("conflict")
                title = f"Conflict: {title}"

            if (label, led) in dashboard["selected_leds"]:
                classes.append("active")

            query = dashboard_query(dashboard, controller=label, led=display_led(led), state="all")
            cells.append(
                f"<a class='{' '.join(classes)}' title='{escape(title)}' href='{BASE_URL}?{escape(query)}' "
                f"data-led-filter data-controller='{escape(label)}' data-led='{display_led(led)}'>{display_led(led)}</a>"
            )

        cards.append(
            "<div class='grid-card'>"
            "<div class='grid-head'>"
            f"<h3>{escape(label)}</h3>"
            f"<span class='muted'>{used_count} used / {max_leds} LEDs</span>"
            "</div>"
            f"<div class='led-grid'>{''.join(cells) or '<span class=\"muted\">No LED count configured.</span>'}</div>"
            "</div>"
        )

    return f"<div class='map-stack'>{''.join(cards)}</div>" if cards else "<p class='note'>No configured WLED controllers.</p>"


def dashboard_query(dashboard: dict, **overrides) -> str:
    """Return a query string preserving dashboard filters with overrides."""
    values = dict(dashboard["filters"])
    values.update(overrides)
    return urlencode({key: value for key, value in values.items() if value})


def render_assignment_rows(dashboard: dict) -> str:
    """Render filtered assignment rows."""
    rows = []

    for row in dashboard["rows"]:
        led_text = display_led(row["led"])
        controller_text = row["controller"] or "-"
        state_text = display_state(row["state"])
        detail = row["invalid"] or state_text
        parts = row.get("path_parts") or split_location_path(row["path"])
        location_url = f"/web/stock/location/{row['id']}/assign-external-indicator-stock-location"
        locate_url = f"{BASE_URL}locate/location/{row['id']}/"

        actions = [f"<a class='link-button ghost' href='{location_url}'>Open</a>"]
        if row["controller"] and row["led"] is not None and not row["invalid"]:
            actions.insert(
                0,
                "<button type='button' class='link-button' "
                f"data-locate-url='{locate_url}' data-location-label='{escape(row['path'])}'>Locate</button>",
            )

        component_badges = render_component_badges(row)
        rows.append(
            "<tr "
            "data-location-row "
            f"data-location-id='{row['id']}' "
            f"data-controller='{escape(controller_text)}' "
            f"data-led='{escape(led_text)}' "
            f"data-state='{escape(row['state'])}'"
            ">"
            "<td class='select-col'><input type='checkbox' data-row-select aria-label='Select row'></td>"
            f"<td class='path'>{escape(parts['location'])}</td>"
            f"<td class='bin'>{escape(parts['bin'])}</td>"
            f"<td class='controller' data-controller-cell>{escape(controller_text)}</td>"
            f"<td class='led-number' data-led-cell>{escape(led_text)}</td>"
            f"<td>{component_badges}</td>"
            f"<td class='state' data-state-cell>{escape(detail)}</td>"
            f"<td class='actions'>{' '.join(actions)}</td>"
            "</tr>"
        )

    return "".join(rows) or "<tr><td colspan='8'>No StockLocations match the current filters.</td></tr>"


def render_component_badges(row: dict) -> str:
    """Render compact component/count text for a location row."""
    count = int(row.get("component_count") or 0)
    names = row.get("component_names") or []

    if not count:
        return "<span class='muted'>No components</span>"

    component_label = "component" if count == 1 else "components"
    visible_names = names[:3]
    name_text = ", ".join(visible_names)

    if len(names) > 3:
        name_text = f"{name_text}, +{len(names) - 3} more"

    return (
        "<span class='component-summary'>"
        f"<span class='component-count'>{count} {component_label}</span>"
        f"<span class='component-list'>{escape(name_text)}</span>"
        "</span>"
    )


def display_state(state: str) -> str:
    """Return a short table/filter label for an assignment state."""
    labels = {
        "assigned": "assigned",
        "unassigned": "unassigned",
        "led-only": "missing WLED",
        "conflict": "conflict",
        "invalid": "invalid",
    }
    return labels.get(state, state.replace("-", " "))


def render_locate_filtered_url(dashboard: dict) -> str:
    """Return locate URL for currently filtered assigned locations."""
    ids = [
        str(row["id"])
        for row in dashboard["rows"]
        if row["controller"] and row["led"] is not None and not row["invalid"]
    ]
    if not ids:
        return ""

    return f"{BASE_URL}locate/locations/?ids={escape(','.join(ids))}"


def render_controller_options(plugin) -> str:
    """Render WLED controller select options when multiple controllers are configured."""
    controllers = plugin.get_wled_controllers(include_info=False)

    if len(controllers) < 2:
        return ""

    options = []

    for index, controller in enumerate(controllers):
        try:
            max_leds = plugin.get_controller_max_leds(controller["label"])
            detail = f"{max_leds} LEDs"
            disabled = ""
        except Exception:
            detail = "unreachable"
            disabled = " disabled"

        selected = " selected" if index == 0 and not disabled else ""
        options.append(
            f"<option value='{escape(controller['label'])}'{selected}{disabled}>"
            f"{escape(controller['label'])} - {escape(detail)}"
            "</option>"
        )

    return f"<label>Controller <select name='controller'>{''.join(options)}</select></label>"


def render_result(message: dict | None, error: str | None) -> str:
    """Render concise page action results."""
    if message:
        result = message.get("result") or {}
        detail = render_result_detail(result)
        return (
            "<section class='result ok'>"
            f"<h2>{escape(message['label'])}</h2>"
            f"<div class='result-detail'>{detail}</div>"
            "</section>"
        )

    if error:
        return (
            "<section class='result error'>"
            "<h2>Error</h2>"
            f"<div class='result-detail'>{escape(error)}</div>"
            "</section>"
        )

    return ""


def render_result_detail(result: dict) -> str:
    """Render a human-readable result block for external page actions."""
    if not isinstance(result, dict):
        return escape(str(result))

    if "location" in result:
        location = result.get("location") or {}
        parts = split_location_path(location.get("path") or location.get("name") or "")
        rows = result.get("lit") if isinstance(result.get("lit"), list) else []

        if rows:
            table_rows = []
            for row in rows:
                row_location = row.get("location") or {}
                row_parts = split_location_path(row_location.get("path") or row_location.get("name") or "")
                table_rows.append(
                    "<tr>"
                    f"<td>{escape(row_parts['location'])}</td>"
                    f"<td>{escape(row_parts['bin'])}</td>"
                    f"<td>{escape(format_indicator(row))}</td>"
                    f"<td>Mapped location</td>"
                    "</tr>"
                )

            return (
                f"<p><strong>{escape(location.get('path') or location.get('name') or 'Location')} located:</strong></p>"
                f"{result_table('Location', 'Bin', 'LED number', 'Component/count', ''.join(table_rows))}"
            )

        table_row = (
            "<tr>"
            f"<td>{escape(parts['location'])}</td>"
            f"<td>{escape(parts['bin'])}</td>"
            f"<td>{escape(format_indicator(result))}</td>"
            "<td>Mapped location</td>"
            "</tr>"
        )
        return (
            f"<p><strong>{escape(parts['location'])}</strong></p>"
            f"{result_table('Location', 'Bin', 'LED number', 'Component/count', table_row)}"
        )

    if "controllers" in result:
        controllers = result.get("controllers") or {}
        count = len(controllers.get("set", {}) if isinstance(controllers, dict) else {})
        return f"<p>WLED command completed on {count} controller(s).</p>"

    if result.get("success") is True:
        return "<p>WLED command completed.</p>"

    return "<p>WLED command completed.</p>"


def format_indicator(entry: dict) -> str:
    """Return compact controller / LED text from a result entry."""
    indicators = entry.get("indicators")

    if isinstance(indicators, list) and indicators:
        return ", ".join(
            f"{item.get('controller', '')} / LED {display_led(item.get('led'))}"
            for item in indicators
        )

    controller = entry.get("controller")
    led = display_led(entry.get("led"))

    if controller and led:
        return f"{controller} / LED {led}"

    if led:
        return f"LED {led}"

    return ""


def result_table(col1: str, col2: str, col3: str, col4: str, rows: str) -> str:
    """Return a compact result table."""
    return (
        "<div class='table-wrap'><table>"
        f"<thead><tr><th>{escape(col1)}</th><th>{escape(col2)}</th><th>{escape(col3)}</th><th>{escape(col4)}</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table></div>"
    )
