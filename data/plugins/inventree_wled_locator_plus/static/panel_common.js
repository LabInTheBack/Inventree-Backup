// One shared UI lock covers all native panels/forms in this browser page.
const panelRoots = new Set();
const disabledStates = new Map();
let pending = 0;

function lockControls() {
    for (const root of panelRoots) {
        if (!root.isConnected) { panelRoots.delete(root); continue; }
        root.setAttribute("aria-busy", "true");
        for (const control of root.querySelectorAll("button, input, select")) {
            if (!disabledStates.has(control)) disabledStates.set(control, control.disabled);
            control.disabled = true;
        }
    }
}

function beginRequest() {
    pending += 1;
    lockControls();
}

function endRequest() {
    pending -= 1;
    if (pending) { lockControls(); return; }
    for (const [control, disabled] of disabledStates) control.disabled = disabled;
    disabledStates.clear();
    for (const root of panelRoots) root.setAttribute("aria-busy", "false");
}

export function registerPanel(target, context) {
    panelRoots.add(target);
    target.dataset.wledPanel = "";
    target.dataset.wledCsrfToken = context.csrf_token || "";
    for (const result of target.querySelectorAll("[data-wled-result], [data-wled-preview-status]")) {
        result.setAttribute("role", "status");
        result.setAttribute("aria-live", "polite");
    }
    if (pending) lockControls();
}

export function setControlDisabled(control, disabled) {
    if (!control) return;
    if (pending) disabledStates.set(control, disabled);
    control.disabled = pending > 0 || disabled;
}

export async function withPanelLoading(callback) {
    beginRequest();
    try { return await callback(); }
    finally { endRequest(); }
}

function cookieToken() {
    const entry = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="));
    return entry ? decodeURIComponent(entry.slice("csrftoken=".length)) : "";
}

export async function fetchJson(url, options = {}) {
    const method = options.method || "GET";
    const headers = {Accept: "application/json"};
    if (method === "POST") {
        const token = options.csrfToken || cookieToken();
        if (!token) throw new Error("Your session token is missing. Refresh the page and sign in again.");
        headers["X-CSRFToken"] = token;
        headers["Content-Type"] = "application/json";
    }
    let response;
    try {
        response = await fetch(url, {credentials: "same-origin", cache: "no-store", method, headers, ...(method === "POST" ? {body: "{}"} : {})});
    } catch {
        const error = new Error("Could not reach InvenTree. Check the connection before retrying.");
        error.uncertain = method === "POST";
        throw error;
    }
    if (response.status === 401 || response.status === 403 || response.redirected) {
        throw new Error("Access denied or your session expired. Refresh the page and sign in again.");
    }
    if (!response.headers.get("content-type")?.includes("application/json")) {
        const error = new Error("InvenTree returned an unexpected response. Refresh the page and sign in again if needed.");
        error.uncertain = method === "POST";
        throw error;
    }
    let payload;
    try { payload = await response.json(); }
    catch {
        const error = new Error("InvenTree returned invalid JSON. Refresh the page before retrying.");
        error.uncertain = method === "POST";
        throw error;
    }
    if (!response.ok || payload?.success !== true || typeof payload?.action !== "string") {
        let message = payload?.error || "InvenTree returned an invalid response. Refresh the page before retrying.";
        if (payload?.code === "locator_busy") message = "The locator is busy. Wait for the current action, then try again.";
        if (response.status === 405) message = "This panel is out of date. Refresh the page to load its current controls.";
        const error = new Error(message);
        error.uncertain = method === "POST" && (response.status >= 500 && payload?.code !== "locator_busy" || response.ok);
        throw error;
    }
    return payload;
}

