export async function fetchJson(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload?.success === false) {
        throw new Error(payload?.error || `HTTP ${response.status}`);
    }

    return payload;
}

export async function runJsonRequest(url, button, result, message, summarizePayload, options = {}) {
    if (!url) {
        setResultText(result, "External indicator is missing the request URL.");
        return null;
    }

    button.disabled = true;
    setResultText(result, message || "Working...");

    try {
        const payload = await fetchJson(url);
        const summary = summarizePayload(payload);
        renderResult(result, summary, options);
        return payload;
    } catch (error) {
        setResultText(result, `WLED request failed: ${error.message || error}`);
        return null;
    } finally {
        button.disabled = false;
    }
}

export function renderResult(result, summary, options = {}) {
    if (!result) {
        return;
    }

    if (summary && typeof summary === "object" && summary.html) {
        setResultHtml(result, summary.html);
        return;
    }

    if (options.html) {
        setResultHtml(result, summary || "");
        return;
    }

    setResultText(result, summary || "WLED request completed.");
}

export function setResultText(result, text) {
    if (!result) {
        return;
    }

    result.textContent = text || "";
}

export function setResultHtml(result, html) {
    if (!result) {
        return;
    }

    result.innerHTML = html || "";
}

export function getSelectedController(form) {
    const select = form?.querySelector("select[name='controller']");
    return select?.value || "";
}

export function getSelectedMaxLed(form, fallbackMaxLed) {
    const select = form?.querySelector("select[name='controller']");
    const selected = select?.selectedOptions?.[0];
    const maxLed = Number.parseInt(selected?.dataset?.maxLed, 10);
    return Number.isInteger(maxLed) ? maxLed : fallbackMaxLed;
}

export function getLedValue(form, maxLed) {
    const values = getLedValues(form, maxLed);
    return values.length === 1 ? values[0] : null;
}

export function getLedValues(form, maxLed) {
    maxLed = getSelectedMaxLed(form, maxLed);
    const rawValue = String(new FormData(form).get("led") || "");
    const parts = rawValue.split(/[,\s]+/).map((item) => item.trim()).filter(Boolean);
    const values = [];

    for (const part of parts) {
        const value = Number.parseInt(part, 10);
        const internalLed = value - 1;

        if (!Number.isInteger(value) || internalLed < 0 || internalLed > maxLed) {
            return [];
        }

        if (!values.includes(internalLed)) {
            values.push(internalLed);
        }
    }

    return values;
}

export function normalizeLed(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const led = Number.parseInt(value, 10);
    return Number.isInteger(led) ? led : null;
}

export function disableForm(form, title) {
    form.querySelectorAll("input, select, button").forEach((element) => {
        element.disabled = true;
        element.style.opacity = "0.65";
        element.title = title;
    });
}

export function enableForm(form) {
    form.querySelectorAll("input, select, button").forEach((element) => {
        element.disabled = false;
        element.style.opacity = "1";
        element.title = "";
    });
}

export function ledInputMessage(form, fallbackMaxLed) {
    const maxLed = getSelectedMaxLed(form, fallbackMaxLed);
    const controller = getSelectedController(form);
    const suffix = controller ? ` on controller ${controller}` : "";
    return `Enter LED number(s) from 1 to ${maxLed + 1}${suffix}, for example 15 or 15,16,17.`;
}

export function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
}

export function locationName(location) {
    return location?.path || location?.name || "location";
}

export function displayLed(value) {
    const led = normalizeLed(value);
    return led === null ? "" : String(led + 1);
}

export function displayLedList(values = []) {
    if (!Array.isArray(values)) {
        return "";
    }

    return values.map(displayLed).filter(Boolean).join(", ");
}

export function displayIndicator(indicator) {
    if (!indicator) {
        return "";
    }

    const led = displayLed(indicator.led);
    return `${indicator.controller ? `${indicator.controller} / ` : ""}LED ${led}`;
}

export function displayIndicators(indicators = []) {
    if (!Array.isArray(indicators)) {
        return "";
    }

    return indicators.map(displayIndicator).filter(Boolean).join(", ");
}

