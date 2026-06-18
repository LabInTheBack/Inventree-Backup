function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];

    for (const cookie of cookies) {
        const [key, ...parts] = cookie.trim().split("=");
        if (key === name) {
            return decodeURIComponent(parts.join("="));
        }
    }

    return "";
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
            ...(options.headers || {}),
        },
        ...options,
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload?.success === false) {
        const error = new Error(payload?.error || `HTTP ${response.status}`);
        error.payload = payload;
        throw error;
    }

    return payload;
}

function normalizeColor(value, fallback = "FF0000") {
    const color = String(value || fallback).replace("#", "").trim();
    return /^[0-9a-fA-F]{6}$/.test(color) ? color.toUpperCase() : fallback;
}

function controllerPayload(form) {
    const formData = new FormData(form);
    return {
        label: String(formData.get("label") || "").trim(),
        address: String(formData.get("address") || "").trim(),
        max_leds: String(formData.get("max_leds") || "").trim(),
        marker_color: normalizeColor(formData.get("marker_color")),
    };
}

function optionsPayload(form) {
    const formData = new FormData(form);
    return {
        clear_color: normalizeColor(formData.get("clear_color"), "000000"),
        request_timeout: Number(formData.get("request_timeout") || 3),
    };
}

function setStatus(target, message, state = "idle") {
    const status = target.querySelector("[data-wled-status]");
    if (!status) {
        return;
    }

    status.textContent = message;
    status.dataset.state = state;
}

function style() {
    return `
        <style>
            .wlp-admin { color: #202124; display: grid; gap: 1rem; }
            .wlp-admin * { box-sizing: border-box; }
            .wlp-section { display: grid; gap: 0.75rem; }
            .wlp-section-title { font-size: 1.05rem; font-weight: 650; margin: 0; }
            .wlp-summary { color: #5f6368; font-size: 0.9rem; margin: 0; }
            .wlp-status { border: 1px solid #d8dde2; border-radius: 6px; font-size: 0.9rem; min-height: 2.25rem; padding: 0.55rem 0.65rem; }
            .wlp-status[data-state="ok"] { background: #eef8f1; border-color: #b8dfc2; color: #17652d; }
            .wlp-status[data-state="error"] { background: #fff1f1; border-color: #efc2c2; color: #8a1f1f; }
            .wlp-status[data-state="working"] { background: #f6f7f8; color: #4b5563; }
            .wlp-grid { display: grid; gap: 0.75rem; }
            .wlp-card { border: 1px solid #d8dde2; border-radius: 8px; display: grid; gap: 0.75rem; padding: 0.85rem; }
            .wlp-card-head { align-items: center; display: flex; gap: 0.75rem; justify-content: space-between; }
            .wlp-card-title { font-size: 1rem; font-weight: 650; margin: 0; }
            .wlp-muted { color: #5f6368; font-size: 0.86rem; }
            .wlp-form { display: grid; gap: 0.65rem; grid-template-columns: minmax(7rem, 0.7fr) minmax(10rem, 1.2fr) minmax(6rem, 0.45fr) minmax(5rem, 0.4fr) auto; }
            .wlp-options-form { display: grid; gap: 0.65rem; grid-template-columns: minmax(7rem, 0.5fr) minmax(7rem, 0.5fr) auto; }
            .wlp-mapping-form { display: grid; gap: 0.65rem; grid-template-columns: minmax(10rem, 1fr) minmax(10rem, 1fr) auto; }
            .wlp-form-add { border-top: 1px solid #eceff1; padding-top: 0.85rem; }
            .wlp-field { color: #3c4043; display: grid; font-size: 0.9rem; gap: 0.25rem; }
            .wlp-field input, .wlp-field select { border: 1px solid #c6c9ce; border-radius: 6px; font: inherit; min-height: 2.25rem; padding: 0.35rem 0.45rem; width: 100%; }
            .wlp-check { align-items: center; display: flex; gap: 0.35rem; min-height: 2.25rem; }
            .wlp-check input { min-height: auto; width: auto; }
            .wlp-actions { align-items: end; display: flex; flex-wrap: wrap; gap: 0.45rem; }
            .wlp-button { background: #2364aa; border: 0; border-radius: 6px; color: #fff; cursor: pointer; font: inherit; min-height: 2.25rem; padding: 0.45rem 0.7rem; white-space: nowrap; }
            .wlp-button.secondary { background: #50565e; }
            .wlp-button.danger { background: #9d2a2a; }
            .wlp-button:disabled { cursor: not-allowed; opacity: 0.55; }
            .wlp-chip { border: 1px solid #d8dde2; border-radius: 999px; color: #3c4043; font-size: 0.8rem; padding: 0.2rem 0.5rem; }
            .wlp-color { align-items: center; display: flex; gap: 0.35rem; }
            .wlp-swatch { border: 1px solid #c6c9ce; border-radius: 4px; display: inline-block; height: 1rem; width: 1rem; }
            @media (max-width: 900px) {
                .wlp-form, .wlp-options-form, .wlp-mapping-form { grid-template-columns: 1fr 1fr; }
                .wlp-actions { grid-column: 1 / -1; }
            }
            @media (max-width: 620px) {
                .wlp-form, .wlp-options-form, .wlp-mapping-form { grid-template-columns: 1fr; }
                .wlp-card-head { align-items: flex-start; flex-direction: column; }
                .wlp-button { width: 100%; }
            }
        </style>
    `;
}

