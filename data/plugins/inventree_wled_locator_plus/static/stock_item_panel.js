import {
    bindDashboardButton,
    buttonStyle,
    clearMappingUrl,
    actionSummaryHtml,
    compactIndicatorText,
    disableForm,
    displayIndicators,
    displayLed,
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
    splitLocationPath,
    testLedUrl,
} from "./panel_common.js";

export function renderStockItemPanel(target, data) {
    renderStockItemLocator(target, data, {
        description: "Locate this stock item, or assign the external indicator saved on its assigned stock location.",
    });
}

function renderStockItemLocator(target, data, options) {
    if (!target) {
        console.error("WLED Locator Plus: no StockItem external indicator panel target provided");
        return;
    }

    const context = data?.context || {};
    const locateUrl = context.locate_url;
    const previewUrl = context.preview_url;
    const registerLocationUrlBase = context.register_location_url_base || "/plugin/wled-locator-plus/register/location/";
    const registerLocationUrlSuffix = context.register_location_url_suffix || "/led/";
    const testUrlBase = context.test_url_base || "/plugin/wled-locator-plus/test/";
    const testControllerUrlBase = context.test_controller_url_base || "/plugin/wled-locator-plus/test/";
    const pluginPageUrl = context.plugin_page_url || "/plugin/wled-locator-plus/";
    const maxLed = Number.isInteger(context.max_led) ? context.max_led : 58;
    const controllers = Array.isArray(context.controllers) ? context.controllers : [];

    if (!locateUrl) {
        target.innerHTML = "<p>External indicator is missing the stock item locate URL.</p>";
        return;
    }

    target.innerHTML = `
        <div style="display: grid; gap: 0.75rem; max-width: 42rem;">
            <p style="margin: 0;">
                ${escapeHtml(options.description)}
            </p>

            <div data-wled-preview style="${previewStyle()}">
                Loading stock item mapping...
            </div>

            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                <button type="button" data-wled-locate style="${buttonStyle("#2364aa")}">
                    Locate This Stock Item
                </button>
                ${openDashboardButtonHtml()}
            </div>

            ${ledFormHtml(maxLed, "", controllers, context.default_controller || context.primary_controller || "")}

            <div data-wled-result style="${resultStyle()}"></div>
        </div>
    `;

    const locateButton = target.querySelector("[data-wled-locate]");
    const testButton = target.querySelector("[data-wled-test]");
    const clearButton = target.querySelector("[data-wled-clear]");
    const form = target.querySelector("[data-wled-map-form]");
    const preview = target.querySelector("[data-wled-preview]");
    const result = target.querySelector("[data-wled-result]");
    let assignedLocationId = null;

    bindDashboardButton(target, pluginPageUrl);

    if (previewUrl) {
        loadPreview(previewUrl, preview, form, locateButton).then((payload) => {
            assignedLocationId = payload?.location?.id || null;
        });
    } else {
        preview.textContent = "Stock item preview URL is not configured.";
        disableForm(form, "Stock item preview URL is not configured.");
    }

    locateButton.addEventListener("click", async () => {
        await runJsonRequest(locateUrl, locateButton, result, "Locating...", summarizePayload);
    });

    testButton.addEventListener("click", async () => {
        const leds = getLedValues(form, maxLed);
        if (!leds.length) {
            result.textContent = ledInputMessage(form, maxLed);
            return;
        }

        await runJsonRequest(testLedUrl(testControllerUrlBase || testUrlBase, form, leds), testButton, result, "Testing LED...", summarizePayload);
    });

    clearButton.addEventListener("click", async () => {
        if (!assignedLocationId) {
            result.textContent = "This stock item has no assigned stock location to clear.";
            return;
        }

        if (!window.confirm("Clear the external indicator mapping for this stock item's StockLocation?")) {
            return;
        }

        const payload = await runJsonRequest(
            clearMappingUrl(assignedLocationId),
            clearButton,
            result,
            "Clearing mapping...",
            summarizePayload
        );

        if (payload?.success) {
            await loadPreview(previewUrl, preview, form, locateButton);
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!assignedLocationId) {
            result.textContent = "This stock item has no assigned stock location to save an external indicator against.";
            return;
        }

        const leds = getLedValues(form, maxLed);
        if (!leds.length) {
            result.textContent = ledInputMessage(form, maxLed);
            return;
        }

        const saveButton = form.querySelector("button[type='submit']");
        const payload = await runJsonRequest(
            registerLedUrl({
                registerLocationUrlBase,
                registerLocationUrlSuffix,
                registerLocationControllerUrlBase: context.register_location_controller_url_base,
            }, assignedLocationId, form, leds),
            saveButton,
            result,
            "Saving mapping...",
            summarizePayload
        );

        if (payload?.success) {
            await loadPreview(previewUrl, preview, form, locateButton);
            assignedLocationId = payload?.location?.id || assignedLocationId;
        }
    });
}

async function loadPreview(url, preview, form, locateButton) {
    try {
        const response = await fetchJson(url);
        preview.innerHTML = renderPreview(response);

        const locationId = response?.location?.id;
        const input = form.querySelector("input[name='led']");

        if (locationId) {
            enableForm(form);
            input.value = Array.isArray(response?.leds) && response.leds.length
                ? displayLedList(response.leds)
                : displayLed(response?.led);
            const controllerSelect = form.querySelector("select[name='controller']");
            if (controllerSelect && response?.controller) {
                controllerSelect.value = response.controller;
            }
        } else {
            input.value = "";
            disableForm(form, "This stock item has no assigned stock location.");
        }

        if (!response?.can_locate) {
            locateButton.disabled = true;
            locateButton.style.opacity = "0.65";
            locateButton.title = response?.reason || "This stock item cannot be located yet.";
        } else {
            locateButton.disabled = false;
            locateButton.style.opacity = "1";
            locateButton.title = "";
        }

        return response;
    } catch (error) {
        preview.textContent = `Preview request failed: ${error}`;
        disableForm(form, "Preview request failed.");
        return null;
    }
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
