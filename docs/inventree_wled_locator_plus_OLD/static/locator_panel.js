import {
    bindDashboardButton,
    buttonStyle,
    clearMappingUrl,
    actionSummaryHtml,
    compactIndicatorText,
    displayIndicators,
    displayLed,
    displayLedList,
    escapeHtml,
    fetchJson,
    getLedValue,
    ledInputMessage,
    ledFormHtml,
    mappingActionHtml,
    openDashboardButtonHtml,
    registerLedUrl,
    resultStyle,
    runJsonRequest,
    splitLocationPath,
    testLedUrl,
} from "./panel_common.js";

export function renderPartPanel(target, data) {
    renderObjectPanel(target, data, {
        objectName: "part",
        missingTargetMessage: "WLED Locator Plus: no Part external indicator panel target provided",
        missingLocateMessage: "External indicator is missing the part locate URL.",
        intro: "Locate this part by lighting all mapped external indicators for available stock items.",
        loading: "Loading mapped stock locations...",
        locateButton: "Locate This Part",
        empty: "No stock items with mapped locations were found for this part.",
        summaryAction: "locate-part",
        summaryLabel: "Located part",
    });
}

export function renderBuildPanel(target, data) {
    renderObjectPanel(target, data, {
        objectName: "build",
        missingTargetMessage: "WLED Locator Plus: no Build external indicator panel target provided",
        missingLocateMessage: "External indicator is missing the build locate URL.",
        intro: "Locate this build order by lighting all mapped external indicators for allocated stock items.",
        loading: "Loading mapped allocation locations...",
        locateButton: "Locate This Build",
        empty: "No allocated stock items with mapped locations were found for this build order.",
        summaryAction: "locate-build",
        summaryLabel: "Located build",
    });
}

function renderObjectPanel(target, data, text) {
    if (!target) {
        console.error(text.missingTargetMessage);
        return;
    }

    const context = data?.context || {};
    const locateUrl = context.locate_url;
    const previewUrl = context.preview_url;
    const pluginPageUrl = context.plugin_page_url || "/plugin/wled-locator-plus/";
    const registerLocationUrlBase = context.register_location_url_base || "/plugin/wled-locator-plus/register/location/";
    const registerLocationUrlSuffix = context.register_location_url_suffix || "/led/";
    const registerLocationControllerUrlBase = context.register_location_controller_url_base || "/plugin/wled-locator-plus/register/location/";
    const testUrlBase = context.test_url_base || "/plugin/wled-locator-plus/test/";
    const testControllerUrlBase = context.test_controller_url_base || "/plugin/wled-locator-plus/test/";
    const maxLed = Number.isInteger(context.max_led) ? context.max_led : 58;
    const controllers = Array.isArray(context.controllers) ? context.controllers : [];

    if (!locateUrl) {
        target.innerHTML = `<p>${escapeHtml(text.missingLocateMessage)}</p>`;
        return;
    }

    target.innerHTML = `
        <div style="display: grid; gap: 0.75rem; max-width: 42rem;">
            <p style="margin: 0;">
                ${escapeHtml(text.intro)}
            </p>
            <div data-wled-preview style="background: #f7f8f9; border: 1px solid #d8dde2; border-radius: 6px; padding: 0.75rem;">
                ${escapeHtml(text.loading)}
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                <button
                    type="button"
                    data-wled-locate
                    style="${buttonStyle("#2364aa")}"
                >
                    ${escapeHtml(text.locateButton)}
                </button>
                ${openDashboardButtonHtml()}
            </div>
            <div data-wled-result style="${resultStyle()}"></div>
        </div>
    `;

    const button = target.querySelector("[data-wled-locate]");
    const preview = target.querySelector("[data-wled-preview]");
    const result = target.querySelector("[data-wled-result]");
    const previewOptions = {
        maxLed,
        controllers,
        defaultController: context.default_controller || context.primary_controller || "",
        registerLocationUrlBase,
        registerLocationUrlSuffix,
        registerLocationControllerUrlBase,
        testUrlBase,
        testControllerUrlBase,
    };

    bindDashboardButton(target, pluginPageUrl);

    if (previewUrl) {
        loadPreview(previewUrl, preview, result, previewOptions, text);
    } else {
        preview.textContent = `${capitalize(text.objectName)} preview URL is not configured.`;
    }

    button.addEventListener("click", async () => {
        await runJsonRequest(locateUrl, button, result, "Locating...", (payload) => summarizePayload(payload, text));
    });
}