function controllerForm(controller) {
    const color = normalizeColor(controller.marker_color);
    const details = [controller.name, controller.version].filter(Boolean).join(" / ");

    return `
        <form class="wlp-card" data-controller-form>
            <div class="wlp-card-head">
                <div>
                    <h3 class="wlp-card-title">${escapeHtml(controller.label)}</h3>
                    <div class="wlp-muted">${details ? escapeHtml(details) : "Saved controller record"}</div>
                </div>
                <div class="wlp-color">
                    <span class="wlp-swatch" style="background: #${escapeHtml(color)}"></span>
                    <span class="wlp-chip">${escapeHtml(controller.max_leds || "manual required")} LEDs</span>
                </div>
            </div>
            <div class="wlp-form">
                <label class="wlp-field">Label
                    <input name="label" value="${escapeHtml(controller.label)}" required pattern="[A-Za-z0-9_-]+">
                </label>
                <label class="wlp-field">IP or URL
                    <input name="address" value="${escapeHtml(controller.address)}" required>
                </label>
                <label class="wlp-field">LEDs
                    <input name="max_leds" type="number" min="1" value="${escapeHtml(controller.max_leds)}" placeholder="Sync or type">
                </label>
                <label class="wlp-field">Color
                    <input name="marker_color" type="color" value="#${escapeHtml(color)}" required>
                </label>
                <div class="wlp-actions">
                    <button class="wlp-button" type="button" data-action="sync">Sync</button>
                    <button class="wlp-button secondary" type="button" data-action="save">Save Manual</button>
                    <button class="wlp-button danger" type="button" data-action="delete">Delete</button>
                </div>
            </div>
        </form>
    `;
}

function optionsForm(options = {}) {
    const clearColor = normalizeColor(options.clear_color, "000000");

    return `
        <form class="wlp-card" data-options-form>
            <div>
                <h3 class="wlp-card-title">Plugin Options</h3>
                <div class="wlp-muted">These options apply to all configured WLED controllers.</div>
            </div>
            <div class="wlp-options-form">
                <label class="wlp-field">Clear color
                    <input name="clear_color" type="color" value="#${escapeHtml(clearColor)}" required>
                </label>
                <label class="wlp-field">Timeout
                    <input name="request_timeout" type="number" min="1" value="${escapeHtml(options.request_timeout || 3)}" required>
                </label>
                <div class="wlp-actions">
                    <button class="wlp-button secondary" type="button" data-action="save-options">Save Options</button>
                </div>
            </div>
        </form>
    `;
}

