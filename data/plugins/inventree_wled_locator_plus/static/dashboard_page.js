(() => {
  "use strict";
  const config = JSON.parse(document.getElementById("dashboard-config").textContent);
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const filters = $("[data-filter-form]");
  const editor = $("[data-editor]");
  const editorForm = $("[data-editor-form]");
  const token = editorForm.elements.csrfmiddlewaretoken.value;
  const params = new URLSearchParams();
  const initial = new URLSearchParams(window.location.search);
  for (const key of ["q", "root", "controller", "state", "led", "page", "view", "led_page"]) {
    if (initial.get(key)) params.set(key, initial.get(key));
  }
  let snapshot = null;
  let chosen = new Map();
  let editRows = [];
  let review = null;
  let reviewedPayload = null;
  let busy = false;
  let loading = false;
  let loadRevision = 0;
  let loadController = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function status(message, kind = "", target = $("[data-status]")) {
    target.textContent = message;
    target.className = `status ${kind}`;
  }
  function stateLabel(value) {
    return ({mapped: "Mapped", shared: "Shared", unmapped: "Unmapped", invalid: "Needs correction"})[value] || value;
  }
  function mappingText(mapping) {
    if (!mapping) return "No mapping";
    if (typeof mapping !== "object" || Array.isArray(mapping)) return "Invalid mapping";
    const raw = mapping.leds ?? (mapping.led === undefined ? [] : [mapping.led]);
    const leds = Array.isArray(raw) ? raw.map((led) => Number.isInteger(led) ? led + 1 : "?") : ["?"];
    return `${mapping.controller || "Missing controller"} · LED${leds.length === 1 ? "" : "s"} ${leds.join(", ") || "missing"}`;
  }
  async function request(url, payload, signal) {
    const response = await fetch(url, {
      method: payload === undefined ? "GET" : "POST", credentials: "same-origin", signal,
      headers: {Accept: "application/json", ...(payload === undefined ? {} : {"Content-Type": "application/json", "X-CSRFToken": token})},
      ...(payload === undefined ? {} : {body: JSON.stringify(payload)}),
    });
    if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("Your session may have expired. Refresh the page and sign in again.");
    }
    const data = await response.json();
    if (!response.ok || data.success !== true) {
      let message = data.error || `Request failed (${response.status}).`;
      if (response.status === 403) message = "Access denied or your session expired. Refresh the page and sign in again.";
      if (data.code === "locator_busy") message = "The locator is busy. Wait for the current action, then try again.";
      const error = new Error(message);
      error.code = data.code;
      throw error;
    }
    return data;
  }
  function choices(select, items, placeholder, value) {
    select.replaceChildren();
    if (placeholder !== null) select.append(new Option(placeholder, ""));
    for (const item of items) select.append(new Option(item.path || item.label, String(item.id ?? item.label)));
    if ([...select.options].some((option) => option.value === value)) select.value = value;
    else if (value) select.append(new Option(`${value} (unavailable)`, value, true, true));
  }
  function updateControls() {
    const blocked = busy || loading;
    $("[data-selected-count]").textContent = String(chosen.size);
    $("[data-edit-selected]").disabled = blocked || !chosen.size;
    $("[data-locate-selected]").disabled = blocked || !chosen.size || [...chosen.values()].some((row) => !["mapped", "shared"].includes(row.state));
    for (const button of $$("[data-view], [data-off], [data-reset], [data-retry], [data-filter-form] button")) button.disabled = blocked;
    for (const input of $$("[data-filter-form] input, [data-filter-form] select, [data-led-filter], [data-tool-controller]")) input.disabled = blocked;
    for (const input of $$("[data-row-select], [data-select-all], [data-row-edit], [data-row-locate], [data-led-grid] button, [data-show-locations]")) input.disabled = blocked || !snapshot;
    $("[data-select-all]").checked = !!snapshot?.rows.length && chosen.size === snapshot.rows.length;
    $("[data-select-all]").indeterminate = chosen.size > 0 && chosen.size < (snapshot?.rows.length || 0);
    for (const button of $$("[data-page]")) button.disabled = blocked || !snapshot || (button.dataset.page === "previous" ? snapshot.page <= 1 : snapshot.page >= snapshot.pages);
    for (const button of $$("[data-led-page]")) button.disabled = blocked || !snapshot?.led_map || (button.dataset.ledPage === "previous" ? snapshot.led_map.page <= 1 : snapshot.led_map.page >= snapshot.led_map.pages);
    $("[data-test-form] button").disabled = blocked || !snapshot?.led_map || !snapshot.controllers.find((item) => item.label === snapshot.led_map.controller)?.max_leds;
    $("[data-test-led]").disabled = blocked || !snapshot?.led_map;
    for (const field of [...editorForm.elements]) {
      if (field.type !== "hidden") field.disabled = busy;
    }
    for (const field of $$('[data-assignment-field] select, [data-assignment-field] input')) field.disabled = busy || editorForm.elements.mode.value === "remove";
    $("[data-save]").disabled = busy || !review;
    $("[data-close-editor]").disabled = busy;
    $("[data-table-region]").setAttribute("aria-busy", String(loading));
  }
  function selectedChanged() {
    for (const checkbox of $$("[data-row-select]")) checkbox.checked = chosen.has(Number(checkbox.dataset.rowSelect));
    updateControls();
  }
  function renderRows(data) {
    const body = $("[data-rows]");
    body.replaceChildren();
    if (!data.rows.length) {
      const td = node("td", "empty", "No locations match these filters.");
      td.colSpan = 6;
      const tr = node("tr"); tr.append(td); body.append(tr);
    }
    for (const row of data.rows) {
      const tr = node("tr");
      tr.dataset.locationId = row.id;
      const selectCell = node("td");
      const checkbox = node("input"); checkbox.type = "checkbox"; checkbox.dataset.rowSelect = row.id;
      checkbox.setAttribute("aria-label", `Select ${row.path}`);
      checkbox.addEventListener("change", () => { if (checkbox.checked) chosen.set(row.id, row); else chosen.delete(row.id); selectedChanged(); });
      selectCell.append(checkbox);
      const location = node("td", "location");
      const link = node("a", "", row.name); link.href = `/web/stock/location/${row.id}`;
      location.append(link, node("span", "small", row.path));
      const stock = node("td", "stock");
      stock.append(node("strong", "", `${row.part_count} ${row.part_count === 1 ? "part" : "parts"}`), node("span", "small", `${row.stock_items} stock ${row.stock_items === 1 ? "record" : "records"}`));
      if (row.part_names?.length) stock.append(node("span", "small", `${row.part_names.join(", ")}${row.part_count > row.part_names.length ? `, +${row.part_count - row.part_names.length} more` : ""}`));
      const mapping = node("td", "mapping");
      mapping.append(node("span", "", row.controller || "—"));
      if (row.leds.length) mapping.append(node("span", "small", `LED${row.leds.length === 1 ? "" : "s"} ${row.leds.join(", ")}`));
      const state = node("td"); state.append(node("span", `badge ${row.state}`, stateLabel(row.state)));
      if (row.error) state.append(node("span", "small", row.error));
      const actions = node("td", "row-actions");
      if (["mapped", "shared"].includes(row.state)) {
        const locate = node("button", "secondary", "Locate"); locate.type = "button"; locate.dataset.rowLocate = row.id;
        locate.setAttribute("aria-label", `Locate ${row.path}`);
        locate.addEventListener("click", () => hardware({command: "locate", location_ids: [row.id]}, `Located ${row.path}.`));
        actions.append(locate);
      }
      const edit = node("button", "secondary", "Edit"); edit.type = "button"; edit.dataset.rowEdit = row.id;
      edit.setAttribute("aria-label", `Edit mapping for ${row.path}`);
      edit.addEventListener("click", () => openEditor([row])); actions.append(edit);
      tr.append(selectCell, location, stock, mapping, state, actions); body.append(tr);
    }
    $("[data-total]").textContent = `${data.total} ${data.total === 1 ? "location" : "locations"}`;
    $("[data-page-label]").textContent = `Page ${data.page} of ${data.pages}`;
  }
  function chooseLed(cell) {
    for (const button of $$("[data-led-grid] button")) button.setAttribute("aria-pressed", String(Number(button.dataset.led) === cell.led));
    $("[data-test-led]").value = cell.led;
    const detail = $("[data-led-detail]"); detail.replaceChildren(node("strong", "", `LED ${cell.led}`));
    if (!cell.locations.length) detail.append(node("p", "muted", "No locations are assigned to this LED."));
    else {
      if (cell.locations.length > 1) detail.append(node("p", "muted", "This LED is shared. Locating any of these locations lights the same physical LED."));
      const list = node("ul");
      for (const location of cell.locations) list.append(node("li", "", location.path));
      const show = node("button", "secondary", "Show locations"); show.type = "button"; show.dataset.showLocations = "";
      show.addEventListener("click", () => {
        const controller = snapshot.led_map.controller;
        for (const key of [...params.keys()]) params.delete(key); params.set("controller", controller); params.set("led", cell.led);
        load();
      });
      detail.append(list, show);
    }
  }
  function renderTools(data) {
    const controller = data.controllers.find((item) => item.label === data.led_map?.controller);
    choices($("[data-tool-controller]"), data.controllers, null, controller?.label || "");
    $("[data-controller-summary]").textContent = controller
      ? `${controller.used} mapped · ${controller.free} free · ${controller.shared} shared · ${controller.max_leds || "No saved"} LEDs`
      : "No controllers are configured. Add a controller in InvenTree Settings to start mapping.";
    const grid = $("[data-led-grid]"); grid.replaceChildren();
    $("[data-led-detail]").replaceChildren(node("p", "muted", "Choose an LED to see its assigned locations."));
    $("[data-test-led]").value = "";
    if (controller?.max_leds) $("[data-test-led]").max = String(controller.max_leds);
    for (const cell of data.led_map?.cells || []) {
      const button = node("button", cell.locations.length > 1 ? "shared" : cell.locations.length ? "used" : "", String(cell.led));
      button.type = "button"; button.dataset.led = cell.led;
      button.setAttribute("aria-label", `LED ${cell.led}, ${cell.locations.length} assigned locations`);
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => chooseLed(cell)); grid.append(button);
    }
    if (controller && !controller.max_leds) grid.append(node("p", "muted", "Sync or save this controller’s LED count in Plugin Configuration before mapping or testing LEDs."));
    $("[data-led-page-label]").textContent = data.led_map?.cells.length
      ? `LEDs ${data.led_map.cells[0].led}–${data.led_map.cells.at(-1).led} of ${controller.max_leds}` : "";
  }
  function render(data) {
    const tools = params.get("view") === "tools";
    $("[data-locations]").hidden = tools; $("[data-tools]").hidden = !tools;
    for (const button of $$("[data-view]")) button.setAttribute("aria-pressed", String((button.dataset.view === "tools") === tools));
    const summary = $("[data-summary]"); summary.replaceChildren();
    for (const [value, label] of [[data.summary.total, "storage locations"], [data.summary.mapped, "mapped locations"], [data.summary.needs_led, "stocked locations needing mapping"]]) {
      const card = node("div", "summary-item"); card.append(node("strong", "", String(value || 0)), node("span", "", label)); summary.append(card);
    }
    choices(filters.elements.root, data.roots, "All areas", params.get("root") || "");
    choices(filters.elements.controller, data.controllers, "All controllers", params.get("controller") || "");
    filters.elements.q.value = params.get("q") || "";
    filters.elements.state.value = params.get("state") || "all";
    $("[data-led-filter]").value = params.get("led") || "";
    renderRows(data); renderTools(data);
  }
  async function load(message = "") {
    if (busy) return;
    const revision = ++loadRevision;
    loadController?.abort(); loadController = new AbortController();
    loading = true; chosen.clear(); selectedChanged();
    status("Loading dashboard…"); $("[data-retry]").hidden = true;
    try {
      const data = await request(`${config.data_url}?${params}`, undefined, loadController.signal);
      if (revision !== loadRevision) return;
      snapshot = data;
      params.set("page", data.page);
      if (data.led_map) params.set("led_page", data.led_map.page);
      history.replaceState(null, "", `${window.location.pathname}?${params}`);
      render(data);
      status(message, message ? "success" : "");
    } catch (error) {
      if (revision !== loadRevision || error.name === "AbortError") return;
      snapshot = null;
      $("[data-rows]").replaceChildren();
      status(`${message ? `${message} ` : ""}Could not refresh the dashboard. ${error.message}`, "error");
      $("[data-retry]").hidden = false;
    } finally {
      if (revision === loadRevision) { loading = false; updateControls(); }
    }
  }
  function invalidateReview() {
    review = null; reviewedPayload = null; $("[data-review]").hidden = true;
    status("", "", $("[data-editor-status]")); updateControls();
  }
  function modeChanged() {
    const mode = editorForm.elements.mode.value;
    for (const field of $$("[data-assignment-field]")) field.hidden = mode === "remove";
    $("[data-mode-help]").textContent = mode === "remove" ? "Remove only the LED assignments for the selected locations. Stock and locations remain in place."
      : mode === "same" ? (editRows.length === 1 ? "Enter one LED number, or several numbers separated by commas." : "Every selected location will share the entered LED numbers. Shared LEDs are supported.")
        : "For several locations, enter one starting LED. Locations are assigned in the order shown in the review.";
    invalidateReview();
  }
  function openEditor(rows) {
    if (busy || loading) return;
    editRows = rows;
    $("[data-editor-description]").textContent = rows.length === 1 ? rows[0].path : `${rows.length} selected locations`;
    choices(editorForm.elements.controller, snapshot.controllers, "Choose controller", rows[0].controller || "");
    editorForm.elements.mode.replaceChildren(
      ...(rows.length === 1 ? [new Option("Assign LED(s)", "same")] : [new Option("Sequential LEDs", "sequential"), new Option("Same LED(s) for every location", "same")]),
      new Option("Remove mapping", "remove"),
    );
    editorForm.elements.mode.value = rows.length === 1 ? "same" : "sequential";
    editorForm.elements.leds.value = rows.length === 1 ? rows[0].leds.join(", ") : "";
    modeChanged(); editor.showModal();
  }
  function editorPayload() {
    const mode = editorForm.elements.mode.value;
    const parts = editorForm.elements.leds.value.split(/[,\s]+/).filter(Boolean);
    if (mode !== "remove" && (!parts.length || parts.some((part) => !/^\d+$/.test(part) || !Number.isSafeInteger(Number(part)) || Number(part) < 1))) throw new Error("Enter whole LED numbers, for example 15 or 15,16,17.");
    return {location_ids: editRows.map((row) => row.id), mode, ...(mode === "remove" ? {} : {controller: editorForm.elements.controller.value, leds: [...new Set(parts.map(Number))]})};
  }
  function renderReview(data) {
    const body = $("[data-review-rows]"); body.replaceChildren();
    for (const change of data.changes) {
      const row = node("tr");
      row.append(node("td", "", change.path), node("td", "", mappingText(change.before)), node("td", "", mappingText(change.after)));
      body.append(row);
    }
    const note = $("[data-sharing-note]"); note.replaceChildren();
    if (data.shared_leds.length || data.shared_with.length) {
      note.append(node("strong", "", "Shared LED assignment"), node("p", "", "These locations will light the same physical LEDs. You can save this if the sharing is intentional."));
      const list = node("ul");
      if (data.shared_leds.length) list.append(node("li", "", `Selected locations share LEDs ${data.shared_leds.join(", ")}.`));
      for (const item of data.shared_with) list.append(node("li", "", `LED ${item.led} is also assigned to ${item.path}.`));
      note.append(list);
    }
    $("[data-save]").textContent = reviewedPayload.mode === "remove" ? "Remove mappings" : "Save mappings";
    $("[data-review]").hidden = false;
  }
  async function hardware(payload, message) {
    if (busy || loading) return;
    busy = true; updateControls(); status("Sending locator command…");
    try { await request(config.action_url, payload); status(message, "success"); }
    catch (error) { status(error.message, "error"); if (error.code === "mapping_changed") $("[data-retry]").hidden = false; }
    finally { busy = false; updateControls(); }
  }

  filters.addEventListener("submit", (event) => {
    event.preventDefault();
    if (busy || loading) return;
    for (const key of ["q", "root", "controller", "state"]) {
      const value = filters.elements[key].value.trim(); if (value && value !== "all") params.set(key, value); else params.delete(key);
    }
    const led = $("[data-led-filter]").value; if (led) params.set("led", led); else params.delete("led");
    params.delete("page"); load();
  });
  $("[data-led-filter]").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); filters.requestSubmit(); } });
  $("[data-reset]").addEventListener("click", () => { for (const key of [...params.keys()]) params.delete(key); load(); });
  $("[data-retry]").addEventListener("click", () => load());
  for (const button of $$("[data-view]")) button.addEventListener("click", () => {
    if (button.dataset.view === "tools") params.set("view", "tools"); else params.delete("view");
    params.delete("led_page"); load();
  });
  for (const button of $$("[data-page]")) button.addEventListener("click", () => { params.set("page", snapshot.page + (button.dataset.page === "next" ? 1 : -1)); load(); });
  for (const button of $$("[data-led-page]")) button.addEventListener("click", () => { params.set("led_page", snapshot.led_map.page + (button.dataset.ledPage === "next" ? 1 : -1)); load(); });
  $("[data-tool-controller]").addEventListener("change", (event) => { params.set("controller", event.target.value); params.delete("led_page"); load(); });
  $("[data-select-all]").addEventListener("change", (event) => {
    chosen = event.target.checked ? new Map(snapshot.rows.map((row) => [row.id, row])) : new Map(); selectedChanged();
  });
  $("[data-edit-selected]").addEventListener("click", () => openEditor(snapshot.rows.filter((row) => chosen.has(row.id))));
  $("[data-locate-selected]").addEventListener("click", () => hardware({command: "locate", location_ids: [...chosen.keys()]}, `Located ${chosen.size} selected locations.`));
  $("[data-off]").addEventListener("click", () => hardware({command: "off"}, "Locator lights switched off."));
  $("[data-test-form]").addEventListener("submit", (event) => {
    event.preventDefault();
    const controller = snapshot?.led_map?.controller;
    const led = Number($("[data-test-led]").value);
    if (controller && Number.isInteger(led) && led > 0) hardware({command: "test", controller, led}, `Testing ${controller} LED ${led}.`);
  });
  $("[data-close-editor]").addEventListener("click", () => editor.close());
  editor.addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
  editorForm.addEventListener("input", invalidateReview);
  editorForm.elements.mode.addEventListener("change", modeChanged);
  editorForm.addEventListener("submit", async (event) => {
    event.preventDefault(); if (busy) return;
    invalidateReview();
    let payload;
    try { payload = editorPayload(); } catch (error) { status(error.message, "error", $("[data-editor-status]")); return; }
    busy = true; updateControls(); status("Checking changes…", "", $("[data-editor-status]"));
    try {
      const data = await request(config.action_url, {command: "preview", ...payload});
      review = data.review; reviewedPayload = payload; renderReview(review);
      status("Review the assignments below, then save.", "", $("[data-editor-status]"));
    } catch (error) { status(error.message, "error", $("[data-editor-status]")); }
    finally { busy = false; updateControls(); }
  });
  $("[data-save]").addEventListener("click", async () => {
    if (busy || !review) return;
    busy = true; updateControls(); status("Saving mappings…", "", $("[data-editor-status]"));
    let saved = null;
    try {
      saved = await request(config.action_url, {command: "save", ...reviewedPayload, revision: review.revision});
      editor.close(); review = null;
    } catch (error) {
      review = null; $("[data-review]").hidden = true;
      status(error.message, "error", $("[data-editor-status]"));
    } finally { busy = false; updateControls(); }
    if (saved) await load(`Saved ${saved.saved} location ${saved.saved === 1 ? "mapping" : "mappings"}.`);
  });
  load();
})();
