import {
    bindDashboardButton,
    buttonStyle,
    clearMappingUrl,
    actionSummaryHtml,
    compactIndicatorText,
    disableForm,
    displayIndicators,
    displayLedList,
    enableForm,
    escapeHtml,
    fetchJson,
    getLedValues,
    ledInputMessage,
    ledFormHtml,
    mappingActionHtml,
    openDashboardButtonHtml,
    previewStyle,
    registerLedUrl,
    resultStyle,
    runJsonRequest,
    registerPanel,
    setControlDisabled,
    withPanelLoading,
    splitLocationPath,
    testLedUrl,
} from "./panel_common.js";

export function renderStockItemPanel(target, data) {
    renderStockItemLocator(target, data, {
        description: "Locate this stock item, or assign the external indicator saved on its assigned stock location.",
    });
}

function renderStockItemLocator(target, data, options) {
    if (!target) return;
    const context = data?.context || {};
    const locateUrl = context.locate_url;
    const previewUrl = context.preview_url;
    const maxLed = Number.isInteger(context.max_led) ? context.max_led : -1;
    const controllers = Array.isArray(context.controllers) ? context.controllers : [];
    if (!locateUrl) { target.textContent = "External indicator is missing the stock item locate URL."; return; }
    target.innerHTML = `
        <div style="display: grid; gap: 0.75rem; max-width: 42rem;">
            <p style="margin: 0;">${escapeHtml(options.description)}</p>
            <div data-wled-preview style="${previewStyle()}">Loading stock item mapping...</div>
            <button type="button" data-wled-retry-preview hidden>Retry preview</button>
            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                <button type="button" data-wled-locate disabled style="${buttonStyle("#2364aa")}">Locate This Stock Item</button>
                ${openDashboardButtonHtml()}
            </div>
            ${ledFormHtml(maxLed, "", controllers, context.default_controller || "")}
            <div data-wled-result style="${resultStyle()}"></div>
        </div>`;
    registerPanel(target, context);
    bindDashboardButton(target, context.plugin_page_url);
    const locateButton = target.querySelector("[data-wled-locate]");
    const form = target.querySelector("[data-wled-map-form]");
    const preview = target.querySelector("[data-wled-preview]");
    const result = target.querySelector("[data-wled-result]");
    const retry = target.querySelector("[data-wled-retry-preview]");
    let assignedLocationId = null;

    async function refreshPreview() {
        return withPanelLoading(async () => {
            assignedLocationId = null;
            disableForm(form, "Checking stock location...");
            setControlDisabled(locateButton, true);
            retry.hidden = true;
            try {
                if (!previewUrl) throw new Error("Stock item preview URL is not configured.");
                const response = await fetchJson(previewUrl);
                if (typeof response.can_locate !== "boolean" || !response.item) throw new Error("Invalid stock item preview. Refresh the page.");
                preview.innerHTML = renderPreview(response);
                assignedLocationId = Number.isSafeInteger(response.location?.id) ? response.location.id : null;
                const input = form.querySelector("input[name='led']");
                input.value = response.location ? displayLedList(response.leds || []) : "";
                if (assignedLocationId && response.mapping_editable !== false && controllers.some((item) => item.reachable !== false)) {
                    enableForm(form);
                    const select = form.querySelector("select[name='controller']");
                    const label = response.controller || context.default_controller || "";
                    select.value = [...select.options].some((option) => option.value === label) ? label : "";
                } else disableForm(form, assignedLocationId ? "Assign LEDs to leaf locations with a configured controller." : "This stock item has no assigned stock location.");
                setControlDisabled(locateButton, !response.can_locate);
                locateButton.title = response.can_locate ? "" : response.reason || "This stock item cannot be located yet.";
            } catch (error) {
                preview.textContent = `Preview request failed: ${error.message}`;
                disableForm(form, "Retry the preview before editing this stock location.");
                retry.hidden = false;
                throw error;
            }
        });
    }
    retry.addEventListener("click", () => refreshPreview().catch(() => {}));
    locateButton.addEventListener("click", () => runJsonRequest(locateUrl, locateButton, result, "Locating...", summarizePayload, {onSuccess: refreshPreview}));
    const testButton = target.querySelector("[data-wled-test]");
    testButton.addEventListener("click", () => {
        const leds = getLedValues(form, maxLed);
        if (!leds.length) { result.textContent = ledInputMessage(form, maxLed); return; }
        return runJsonRequest(testLedUrl(context.test_controller_url_base || context.test_url_base, form, leds), testButton, result, "Testing LED...", summarizePayload);
    });
    const clearButton = target.querySelector("[data-wled-clear]");
    clearButton.addEventListener("click", () => {
        if (!assignedLocationId || !window.confirm("Clear the external indicator mapping for this stock item's StockLocation?")) return;
        return runJsonRequest(clearMappingUrl(assignedLocationId), clearButton, result, "Clearing mapping...", summarizePayload, {onSuccess: refreshPreview});
    });
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!assignedLocationId) { result.textContent = "This stock item has no checked stock location. Retry the preview."; return; }
        const leds = getLedValues(form, maxLed);
        if (!leds.length) { result.textContent = ledInputMessage(form, maxLed); return; }
        return runJsonRequest(registerLedUrl({
            registerLocationUrlBase: context.register_location_url_base,
            registerLocationUrlSuffix: context.register_location_url_suffix,
            registerLocationControllerUrlBase: context.register_location_controller_url_base,
        }, assignedLocationId, form, leds), form.querySelector("button[type='submit']"), result, "Saving mapping...", summarizePayload, {onSuccess: refreshPreview});
    });
    refreshPreview().catch(() => {});
}

