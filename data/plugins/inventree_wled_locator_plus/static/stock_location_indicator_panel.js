import {
    bindDashboardButton,
    buttonStyle,
    clearMappingUrl,
    actionSummaryHtml,
    compactIndicatorText,
    displayLedList,
    escapeHtml,
    getLedValues,
    ledInputMessage,
    ledFormHtml,
    locationName,
    mappingActionHtml,
    normalizeLed,
    openDashboardButtonHtml,
    registerLedUrl,
    resultStyle,
    runJsonRequest,
    registerPanel,
    fetchJson,
    setControlDisabled,
    withPanelLoading,
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
    const maxLed = Number.isInteger(context.max_led) ? context.max_led : -1;
    const controllers = Array.isArray(context.controllers) ? context.controllers : [];
    const hasChildren = Boolean(context.has_children);
    const childCount = Number.isInteger(context.child_count) ? context.child_count : 0;
    const currentLeds = Array.isArray(context.current_leds)
        ? context.current_leds.map(normalizeLed).filter((value) => value !== null)
        : [normalizeLed(context.current_led)].filter((value) => value !== null);
    const currentController = context.current_controller || context.default_controller || context.primary_controller || "";
    const currentLedText = hasChildren
        ? `Parent location: ${childCount} child location(s)`
        : (currentLeds.length ? `Current mapping: ${currentController ? `${currentController} / ` : ""}LED ${displayLedList(currentLeds)}` : "No LED mapping saved");
    const currentLedValue = currentLeds.length ? currentLeds : "";
    const assignmentHtml = hasChildren
        ? `<p style="margin: 0;">Parent locations are containers. Locating this location will light mapped leaf child locations.</p>`
        : ledFormHtml(maxLed, currentLedValue, controllers, currentController);

    target.innerHTML = `
        <div style="display: grid; gap: 0.75rem; max-width: 38rem;">
            <p style="margin: 0;">
                ${escapeHtml(options.description)}
            </p>
            <p data-current-mapping style="font-weight: 600; margin: 0;">
                ${escapeHtml(currentLedText)}
            </p>

            <button type="button" data-wled-retry-preview hidden>Retry preview</button>
            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                <button type="button" data-wled-locate disabled style="${buttonStyle("#2364aa")}">
                    Locate This Location
                </button>
                ${openDashboardButtonHtml()}
            </div>

            ${assignmentHtml}

            <div data-wled-result style="${resultStyle()}"></div>
        </div>
    `;

    registerPanel(target, context);
    const locateButton = target.querySelector("[data-wled-locate]");
    const testButton = target.querySelector("[data-wled-test]");
    const clearButton = target.querySelector("[data-wled-clear]");
    const form = target.querySelector("[data-wled-map-form]");
    const result = target.querySelector("[data-wled-result]");
    const currentMapping = target.querySelector("[data-current-mapping]");

    bindDashboardButton(target, pluginPageUrl);

    const retry = target.querySelector("[data-wled-retry-preview]");
    async function refreshPreview() {
        return withPanelLoading(async () => {
            setControlDisabled(locateButton, true);
            if (form) for (const element of form.querySelectorAll("input, select, button")) setControlDisabled(element, true);
            retry.hidden = true;
            try {
                if (!context.preview_url) throw new Error("Location preview URL is not configured. Refresh the page.");
                const response = await fetchJson(context.preview_url);
                if (typeof response.can_locate !== "boolean" || !response.location) throw new Error("Invalid location preview. Refresh the page.");
                currentMapping.textContent = response.has_children
                    ? `Parent location: ${response.child_count} child location(s)`
                    : response.leds?.length ? `Current mapping: ${compactIndicatorText(response)}` : `No usable LED mapping${response.reason ? `: ${response.reason}` : ""}`;
                setControlDisabled(locateButton, !response.can_locate);
                locateButton.title = response.can_locate ? "" : response.reason || "This location cannot be located yet.";
                if (form) {
                    const editable = !response.has_children && controllers.some((item) => item.reachable !== false);
                    for (const element of form.querySelectorAll("input, select, button")) setControlDisabled(element, !editable);
                    form.querySelector("input[name='led']").value = displayLedList(response.leds || []);
                    const select = form.querySelector("select[name='controller']");
                    const label = response.controller || context.default_controller || "";
                    select.value = [...select.options].some((option) => option.value === label) ? label : "";
                }
            } catch (error) {
                currentMapping.textContent = `Preview request failed: ${error.message}`;
                retry.hidden = false;
                throw error;
            }
        });
    }
    retry.addEventListener("click", () => refreshPreview().catch(() => {}));
    locateButton.addEventListener("click", () => runJsonRequest(locateUrl, locateButton, result, "Locating...", summarizePayload, {onSuccess: refreshPreview}));
    if (form) {
        testButton.addEventListener("click", () => {
            const leds = getLedValues(form, maxLed);
            if (!leds.length) { result.textContent = ledInputMessage(form, maxLed); return; }
            return runJsonRequest(testLedUrl(testControllerUrlBase || testUrlBase, form, leds), testButton, result, "Testing LED...", summarizePayload);
        });
        clearButton.addEventListener("click", () => {
            if (!window.confirm("Clear this StockLocation external indicator mapping?")) return;
            return runJsonRequest(clearMappingUrl(context.stock_location_id), clearButton, result, "Clearing mapping...", summarizePayload, {onSuccess: refreshPreview});
        });
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            const leds = getLedValues(form, maxLed);
            if (!leds.length) { result.textContent = ledInputMessage(form, maxLed); return; }
            return runJsonRequest(registerLedUrl({registerUrlBase, registerControllerUrlBase: context.register_controller_url_base}, null, form, leds),
                form.querySelector("button[type='submit']"), result, "Saving mapping...", summarizePayload, {onSuccess: refreshPreview});
        });
    }
    refreshPreview().catch(() => {});
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
            led: compactIndicatorText(payload),
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