function mappingTools(payload = {}) {
    const controllers = payload.controllers || [];
    const mappings = payload.mappings || {};
    const summary = mappings.summary || {};
    const controllerCounts = mappings.controller_counts || {};
    const sourceOptions = [
        ...Object.entries(controllerCounts).map(([label, count]) => (
            `<option value="${escapeHtml(label)}">${escapeHtml(label)} mappings (${escapeHtml(count)})</option>`
        )),
    ].filter(Boolean).join("");
    const targetOptions = controllers.map((controller) => (
        `<option value="${escapeHtml(controller.label)}">${escapeHtml(controller.label)}</option>`
    )).join("");
    const clearOptions = [
        `<option value="all">All controller mappings</option>`,
        ...Object.keys(controllerCounts).map((label) => (
            `<option value="${escapeHtml(label)}">${escapeHtml(label)} mappings</option>`
        )),
    ].filter(Boolean).join("");

    return `
        <div class="wlp-card" data-mapping-tools>
            <div>
                <h3 class="wlp-card-title">StockLocation Mapping Cleanup</h3>
                <div class="wlp-muted">
                    ${escapeHtml(summary.controller_mappings || 0)} controller mappings,
                    ${escapeHtml(summary.invalid || 0)} invalid records.
                </div>
            </div>
            <div class="wlp-mapping-form">
                <label class="wlp-field">Move from
                    <select name="source_controller"${sourceOptions ? "" : " disabled"}>${sourceOptions || "<option>No mappings</option>"}</select>
                </label>
                <label class="wlp-field">Move to
                    <select name="target_controller"${targetOptions ? "" : " disabled"}>${targetOptions || "<option>No controllers</option>"}</select>
                </label>
                <div class="wlp-actions">
                    <button class="wlp-button secondary" type="button" data-action="reassign-mappings"${sourceOptions && targetOptions ? "" : " disabled"}>Reassign</button>
                </div>
            </div>
            <div class="wlp-mapping-form">
                <label class="wlp-field">Clear
                    <select name="clear_source">${clearOptions}</select>
                </label>
                <div class="wlp-actions">
                    <button class="wlp-button danger" type="button" data-action="clear-mappings">Clear Mappings</button>
                </div>
            </div>
        </div>
    `;
}

function addForm() {
    return `
        <form class="wlp-card wlp-form-add" data-add-form>
            <div>
                <h3 class="wlp-card-title">Add WLED Controller</h3>
                <div class="wlp-muted">Type a label and IP, then Sync. If Sync cannot reach WLED, enter LEDs manually and Save Manual.</div>
            </div>
            <div class="wlp-form">
                <label class="wlp-field">Label
                    <input name="label" placeholder="wled-1" required pattern="[A-Za-z0-9_-]+">
                </label>
                <label class="wlp-field">IP or URL
                    <input name="address" placeholder="192.168.1.50" required>
                </label>
                <label class="wlp-field">LEDs
                    <input name="max_leds" type="number" min="1" placeholder="Sync or type">
                </label>
                <label class="wlp-field">Color
                    <input name="marker_color" type="color" value="#FF0000" required>
                </label>
                <div class="wlp-actions">
                    <button class="wlp-button" type="button" data-action="sync">Sync</button>
                    <button class="wlp-button secondary" type="button" data-action="save">Save Manual</button>
                </div>
            </div>
        </form>
    `;
}

function render(target, data) {
    const context = data?.context || data || {};
    const state = target.__wlpState || { payload: null };
    target.__wlpState = state;

    const payload = state.payload || {
        controllers: [],
        count: 0,
    };
    const controllers = payload.controllers || [];

    target.innerHTML = `
        ${style()}
        <div class="wlp-admin">
            <p class="wlp-summary">
                Configure WLED controllers here. Sync reads WLED /json/info only; manual save is available when Sync cannot reach the controller.
            </p>
            <div class="wlp-status" data-wled-status data-state="idle">
                ${controllers.length ? `${controllers.length} controller records configured.` : "Loading controller records..."}
            </div>
            <div class="wlp-grid" data-controller-list>
                ${controllers.map((controller) => controllerForm(controller)).join("")}
                ${addForm()}
            </div>
            <div class="wlp-section">
                ${optionsForm(payload.options || {})}
            </div>
            <div class="wlp-section">
                ${mappingTools(payload)}
            </div>
        </div>
    `;

    bind(target, context);
}

async function loadControllers(target, data) {
    const context = data?.context || data || {};
    const state = target.__wlpState || {};
    target.__wlpState = state;

    try {
        setStatus(target, "Loading controller records...", "working");
        const controllers = await fetchJson(context.controllers_url || "/plugin/wled-locator-plus/controllers/");
        const mappings = await fetchJson(context.mappings_url || "/plugin/wled-locator-plus/controllers/mappings/");
        state.payload = { ...controllers, mappings: mappings.mappings };
        render(target, data);
        setStatus(
            target,
            `${state.payload.count} controller records configured.`,
            "ok",
        );
    } catch (error) {
        setStatus(target, `Could not load controllers: ${error.message}`, "error");
    }
}