function renderPreview(payload) {
    if (!payload?.success) {
        const error = payload?.error || "Preview request failed.";
        return `<strong>Preview error:</strong> ${escapeHtml(error)}`;
    }

    const item = payload.item || {};
    const location = payload.location;
    const locationText = location?.path || location?.name || "No location assigned";
    const ledText = Array.isArray(payload.leds) && payload.leds.length
        ? formatIndicators(payload)
        : "No LED mapping";
    const statusText = payload.can_locate ? "Ready to locate" : (payload.reason || "Not ready");

    return `
        <div style="display: grid; gap: 0.45rem;">
            <strong>${escapeHtml(statusText)}</strong>
            <div><strong>Part:</strong> ${escapeHtml(item.part || "")}</div>
            <div><strong>Quantity:</strong> ${escapeHtml(item.quantity || "")}</div>
            <div><strong>Location:</strong> ${escapeHtml(locationText)}</div>
            <div><strong>Mapped LED:</strong> ${escapeHtml(ledText)}</div>
        </div>
    `;
}

function summarizePayload(payload) {
    if (!payload?.success) {
        return payload?.error ? `Error: ${payload.error}` : "WLED request failed.";
    }

    if (payload.action === "locate-stock-item") {
        const rows = stockItemRows(payload);
        const part = payload.item?.part || "Stock item";
        return actionSummaryHtml(`${part} located:`, rows);
    }

    if (payload.action === "register-location-led") {
        return mappingActionHtml("Saved mapping:", payload, "StockLocation mapping");
    }

    if (payload.action === "clear-location-indicator") {
        return mappingActionHtml("Cleared mapping:", payload, "No LED assigned");
    }

    if (payload.action === "test") {
        const parts = splitLocationPath(payload.location);
        return actionSummaryHtml("Test LED sent:", [{
            location: parts.location,
            bin: parts.bin,
            led: compactIndicatorText(payload),
            component: payload.item?.part || "Test only",
        }]);
    }

    if (payload.wled) {
        return `WLED ${payload.wled.address}, marker color ${payload.wled.mark_color}, ${payload.wled.max_leds} LEDs`;
    }

    return "WLED request completed.";
}

function stockItemRows(payload) {
    const entries = Array.isArray(payload?.lit) && payload.lit.length
        ? payload.lit
        : (payload?.location ? [payload] : []);
    const component = payload.item?.part || "";

    return entries.map((entry) => {
        const parts = splitLocationPath(entry.location);
        return {
            location: parts.location,
            bin: parts.bin,
            led: compactIndicatorText(entry),
            component: component || "1 stock item",
        };
    });
}

function formatIndicators(payload) {
    if (Array.isArray(payload.indicators) && payload.indicators.length) {
        return displayIndicators(payload.indicators);
    }

    return `LED ${displayLedList(payload.leds)}`;
}