export async function runJsonRequest(url, button, result, message, summarizePayload, options = {}) {
    if (pending) return null;
    if (!url) {
        setResultText(result, "External indicator is missing the request URL.");
        return null;
    }
    beginRequest();
    setResultText(result, message || "Working...");
    try {
        const payload = await fetchJson(url, {
            method: "POST", csrfToken: button.closest("[data-wled-panel]")?.dataset.wledCsrfToken,
        });
        renderResult(result, summarizePayload(payload), options);
        if (options.onSuccess) {
            try { await options.onSuccess(payload); }
            catch {
                const note = document.createElement("p");
                note.textContent = "The action completed, but the preview could not be refreshed. Retry the preview before another action.";
                result.append(note);
            }
        }
        return payload;
    } catch (error) {
        const hardware = !url.includes("/register/");
        setResultText(result, `${error.message}${hardware && error.uncertain ? " Some lights may have changed; check them before retrying." : ""}`);
        return null;
    } finally {
        endRequest();
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
    if (select) {
        if (!selected?.value || selected.disabled) return -1;
        const raw = selected.dataset.maxLed;
        const maxLed = raw === undefined ? NaN : Number(raw);
        return Number.isSafeInteger(maxLed) && maxLed >= 0 ? maxLed : -1;
    }
    return Number.isSafeInteger(fallbackMaxLed) && fallbackMaxLed >= 0 ? fallbackMaxLed : -1;
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
        const value = /^\d+$/.test(part) ? Number(part) : NaN;
        const internalLed = value - 1;

        if (!Number.isSafeInteger(value) || internalLed < 0 || internalLed > maxLed) {
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

    const raw = String(value);
    const led = /^\d+$/.test(raw) ? Number(raw) : NaN;
    return Number.isSafeInteger(led) && led >= 0 ? led : null;
}

export function disableForm(form, title) {
    form.querySelectorAll("input, select, button").forEach((element) => {
        setControlDisabled(element, true);
        element.style.opacity = "0.65";
        element.title = title;
    });
}

export function enableForm(form) {
    form.querySelectorAll("input, select, button").forEach((element) => {
        setControlDisabled(element, false);
        element.style.opacity = "1";
        element.title = "";
    });
}

export function ledInputMessage(form, fallbackMaxLed) {
    const maxLed = getSelectedMaxLed(form, fallbackMaxLed);
    const controller = getSelectedController(form);
    const suffix = controller ? ` on controller ${controller}` : "";
    if (maxLed < 0) return "Choose a configured controller with an available LED count first.";
    return `Enter whole LED numbers from 1 to ${maxLed + 1}${suffix}, for example 15 or 15,16,17.`;
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
    controllers = Array.isArray(controllers) ? controllers : [];
    const available = controllers.some((controller) => controller.reachable !== false && Number.isSafeInteger(controller.max_led) && controller.max_led >= 0 && controller.label === currentController);
    const placeholder = available ? "" : `<option value="" selected disabled>${escapeHtml(controllers.length ? "Choose controller" : "No controllers configured")}</option>`;
    const options = controllers.map((controller) => {
        const selected = available && controller.label === currentController ? " selected" : "";
        const knownCount = Number.isSafeInteger(controller.max_led) && controller.max_led >= 0;
        const disabled = controller.reachable === false || !knownCount ? " disabled" : "";
        const maxLed = knownCount ? controller.max_led : "";
        return `
            <option value="${escapeHtml(controller.label)}" data-max-led="${maxLed}"${selected}${disabled}>
                ${escapeHtml(controller.label)} (${knownCount ? `${maxLed + 1} LEDs` : "LED count unavailable"}${controller.reachable === false ? ", setup needed" : ""})
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
            >${placeholder}${options}</select>
        </label>
    `;
}

export function testLedUrl(baseUrl, form, led) {
    const controller = getSelectedController(form);
    const ledPath = Array.isArray(led) ? `leds/${led.join(",")}/` : `${led}/`;
    return controller ? `${baseUrl}${encodeURIComponent(controller)}/${ledPath}` : `${baseUrl}${ledPath}`;
}

export function registerLedUrl(options, locationId, form, led) {
    const controller = getSelectedController(form);
    const ledPath = Array.isArray(led)
        ? `leds/${led.join(",")}/`
        : `led/${led}/`;

    if (controller && options.registerLocationControllerUrlBase) {
        return `${options.registerLocationControllerUrlBase}${locationId}/controller/${encodeURIComponent(controller)}/${ledPath}`;
    }

    if (controller && options.registerControllerUrlBase) {
        return `${options.registerControllerUrlBase}${encodeURIComponent(controller)}/${ledPath}`;
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
    const displayValue = Array.isArray(currentLedValue)
        ? displayLedList(currentLedValue)
        : displayLed(currentLedValue);

    return `
        <form data-wled-map-form style="align-items: end; display: flex; flex-wrap: wrap; gap: 0.55rem 0.9rem;">
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