async function runAction(target, context, form, action) {
    const payload = controllerPayload(form);
    const buttons = form.querySelectorAll("button");

    if (action === "save" && !payload.max_leds) {
        setStatus(target, "Manual save needs an LED count. Use Sync or type the LED count.", "error");
        return;
    }

    const url = {
        sync: context.sync_url || "/plugin/wled-locator-plus/controllers/sync/",
        save: context.save_url || "/plugin/wled-locator-plus/controllers/save/",
        delete: context.delete_url || "/plugin/wled-locator-plus/controllers/delete/",
    }[action];

    if (action === "delete" && !window.confirm(`Delete WLED controller ${payload.label}? StockLocation mappings are not changed.`)) {
        return;
    }

    buttons.forEach((button) => { button.disabled = true; });
    setStatus(target, `${action === "sync" ? "Syncing" : action === "delete" ? "Deleting" : "Saving"} ${payload.label}...`, "working");

    try {
        const result = await fetchJson(url, {
            method: "POST",
            body: JSON.stringify(action === "delete" ? { label: payload.label } : payload),
        });
        target.__wlpState.payload = { ...target.__wlpState.payload, ...result };
        render(target, { context });
        setStatus(target, `${payload.label} ${action === "sync" ? "synced" : action === "delete" ? "deleted" : "saved"}.`, "ok");
    } catch (error) {
        const fallback = error.payload?.manual_fallback ? " Enter LEDs manually and Save Manual." : "";
        setStatus(target, `${error.message}.${fallback}`, "error");
    } finally {
        buttons.forEach((button) => { button.disabled = false; });
    }
}

async function saveOptions(target, context, form) {
    const buttons = form.querySelectorAll("button");
    buttons.forEach((button) => { button.disabled = true; });
    setStatus(target, "Saving plugin options...", "working");

    try {
        const result = await fetchJson(context.settings_url || "/plugin/wled-locator-plus/controllers/settings/", {
            method: "POST",
            body: JSON.stringify(optionsPayload(form)),
        });
        target.__wlpState.payload = { ...target.__wlpState.payload, ...result };
        render(target, { context });
        setStatus(target, "Plugin options saved.", "ok");
    } catch (error) {
        setStatus(target, `Could not save options: ${error.message}`, "error");
    } finally {
        buttons.forEach((button) => { button.disabled = false; });
    }
}

async function runMappingAction(target, context, container, action) {
    const formData = new FormData();
    container.querySelectorAll("select, input").forEach((input) => {
        if (input.type === "checkbox") {
            formData.set(input.name, input.checked ? "true" : "false");
        } else {
            formData.set(input.name, input.value);
        }
    });

    const payload = action === "reassign-mappings"
        ? {
            source_controller: formData.get("source_controller"),
            target_controller: formData.get("target_controller"),
        }
        : {
            source_controller: formData.get("clear_source"),
            confirm: true,
        };

    if (action === "clear-mappings" && !window.confirm("Clear selected StockLocation WLED mappings?")) {
        return;
    }

    const buttons = container.querySelectorAll("button");
    buttons.forEach((button) => { button.disabled = true; });
    setStatus(target, action === "reassign-mappings" ? "Reassigning mappings..." : "Clearing mappings...", "working");

    try {
        const result = await fetchJson(
            action === "reassign-mappings"
                ? (context.reassign_url || "/plugin/wled-locator-plus/controllers/mappings/reassign/")
                : (context.clear_mappings_url || "/plugin/wled-locator-plus/controllers/mappings/clear/"),
            {
                method: "POST",
                body: JSON.stringify(payload),
            },
        );
        target.__wlpState.payload = { ...target.__wlpState.payload, ...result };
        render(target, { context });
        setStatus(target, action === "reassign-mappings" ? "Mappings reassigned." : "Mappings cleared.", "ok");
    } catch (error) {
        setStatus(target, `${error.message}`, "error");
    } finally {
        buttons.forEach((button) => { button.disabled = false; });
    }
}

function bind(target, context) {
    target.querySelectorAll("[data-controller-form], [data-add-form]").forEach((form) => {
        form.querySelectorAll("[data-action]").forEach((button) => {
            button.addEventListener("click", () => runAction(target, context, form, button.dataset.action));
        });
    });

    target.querySelectorAll("[data-options-form]").forEach((form) => {
        form.querySelector("[data-action='save-options']")?.addEventListener("click", () => saveOptions(target, context, form));
    });

    target.querySelectorAll("[data-mapping-tools]").forEach((container) => {
        container.querySelector("[data-action='reassign-mappings']")?.addEventListener("click", () => runMappingAction(target, context, container, "reassign-mappings"));
        container.querySelector("[data-action='clear-mappings']")?.addEventListener("click", () => runMappingAction(target, context, container, "clear-mappings"));
    });
}

export function renderPluginSettings(target, data) {
    render(target, data);
    loadControllers(target, data);
}
