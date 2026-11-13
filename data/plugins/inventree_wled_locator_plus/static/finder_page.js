(() => {
  "use strict";

  const config = JSON.parse(document.getElementById("finder-config").textContent);
  const find = (name) => document.querySelector(`[data-${name}]`);
  const form = find("search-form");
  const input = document.getElementById("part-queries");
  const csrfToken = form.elements.csrfmiddlewaretoken.value;
  const selected = new Map();
  let preview = null;
  let revision = 0;
  let previewTimer = null;
  let previewRequest = null;
  let searchBusy = false;
  let hardwareBusy = false;
  let lastLocated = null;
  let searchGeneration = 0;
  let resultGroups = [];
  const maxSavedText = 8192;
  let saveTimer = null;
  let stateDirty = false;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function status(name, text, kind = "") {
    const node = find(name);
    node.textContent = text;
    node.classList.toggle("error", kind === "error");
    node.classList.toggle("success", kind === "success");
  }

  function recoveryMessage(text) {
    find("recovery-status").textContent = text;
  }

  function saveState() {
    clearTimeout(saveTimer);
    if (!stateDirty) return;
    stateDirty = false;
    if (!config.storage_key) return;
    try {
      // Remove first when the list is empty so even a full storage quota cannot
      // leave cleared IDs waiting to reappear after a refresh.
      if (!selected.size) window.localStorage.removeItem(config.storage_key);
      const text = input.value.length <= maxSavedText ? input.value : "";
      if (selected.size || text) {
        window.localStorage.setItem(config.storage_key, JSON.stringify({
          version: 1, part_ids: [...selected.keys()], search_text: text,
        }));
      }
      recoveryMessage(input.value.length > maxSavedText
        ? "Selected parts are remembered, but this search text is too long to save."
        : "Search text and selected parts are remembered in this browser.");
    } catch {
      // Prefer losing recovery over restoring an older selection after a failed
      // write. The current page and its explicit locate actions keep working.
      try { window.localStorage.removeItem(config.storage_key); } catch { /* Storage may be blocked. */ }
      recoveryMessage("Your list works on this page, but this browser could not save it for next time.");
    }
  }

  function restoreState() {
    if (!config.storage_key) {
      recoveryMessage("Your list works on this page. Browser recovery is unavailable for this session.");
      return;
    }
    try {
      const raw = window.localStorage.getItem(config.storage_key);
      if (raw === null) return;
      let state;
      try {
        if (typeof raw !== "string" || raw.length > 65536) throw new Error("Invalid saved list");
        state = JSON.parse(raw);
        if (!state || state.version !== 1 || !Array.isArray(state.part_ids)
            || state.part_ids.length > config.max_selected_parts
            || state.part_ids.some((id) => !Number.isSafeInteger(id) || id < 1)
            || typeof state.search_text !== "string" || state.search_text.length > maxSavedText) {
          throw new Error("Invalid saved list");
        }
      } catch {
        window.localStorage.removeItem(config.storage_key);
        recoveryMessage("The saved list could not be restored. You can start a new list.");
        return;
      }
      input.value = state.search_text;
      for (const id of new Set(state.part_ids)) {
        selected.set(id, {part: {id, name: `Part #${id}`}, restoring: true});
      }
      if (selected.size) {
        selectionChanged(false);
        status("preview-status", "Restored your saved list. Checking current stock and mappings…");
      }
    } catch {
      recoveryMessage("Your list works on this page, but browser recovery is unavailable.");
    }
  }

  function validatePreview(payload) {
    const ids = [...selected.keys()];
    if (!Array.isArray(payload.part_ids) || payload.part_ids.length !== ids.length
        || payload.part_ids.some((id, index) => id !== ids[index])
        || typeof payload.can_locate !== "boolean" || !Array.isArray(payload.parts)
        || !Array.isArray(payload.missing_part_ids)) {
      throw new Error("The location check was incomplete. Retry the check before locating.");
    }
    const checked = new Set();
    for (const part of payload.parts) {
      const id = part.part?.id;
      if (!selected.has(id) || checked.has(id) || typeof part.can_locate !== "boolean"
          || typeof (part.part.full_name || part.part.name) !== "string"
          || !Array.isArray(part.availability?.locations)) {
        throw new Error("The location check was incomplete. Retry the check before locating.");
      }
      checked.add(id);
    }
    for (const id of payload.missing_part_ids) {
      if (!selected.has(id) || checked.has(id)) throw new Error("The location check was incomplete. Retry the check before locating.");
      checked.add(id);
    }
    if (checked.size !== ids.length || (payload.can_locate && (payload.missing_part_ids.length
        || payload.parts.some((part) => !part.can_locate || !canLocate(part))))) {
      throw new Error("The location check was incomplete. Retry the check before locating.");
    }
  }

  function signature() {
    return [...selected.keys()].join(",");
  }

  function canLocate(candidate) {
    return (candidate.availability?.locations || []).some((location) => location.can_locate === true);
  }

  function partThumbnail(part) {
    const frame = element("div", undefined, "part-thumbnail");
    frame.setAttribute("aria-hidden", "true");
    const placeholder = element("span", "No image", "image-placeholder");
    frame.append(placeholder);
    const sources = [];
    for (const value of [part.thumbnail_url, part.image_url]) {
      if (typeof value !== "string" || !value) continue;
      try {
        const url = new URL(value, `${window.location.origin}/`);
        if (["http:", "https:"].includes(url.protocol) && !sources.includes(url.href)) sources.push(url.href);
      } catch {
        // A malformed media URL should not prevent choosing the part.
      }
    }
    if (!sources.length) return frame;
    const image = element("img");
    image.alt = ""; // The adjacent heading names the part.
    image.width = 64;
    image.height = 64;
    image.loading = "lazy";
    image.decoding = "async";
    let nextSource = 0;
    image.addEventListener("load", () => {
      placeholder.hidden = true;
      frame.classList.add("has-image");
    });
    image.addEventListener("error", () => {
      if (nextSource < sources.length) {
        image.src = sources[nextSource++];
      } else {
        image.remove();
      }
    });
    frame.append(image);
    image.src = sources[nextSource++];
    return frame;
  }

  async function post(url, payload, signal) {
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(payload),
        signal,
      });
    } catch (error) {
      if (error.name === "AbortError") throw error;
      throw new Error("Could not reach InvenTree. Check your connection and try again.");
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.success !== true) {
      let message = body.error || "The request could not be completed. Please try again.";
      if (response.status === 401 || response.status === 403) {
        message = "Your session or request token has expired. Reload this page and sign in again.";
      } else if (body.code === "locator_busy") {
        message = "Another locate action is running. Please try again shortly.";
      }
      const error = new Error(message);
      error.payload = body;
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function updateControls() {
    find("search-button").disabled = searchBusy || hardwareBusy;
    find("search-button").textContent = searchBusy ? "Searching…" : "Search parts";
    input.disabled = hardwareBusy;
    find("clear-selection").disabled = hardwareBusy || selected.size === 0;
    find("locate").disabled = hardwareBusy || !preview?.can_locate || selected.size === 0;
    find("off").disabled = hardwareBusy;
    find("retry-preview").disabled = hardwareBusy;
    find("selected-count").textContent = String(selected.size);
    find("selection-shortcut").hidden = selected.size === 0;
    find("selection-shortcut").textContent = `View selected (${selected.size})`;
    for (const group of resultGroups) {
      group.more.disabled = searchBusy || hardwareBusy || group.loading;
      group.more.textContent = group.loading ? "Loading…" : group.error ? "Retry load more" : "Load more";
    }
    document.querySelectorAll("[data-remove-part]").forEach((button) => { button.disabled = hardwareBusy; });
    document.querySelectorAll("[data-part-toggle]").forEach((button) => {
      const added = selected.has(Number(button.dataset.partToggle));
      button.disabled = hardwareBusy || (!added && button.dataset.locatable !== "true");
      button.textContent = added ? "Remove" : button.dataset.locatable === "true" ? "Add" : "Unavailable";
      button.classList.toggle("secondary", added);
      button.setAttribute("aria-pressed", String(added));
      button.setAttribute("aria-label", `${added ? "Remove" : "Add"} ${button.dataset.partName} ${added ? "from" : "to"} selection`);
      button.closest("[data-match]").classList.toggle("selected", added);
    });
  }

  function appendAvailability(parent, availability, compact = false) {
    const locations = availability?.locations || [];
    const stock = element("p", `In stock: ${availability?.in_stock_quantity || "0"}`, "stock-summary");
    if (!locations.some((location) => location.can_locate)) stock.classList.add("unavailable");
    parent.append(stock);
    if (!locations.length) {
      parent.append(element("p", "No in-stock items to locate.", "muted"));
      return;
    }
    const unavailable = locations.filter((location) => !location.can_locate).length;
    if (unavailable) {
      parent.append(element("p", `${unavailable} stock location${unavailable === 1 ? "" : "s"} can’t be lit. Check the location details.`, "location-warning"));
    }
    const list = element("ul", undefined, "location-list");
    for (const entry of locations) {
      const row = element("li");
      row.append(element("span", entry.location?.path || entry.location?.name || "No assigned location"));
      row.append(element("span", ` · ${entry.in_stock_quantity} in stock`, "location-quantity"));
      if (!entry.can_locate && entry.location) row.append(element("span", "Indicator setup needed", "location-warning"));
      list.append(row);
    }
    if ((compact && locations.length > 1) || locations.length > 3) {
      const details = element("details");
      details.append(element("summary", `View ${locations.length} stock locations`), list);
      parent.append(details);
    } else {
      parent.append(list);
    }
  }

  function renderSelection() {
    const container = find("selected-parts");
    container.replaceChildren();
    const freshParts = new Map((preview?.parts || []).map((part) => [part.part.id, part]));
    for (const [id, candidate] of selected) {
      const fresh = freshParts.get(id);
      const card = element("article", undefined, "selected-part");
      const heading = element("div", undefined, "match-heading");
      heading.append(element("h3", fresh?.part.full_name || candidate.part.full_name || candidate.part.name));
      const remove = element("button", "Remove", "text-button");
      remove.type = "button";
      remove.dataset.removePart = String(id);
      remove.setAttribute("aria-label", `Remove ${candidate.part.full_name || candidate.part.name} from selection`);
      remove.addEventListener("click", () => {
        selected.delete(id);
        selectionChanged();
      });
      heading.append(remove);
      card.append(heading);
      if (preview?.missing_part_ids?.includes(id)) {
        card.append(element("p", "This part is no longer available. Remove it and search again.", "location-warning"));
      } else if (candidate.restoring && !fresh) {
        card.append(element("p", "Current stock and mappings have not been checked yet.", "muted"));
      } else {
        appendAvailability(card, fresh?.availability || candidate.availability);
        if (fresh && !fresh.can_locate) card.append(element("p", "This part has no usable mapped stock location.", "location-warning"));
      }
      container.append(card);
    }
  }

  function applyPreview(payload) {
    preview = payload;
    find("retry-preview").hidden = true;
    for (const part of payload.parts || []) {
      const candidate = selected.get(part.part.id);
      if (candidate) {
        candidate.part = {...candidate.part, ...part.part};
        candidate.availability = part.availability;
        candidate.restoring = false;
      }
    }
    renderSelection();
    if (payload.can_locate) {
      const count = payload.summary?.unique_locations || 0;
      status("preview-status", `Ready to locate ${selected.size} part${selected.size === 1 ? "" : "s"} across ${count} stock location${count === 1 ? "" : "s"}.`);
    } else {
      status("preview-status", "Some selected parts cannot be located. Review the list below.", "error");
    }
    updateControls();
  }

  async function refreshPreview(version) {
    previewRequest = new AbortController();
    try {
      const payload = await post(config.preview_url, { part_ids: [...selected.keys()] }, previewRequest.signal);
      if (version === revision) {
        validatePreview(payload);
        applyPreview(payload);
      }
    } catch (error) {
      if (version === revision && error.name !== "AbortError") {
        status("preview-status", error.message || "Could not check stock locations. Try the selection again.", "error");
        find("retry-preview").hidden = false;
      }
    }
  }

  function selectionChanged(persist = true) {
    if (persist) {
      stateDirty = true;
      saveState();
    }
    revision += 1;
    preview = null;
    find("retry-preview").hidden = true;
    clearTimeout(previewTimer);
    previewRequest?.abort();
    renderSelection();
    updateControls();
    if (lastLocated !== null && lastLocated !== signature()) {
      status("action-status", "Selection changed. Choose Locate selected to update the lights, or All off.");
    }
    if (selected.size) {
      status("preview-status", "Checking stock locations…");
      const version = revision;
      previewTimer = setTimeout(() => refreshPreview(version), 120);
    } else {
      status("preview-status", "Choose parts from the matches.");
    }
  }

  function toggle(candidate) {
    const id = candidate.part.id;
    if (hardwareBusy) return;
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      if (!canLocate(candidate)) return;
      if (selected.size >= config.max_selected_parts) {
        status("preview-status", `You can select up to ${config.max_selected_parts} parts.`, "error");
        return;
      }
      selected.set(id, candidate);
    }
    selectionChanged();
  }

  function matchCard(candidate) {
    const card = element("article", undefined, "match");
    card.dataset.match = "";
    const heading = element("div", undefined, "match-heading");
    const identity = element("div", undefined, "match-identity");
    const info = element("div");
    info.append(element("h3", candidate.part.full_name || candidate.part.name));
    if (candidate.part.IPN && candidate.part.IPN !== candidate.part.name) info.append(element("p", candidate.part.IPN, "muted"));
    if (candidate.part.description) info.append(element("p", candidate.part.description, "part-description"));
    const button = element("button", "Add");
    button.type = "button";
    button.dataset.partToggle = String(candidate.part.id);
    button.dataset.partName = candidate.part.full_name || candidate.part.name;
    button.dataset.locatable = String(canLocate(candidate));
    button.addEventListener("click", () => toggle(candidate));
    identity.append(partThumbnail(candidate.part), info);
    heading.append(identity, button);
    card.append(heading);
    appendAvailability(card, candidate.availability, true);
    return card;
  }

  function appendMatches(group, result) {
    for (const candidate of result.matches || []) {
      if (group.ids.has(candidate.part.id)) continue;
      group.ids.add(candidate.part.id);
      group.list.append(matchCard(candidate));
    }
    group.cursor = result.next_cursor || null;
    group.more.hidden = !group.cursor;
    group.count.textContent = `${group.ids.size} match${group.ids.size === 1 ? "" : "es"}${result.has_more ? " shown" : ""}`;
    if (!group.ids.size) group.list.append(element("p", "No matches. Try a part number, a shorter name, or different keywords.", "empty-state"));
  }

  async function loadMore(group) {
    if (searchBusy || hardwareBusy || group.loading || !group.cursor) return;
    const generation = searchGeneration;
    const controller = new AbortController();
    const cursor = group.cursor;
    group.controller = controller;
    group.loading = true;
    group.error = false;
    group.status.textContent = "Loading more matches…";
    group.status.classList.remove("error");
    group.node.setAttribute("aria-busy", "true");
    updateControls();
    try {
      const payload = await post(config.search_url, {queries: [group.query], cursor}, controller.signal);
      if (generation !== searchGeneration || !group.node.isConnected) return;
      const result = payload.results?.[0];
      if (!result || result.query !== group.query || !Array.isArray(result.matches)
          || typeof result.has_more !== "boolean"
          || (result.has_more && (typeof result.next_cursor !== "string" || !result.next_cursor || result.next_cursor === cursor))) {
        throw new Error("Search results changed. Search again to refresh the matches.");
      }
      appendMatches(group, result);
      group.status.textContent = `${group.ids.size} matches shown.${group.cursor ? "" : " All current matches loaded."}`;
    } catch (error) {
      if (generation !== searchGeneration || error.name === "AbortError") return;
      group.error = true;
      group.status.classList.add("error");
      group.status.textContent = error.message || "Could not load more matches. Try again.";
    } finally {
      if (group.controller === controller) {
        group.loading = false;
        group.controller = null;
        group.node.setAttribute("aria-busy", "false");
        updateControls();
      }
    }
  }

  function renderResults(payload) {
    const container = find("results");
    container.replaceChildren();
    resultGroups = [];
    const results = payload.results || [];
    find("results-count").textContent = `${results.length} search${results.length === 1 ? "" : "es"}`;
    for (const result of results) {
      const node = element("section", undefined, "query-group");
      const title = element("div", undefined, "query-heading");
      const count = element("span", "", "muted");
      title.append(element("h3", result.query), count);
      node.append(title);
      if (result.value_match?.display) node.append(element("p", `Value matching: ${result.value_match.display}`, "query-note"));
      const list = element("div");
      const more = element("button", "Load more", "secondary");
      more.type = "button";
      more.dataset.loadMore = "";
      more.setAttribute("aria-label", `Load more matches for ${result.query}`);
      const progress = element("p", "", "status query-note");
      progress.setAttribute("role", "status");
      progress.setAttribute("aria-live", "polite");
      const group = {query: result.query, node, list, more, count, status: progress, ids: new Set(), loading: false, error: false};
      more.addEventListener("click", () => loadMore(group));
      appendMatches(group, result);
      node.append(list, more, progress);
      container.append(node);
      resultGroups.push(group);
    }
    updateControls();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (searchBusy || hardwareBusy) return;
    const queries = input.value.split(/[\n;]+/u).map((query) => query.trim().replace(/\s+/gu, " ")).filter(Boolean);
    if (!queries.length || queries.length > config.max_queries) {
      status("search-status", `Enter between 1 and ${config.max_queries} parts, one per line.`, "error");
      return;
    }
    if (queries.some((query) => query.length > config.max_query_length || query.split(" ").length > config.max_query_terms)) {
      status("search-status", `Keep each search to at most ${config.max_query_length} characters and ${config.max_query_terms} words.`, "error");
      return;
    }
    stateDirty = true;
    saveState();
    searchGeneration += 1;
    for (const group of resultGroups) {
      group.controller?.abort();
      group.controller = null;
      group.loading = false;
      group.error = false;
      group.status.textContent = "";
      group.node.setAttribute("aria-busy", "false");
    }
    searchBusy = true;
    find("results-region").setAttribute("aria-busy", "true");
    status("search-status", "Searching for matching parts…");
    updateControls();
    try {
      const payload = await post(config.search_url, { queries });
      renderResults(payload);
      const matched = payload.summary?.matched_queries || 0;
      status("search-status", `${matched} of ${queries.length} searches matched. Choose the parts you need below.`);
    } catch (error) {
      status("search-status", error.message || "Could not search. Check the connection and try again.", "error");
    } finally {
      searchBusy = false;
      find("results-region").setAttribute("aria-busy", "false");
      updateControls();
    }
  });

  input.addEventListener("input", () => {
    stateDirty = true;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveState, 250);
  });
  input.addEventListener("change", () => { stateDirty = true; saveState(); });
  window.addEventListener("pagehide", saveState);
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && selected.size) {
      lastLocated = null;
      status("action-status", "");
      selectionChanged(false);
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  find("clear-selection").addEventListener("click", () => {
    if (hardwareBusy) return;
    selected.clear();
    selectionChanged();
  });

  find("retry-preview").addEventListener("click", () => {
    if (!hardwareBusy && selected.size) selectionChanged(false);
  });

  async function hardwareAction(off) {
    if (hardwareBusy || (!off && (!selected.size || !preview?.can_locate))) return;
    hardwareBusy = true;
    find("locate").textContent = off ? "Locate selected" : "Locating…";
    find("off").textContent = off ? "Turning off…" : "All off";
    status("action-status", off ? "Turning off locator lights…" : "Locating the selected parts together…");
    updateControls();
    try {
      const payload = await post(off ? config.off_url : config.locate_url, off ? {} : { part_ids: [...selected.keys()] });
      if (off) {
        lastLocated = null;
        status("action-status", "All locator lights are off.", "success");
      } else {
        applyPreview(payload);
        lastLocated = signature();
        status("action-status", selected.size === 1
          ? "Part located. Its mapped locations are lit."
          : `${selected.size} parts located together. Their mapped locations are lit.`, "success");
      }
    } catch (error) {
      if (error.payload?.preview) applyPreview(error.payload.preview);
      const message = error.payload?.code === "selection_not_locatable"
        ? "Some selected parts can no longer be located. Review the list and remove unavailable parts."
        : error.payload?.code === "locator_busy" || error.status === 401 || error.status === 403
          ? error.message
          : "Could not complete the light update. Some lights may have changed; check them before retrying.";
      status("action-status", message, "error");
    } finally {
      hardwareBusy = false;
      find("locate").textContent = "Locate selected";
      find("off").textContent = "All off";
      updateControls();
    }
  }

  find("locate").addEventListener("click", () => hardwareAction(false));
  find("off").addEventListener("click", () => hardwareAction(true));
  restoreState();
  updateControls();
})();