export function splitLocationPath(location) {
    const path = location?.path || location?.name || "";
    const parts = String(path).split("/").map((item) => item.trim()).filter(Boolean);

    if (!parts.length) {
        return { location: "Location", bin: "" };
    }

    if (parts.length === 1) {
        return { location: parts[0], bin: "" };
    }

    return {
        location: parts.slice(0, -1).join(" / "),
        bin: parts[parts.length - 1],
    };
}

export function compactIndicatorText(entry) {
    if (Array.isArray(entry?.indicators) && entry.indicators.length) {
        return displayIndicators(entry.indicators);
    }

    if (Array.isArray(entry?.leds) && entry.leds.length) {
        return `LED ${displayLedList(entry.leds)}`;
    }

    const led = displayLed(entry?.led);
    return led ? `${entry?.controller ? `${entry.controller} / ` : ""}LED ${led}` : "";
}

export function actionSummaryHtml(title, rows = [], notes = []) {
    const rowHtml = rows.map((row) => `
        <tr>
            <td style="${summaryCellStyle()}">${escapeHtml(row.location || "")}</td>
            <td style="${summaryCellStyle()}">${escapeHtml(row.bin || "")}</td>
            <td style="${summaryCellStyle()}">${escapeHtml(row.led || "")}</td>
            <td style="${summaryCellStyle()}">${escapeHtml(row.component || "")}</td>
        </tr>
    `).join("");
    const notesHtml = notes.filter(Boolean).map((note) => `<p style="margin: 0;">${escapeHtml(note)}</p>`).join("");

    return {
        html: `
            <div style="display: grid; gap: 0.55rem;">
                <strong>${escapeHtml(title)}</strong>
                ${rows.length ? `
                    <table style="border-collapse: collapse; width: 100%;">
                        <thead>
                            <tr>
                                <th style="${summaryHeaderStyle()}">Location</th>
                                <th style="${summaryHeaderStyle()}">Bin</th>
                                <th style="${summaryHeaderStyle()}">LED number</th>
                                <th style="${summaryHeaderStyle()}">Component/count</th>
                            </tr>
                        </thead>
                        <tbody>${rowHtml}</tbody>
                    </table>
                ` : ""}
                ${notesHtml}
            </div>
        `,
    };
}

export function mappingActionHtml(title, payload, component = "") {
    const locationParts = splitLocationPath(payload?.location);
    const led = compactIndicatorText(payload);

    return actionSummaryHtml(title, [{
        location: locationParts.location,
        bin: locationParts.bin,
        led,
        component,
    }]);
}

export function resultStyle() {
    return "background: #f7f8f9; border: 1px solid #d8dde2; border-radius: 6px; margin: 0; overflow: auto; padding: 0.75rem;";
}

function summaryHeaderStyle() {
    return "border-bottom: 1px solid #d8dde2; color: #4b5563; font-weight: 600; padding: 0.35rem; text-align: left;";
}

function summaryCellStyle() {
    return "border-bottom: 1px solid #e8eaed; padding: 0.35rem;";
}

export function buttonStyle(background) {
    return `align-items: center; background: ${background}; border: 0; border-radius: 6px; color: #fff; cursor: pointer; display: inline-flex; justify-content: center; min-height: 2.4rem; padding: 0.45rem 0.75rem; white-space: nowrap;`;
}

export function openDashboardButtonHtml(label = "Open Indicator Dashboard") {
    return `
        <button type="button" data-wled-open-dashboard style="${buttonStyle("#50565e")}">
            ${escapeHtml(label)}
        </button>
    `;
}

export function bindDashboardButton(container, url = "/plugin/wled-locator-plus/") {
    container.querySelectorAll("[data-wled-open-dashboard]").forEach((button) => {
        button.addEventListener("click", () => {
            window.location.href = url;
        });
    });
}

export function previewStyle() {
    return "background: #f7f8f9; border: 1px solid #d8dde2; border-radius: 6px; padding: 0.75rem;";
}