async function loadPreview(url, container, result, options, text) {
    try {
        const payload = await fetchJson(url);
        container.innerHTML = renderPreview(payload, options, text);
        bindAssignmentForms(container, result, options);
    } catch (error) {
        container.textContent = `Preview request failed: ${error}`;
    }
}

function renderPreview(payload, options, text) {
    if (!payload?.success) {
        const error = payload?.error || "Preview request failed.";
        return `<strong>Preview error:</strong> ${escapeHtml(error)}`;
    }

    const lit = Array.isArray(payload.locations) ? payload.locations : (Array.isArray(payload.lit) ? payload.lit : []);
    const skipped = Array.isArray(payload.skipped) ? payload.skipped : [];

    if (!lit.length && !skipped.length) {
        return escapeHtml(text.empty);
    }

    const rows = lit.map((entry) => `
        <tr>
            <td style="${cellStyle()}">${escapeHtml(entry.location?.path || entry.location?.name || "Location")}</td>
            <td style="${cellStyle()}">${escapeHtml(quantityText(entry))}</td>
            <td data-led-cell style="${cellStyle()}">${escapeHtml(formatLeds(entry))}</td>
            <td style="${cellStyle()}">${locationAssignment(entry, options)}</td>
        </tr>
    `).join("");

    const skippedText = skipped.length
        ? `<p style="margin: 0.5rem 0 0;">Skipped: ${escapeHtml(skipped.length)} stock item(s) without usable LED mapping.</p>`
        : "";

    return `
        <div style="display: grid; gap: 0.5rem;">
            <strong>Will light ${escapeHtml((payload.indicators || payload.leds || []).length || 0)} indicator(s): ${escapeHtml(formatPayloadIndicators(payload))}</strong>
            <table style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr>
                        <th style="${headerStyle()}">Location</th>
                        <th style="${headerStyle()}">Qty</th>
                        <th style="${headerStyle()}">LED</th>
                        <th style="${headerStyle()}">Action</th>
                    </tr>
                </thead>
                <tbody>${rows || `<tr><td style="${cellStyle()}" colspan="4">No mapped stock locations.</td></tr>`}</tbody>
            </table>
            ${skippedText}
        </div>
    `;
}

function locationAssignment(entry, options) {
    const locationId = entry?.location?.id;

    if (!locationId) {
        return "";
    }

    const currentLedValue = Array.isArray(entry?.leds) && entry.leds.length === 1
        ? entry.leds[0]
        : (entry?.led ?? "");

    return `
        <div
            data-location-assignment
            data-location-id="${escapeHtml(locationId)}"
            style="display: grid; gap: 0.4rem;"
        >
            ${ledFormHtml(options.maxLed, currentLedValue, options.controllers, entry?.controller || options.defaultController)}
            <a href="/web/stock/location/${locationId}/assign-external-indicator-stock-location" style="${linkStyle("#50565e")}">Open Location</a>
        </div>
    `;
}

