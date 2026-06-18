import {
    bindDashboardButton,
    buttonStyle,
    clearMappingUrl,
    actionSummaryHtml,
    compactIndicatorText,
    displayLed,
    escapeHtml,
    getLedValue,
    ledInputMessage,
    ledFormHtml,
    locationName,
    mappingActionHtml,
    normalizeLed,
    openDashboardButtonHtml,
    registerLedUrl,
    resultStyle,
    runJsonRequest,
    splitLocationPath,
    testLedUrl,
} from "./panel_common.js";

export function renderStockLocationPanel(target, data) {
    renderStockLocationLocator(target, data, {
        description: "Locate this stock location, or assign the external indicator stored as location metadata.",
    });
}

function renderStockLocationLocator(target, data, options) {
    if (!target) {
        console.error("WLED Locator Plus: no StockLocation external indicator panel target provided");
        return;
    }

    const context = data?.context || {};
    const locateUrl = context.locate_url;
    const registerUrlBase = context.register_url_base;
    const testUrlBase = context.test_url_base || "/plugin/wled-locator-plus/test/";
    const testControllerUrlBase = context.test_controller_url_base || "/plugin/wled-locator-plus/test/";
    const pluginPageUrl = context.plugin_page_url || "/plugin/wled-locator-plus/";
    const maxLed = Number.isInteger(context.max_led) ? context.max_led : 58;
    const controllers = Array.isArray(context.controllers) ? context.controllers : [];
    const hasChildren = Boolean(context.has_children);
    const childCount = Number.isInteger(context.child_count) ? context.child_count : 0;
    const currentLed = normalizeLed(context.current_led);
    const currentController = context.current_controller || context.default_controller || context.primary_controller || "";
    const currentLedText = hasChildren
        ? `Parent location: ${childCount} child location(s)`
        : (currentLed === null ? "No LED mapping saved" : `Current mapping: ${currentController ? `${currentController} / ` : ""}LED ${displayLed(currentLed)}`);
    const currentLedValue = currentLed === null ? "" : currentLed;
    const assignmentHtml = hasChildren
        ? `<p style="margin: 0;">Parent locations are containers. Locating this location will light mapped leaf child locations.</p>`
        : ledFormHtml(maxLed, currentLedValue, controllers, currentController);

    target.innerHTML = `
        <div style="display: grid; gap: 0.75rem; max-width: 38rem;">
            <p style="margin: 0;">
                ${escapeHtml(options.description)}
            </p>
            <p data-current-mapping style="font-weight: 600; margin: 0;">
                ${currentLedText}
            </p>

            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                <button type="button" data-wled-locate style="${buttonStyle("#2364aa")}">
                    Locate This Location
                </button>
                ${openDashboardButtonHtml()}
            </div>

            ${assignmentHtml}

            <div data-wled-result style="${resultStyle()}"></div>
        </div>
    `;

    const locateButton = target.querySelector("[data-wled-locate]");
    const testButton = target.querySelector("[data-wled-test]");
    const clearButton = target.querySelector("[data-wled-clear]");
    const form = target.querySelector("[data-wled-map-form]");
    const result = target.querySelector("[data-wled-result]");
    const currentMapping = target.querySelector("[data-current-mapping]");

    bindDashboardButton(target, pluginPageUrl);

    locateButton.addEventListener("click", async () => {
        await runJsonRequest(locateUrl, locateButton, result, "Locating...", summarizePayload);
    });

    if (!form) {
        return;
    }

    testButton.addEventListener("click", async () => {
        const led = getLedValue(form, maxLed);
        if (led === null) {
            result.textContent = ledInputMessage(form, maxLed);
            return;
        }

        await runJsonRequest(testLedUrl(testControllerUrlBase || testUrlBase, form, led), testButton, result, "Testing LED...", summarizePayload);
    });

    clearButton.addEventListener("click", async () => {
        if (!window.confirm("Clear this StockLocation external indicator mapping?")) {
            return;
        }

        const payload = await runJsonRequest(
            clearMappingUrl(context.stock_location_id),
            clearButton,
            result,
            "Clearing mapping...",
            summarizePayload
        );

        if (payload?.success) {
            form.querySelector("input[name='led']").value = "";
            currentMapping.textContent = "No LED mapping saved";
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const led = getLedValue(form, maxLed);
        if (led === null) {
            result.textContent = ledInputMessage(form, maxLed);
            return;
        }

        const payload = await runJsonRequest(
            registerLedUrl({
                registerUrlBase,
                registerControllerUrlBase: context.register_controller_url_base,
            }, null, form, led),
            form.querySelector("button[type='submit']"),
            result,
            "Saving mapping...",
            summarizePayload
        );

        if (payload?.success) {
            currentMapping.textContent = `Current mapping: ${payload.controller ? `${payload.controller} / ` : ""}LED ${displayLed(led)}`;
        }
    });
}

function summarizePayload(payload) {
    if (!payload?.success) {
        return payload?.error ? `Error: ${payload.error}` : "WLED request failed.";
    }

    if (payload.action === "register-location-led") {
        return mappingActionHtml("Saved mapping:", payload, "StockLocation mapping");
    }

    if (payload.action === "clear-location-indicator") {
        return mappingActionHtml("Cleared mapping:", payload, "No LED assigned");
    }

    if (payload.action === "locate-location") {
        const rows = locationRows(payload);
        const title = rows.length
            ? `${locationName(payload.location)} located using ${rows.length} mapped bin(s):`
            : `${locationName(payload.location)} has no mapped LEDs to locate.`;
        const skipped = Array.isArray(payload.skipped) && payload.skipped.length
            ? [`Skipped ${payload.skipped.length} unmapped child location(s).`]
            : [];
        return actionSummaryHtml(title, rows, skipped);
    }

    if (payload.action === "test") {
        return actionSummaryHtml("Test LED sent:", [{
            location: "",
            bin: "",
            led: `${payload.controller ? `${payload.controller} / ` : ""}LED ${displayLed(payload.led)}`,
            component: "Test only",
        }]);
    }

    if (payload.wled) {
        return `WLED ${payload.wled.address}, marker color ${payload.wled.mark_color}, ${payload.wled.max_leds} LEDs`;
    }

    return "WLED request completed.";
}

function locationRows(payload) {
    const entries = Array.isArray(payload?.lit) && payload.lit.length
        ? payload.lit
        : (payload?.location ? [payload] : []);

    return entries.map((entry) => {
        const parts = splitLocationPath(entry.location);
        return {
            location: parts.location,
            bin: parts.bin,
            led: compactIndicatorText(entry),
            component: entry.item_count ? `${entry.item_count} component(s)` : "Mapped location",
        };
    });
}