export function controllerSelectHtml(controllers = [], currentController = "") {
    if (!Array.isArray(controllers) || controllers.length < 2) {
        return "";
    }

    const options = controllers.map((controller) => {
        const selected = controller.label === currentController ? " selected" : "";
        const disabled = controller.reachable === false ? " disabled" : "";
        const maxLed = Number.isInteger(controller.max_led) ? controller.max_led : 0;
        return `
            <option value="${escapeHtml(controller.label)}" data-max-led="${maxLed}"${selected}${disabled}>
                ${escapeHtml(controller.label)} (${maxLed + 1} LEDs${controller.reachable === false ? ", unreachable" : ""})
            </option>
        `;
    }).join("");

    return `
        <label style="display: grid; gap: 0.3rem; min-width: 13rem;">
            Controller
            <select
                name="controller"
                required
                style="border: 1px solid #c6c9ce; border-radius: 6px; box-sizing: border-box; height: 2.4rem; padding: 0.35rem 0.5rem;"
            >${options}</select>
        </label>
    `;
}

export function testLedUrl(baseUrl, form, led) {
    const controller = getSelectedController(form);
    const ledPath = Array.isArray(led) ? `leds/${led.join(",")}/` : `${led}/`;
    return controller ? `${baseUrl}${controller}/${ledPath}` : `${baseUrl}${ledPath}`;
}

export function registerLedUrl(options, locationId, form, led) {
    const controller = getSelectedController(form);
    const ledPath = Array.isArray(led)
        ? `leds/${led.join(",")}/`
        : `led/${led}/`;

    if (controller && options.registerLocationControllerUrlBase) {
        return `${options.registerLocationControllerUrlBase}${locationId}/controller/${controller}/${ledPath}`;
    }

    if (controller && options.registerControllerUrlBase) {
        return `${options.registerControllerUrlBase}${controller}/${ledPath}`;
    }

    if (options.registerUrlBase && !locationId) {
        if (Array.isArray(led)) {
            const base = options.registerUrlBase.replace(/\/led\/?$/, "/leds/");
            return `${base}${led.join(",")}/`;
        }
        return `${options.registerUrlBase}${led}/`;
    }

    if (Array.isArray(led)) {
        return `${options.registerLocationUrlBase || options.registerUrlBase}${locationId || ""}/leds/${led.join(",")}/`;
    }

    return `${options.registerLocationUrlBase || options.registerUrlBase}${locationId || ""}${options.registerLocationUrlSuffix || options.registerUrlSuffix || "/led/"}${led}/`;
}

export function clearMappingUrl(locationId) {
    return `/plugin/wled-locator-plus/register/location/${locationId}/clear/`;
}

export function ledFormHtml(maxLed, currentLedValue = "", controllers = [], currentController = "") {
    const gridColumns = Array.isArray(controllers) && controllers.length > 1
        ? "minmax(13rem, max-content) minmax(7rem, 8rem) auto auto auto"
        : "minmax(7rem, 8rem) auto auto auto";
    const displayValue = Array.isArray(currentLedValue)
        ? displayLedList(currentLedValue)
        : displayLed(currentLedValue);

    return `
        <form data-wled-map-form style="align-items: end; column-gap: 0.9rem; display: grid; grid-template-columns: ${gridColumns}; row-gap: 0.55rem;">
            ${controllerSelectHtml(controllers, currentController)}
            <label style="display: grid; gap: 0.3rem; min-width: 7rem;">
                LED Number(s)
                <input
                    name="led"
                    type="text"
                    inputmode="numeric"
                    value="${displayValue}"
                    required
                    placeholder="15 or 15,16,17"
                    style="border: 1px solid #c6c9ce; border-radius: 6px; box-sizing: border-box; height: 2.4rem; padding: 0.35rem 0.5rem;"
                >
            </label>
            <button type="button" data-wled-test style="${buttonStyle("#50565e")}">
                Test LED
            </button>
            <button type="submit" style="${buttonStyle("#2364aa")}">
                Save Mapping
            </button>
            <button type="button" data-wled-clear style="${buttonStyle("#a43d2f")}">
                Clear Mapping
            </button>
        </form>
    `;
}