function bindAssignmentForms(container, result, options) {
    container.querySelectorAll("[data-location-assignment]").forEach((assignment) => {
        const locationId = Number.parseInt(assignment.dataset.locationId, 10);
        const form = assignment.querySelector("[data-wled-map-form]");
        const testButton = assignment.querySelector("[data-wled-test]");
        const clearButton = assignment.querySelector("[data-wled-clear]");

        if (!Number.isInteger(locationId) || !form || !testButton || !clearButton) {
            return;
        }

        testButton.addEventListener("click", async () => {
            const led = getLedValue(form, options.maxLed);
            if (led === null) {
                result.textContent = ledInputMessage(form, options.maxLed);
                return;
            }

            await runJsonRequest(testLedUrl(options.testControllerUrlBase || options.testUrlBase, form, led), testButton, result, "Testing LED...", summarizePayload);
        });

        clearButton.addEventListener("click", async () => {
            if (!window.confirm("Clear this StockLocation external indicator mapping?")) {
                return;
            }

            const payload = await runJsonRequest(
                clearMappingUrl(locationId),
                clearButton,
                result,
                "Clearing mapping...",
                summarizePayload
            );

            if (payload?.success) {
                const input = form.querySelector("input[name='led']");
                const ledCell = assignment.closest("tr")?.querySelector("[data-led-cell]");
                input.value = "";
                if (ledCell) {
                    ledCell.textContent = "No LED";
                }
            }
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            const led = getLedValue(form, options.maxLed);
            if (led === null) {
                result.textContent = ledInputMessage(form, options.maxLed);
                return;
            }

            const payload = await runJsonRequest(
                registerLedUrl(options, locationId, form, led),
                form.querySelector("button[type='submit']"),
                result,
                "Saving mapping...",
                summarizePayload
            );

            if (payload?.success) {
                const ledCell = assignment.closest("tr")?.querySelector("[data-led-cell]");
                if (ledCell) {
                    ledCell.textContent = `${payload.controller ? `${payload.controller} / ` : ""}LED ${displayLed(led)}`;
                }
            }
        });
    });
}

function summarizePayload(payload, text = {}) {
    if (!payload?.success) {
        return payload?.error ? `Error: ${payload.error}` : "WLED request failed.";
    }

    if (payload.action === "locate-part" || payload.action === "locate-build") {
        const rows = groupedLocationRows(payload);
        const summary = payload.summary || {};
        const objectName = payload.part?.full_name || payload.part?.name || payload.build?.reference || "Object";
        const count = summary.lit_items ?? summary.lit_allocations ?? rows.length;
        const skipped = summary.skipped_items ?? summary.skipped_allocations ?? 0;
        const notes = skipped ? [`Skipped ${skipped} item(s) without usable LED mapping.`] : [];

        return actionSummaryHtml(
            `${objectName} located in ${rows.length} location(s), ${count} component record(s):`,
            rows,
            notes
        );
    }

    if (payload.action === "register-location-led") {
        return mappingActionHtml("Saved mapping:", payload, "StockLocation mapping");
    }

    if (payload.action === "clear-location-indicator") {
        return mappingActionHtml("Cleared mapping:", payload, "No LED assigned");
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

function groupedLocationRows(payload) {
    const entries = Array.isArray(payload?.locations) && payload.locations.length
        ? payload.locations
        : (Array.isArray(payload?.lit) ? payload.lit : []);

    return entries.map((entry) => {
        const parts = splitLocationPath(entry.location);
        return {
            location: parts.location,
            bin: parts.bin,
            led: compactIndicatorText(entry),
            component: componentText(entry),
        };
    });
}

function formatLeds(entry) {
    if (Array.isArray(entry?.indicators) && entry.indicators.length) {
        return displayIndicators(entry.indicators);
    }

    if (Array.isArray(entry?.leds) && entry.leds.length) {
        return `LED ${displayLedList(entry.leds)}`;
    }

    const led = displayLed(entry?.led);
    return led ? `LED ${led}` : "";
}

function formatPayloadIndicators(payload) {
    if (Array.isArray(payload?.indicators) && payload.indicators.length) {
        return displayIndicators(payload.indicators);
    }

    return displayLedList(payload.leds) || "none";
}

function quantityText(entry) {
    if (Number.isInteger(entry?.item_count)) {
        return `${entry.item_count} stock item(s)`;
    }

    return entry?.item?.quantity || "";
}

function componentText(entry) {
    if (Number.isInteger(entry?.item_count)) {
        return `${entry.item_count} component(s)`;
    }

    if (Number.isInteger(entry?.allocation_count)) {
        return `${entry.allocation_count} allocation(s)`;
    }

    if (entry?.item?.part) {
        return entry.item.part;
    }

    return quantityText(entry);
}

function linkStyle(background) {
    return `align-items: center; background: ${background}; border-radius: 6px; color: #fff; display: inline-flex; min-height: 2.25rem; padding: 0 0.7rem; text-decoration: none;`;
}

function capitalize(text) {
    return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

function headerStyle() {
    return "border-bottom: 1px solid #d8dde2; padding: 0.35rem; text-align: left;";
}

function cellStyle() {
    return "border-bottom: 1px solid #e8eaed; padding: 0.35rem;";
}
