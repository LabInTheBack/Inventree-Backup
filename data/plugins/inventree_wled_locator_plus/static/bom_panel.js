import {fetchJson, registerPanel, setControlDisabled, withPanelLoading, panelRequestPending, displayIndicators} from "./panel_common.js";
import {createPickingChecklist} from "./picking_checklist.js";

function node(tag, text) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    return item;
}

function amount(value) {
    return String(value).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
}

function imageUrl(value) {
    if (typeof value !== "string" || !value) return null;
    try {
        const url = new URL(value, window.location.origin);
        return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch { return null; }
}

function thumbnail(part, size = 48) {
    const holder = node("span", "No image");
    holder.style.cssText = `display:inline-flex;width:${size}px;min-width:${size}px;height:${size}px;align-items:center;justify-content:center;font-size:10px;color:#666`;
    const original = imageUrl(part.image_url);
    const url = imageUrl(part.thumbnail_url) || original;
    if (url) {
        const img = node("img");
        img.alt = "";
        img.loading = "lazy";
        img.decoding = "async";
        img.style.cssText = `width:${size}px;height:${size}px;object-fit:contain`;
        img.onerror = () => {
            if (original && img.src !== original) img.src = original;
            else holder.replaceChildren(node("span", "No image"));
        };
        img.src = url;
        holder.replaceChildren(img);
    }
    return holder;
}

export function renderBomPanel(target, data) {
    const context = data?.context || {};
    const buildMode = Number.isSafeInteger(context.build_id);
    target.replaceChildren();
    target.style.cssText = "display:grid;grid-template-columns:minmax(0,1fr);gap:12px;max-width:1100px;min-width:0";
    target.append(node("p", buildMode
        ? "Find outstanding build components using saved requirements, consumed quantities and allocations. Highlighting does not allocate or consume stock."
        : "Find the stocked components required to make this assembly. Highlighting does not allocate or consume stock."));
    const controls = node("div");
    controls.style.cssText = "display:flex;flex-wrap:wrap;gap:16px;align-items:center";
    const quantityLabel = node("label", "Assembly quantity ");
    const quantity = node("input");
    quantity.type = "number"; quantity.min = "1"; quantity.max = "10000"; quantity.step = "1"; quantity.value = "1";
    quantity.dataset.bomQuantity = "";
    quantity.style.width = "90px";
    quantityLabel.append(quantity);
    const expandLabel = node("label");
    const expand = node("input"); expand.type = "checkbox"; expand.dataset.bomExpand = "";
    expandLabel.append(expand, document.createTextNode(" Expand subassemblies into components"));
    const optionalLabel = node("label");
    const optional = node("input"); optional.type = "checkbox";
    optionalLabel.append(optional, document.createTextNode(" Include optional components"));
    const subbuildLabel = node("label");
    const subbuild = node("input"); subbuild.type = "checkbox"; subbuild.dataset.bomSubbuilds = "";
    subbuildLabel.append(subbuild, document.createTextNode(" Include active sub-build requirements"));
    if (buildMode) controls.append(subbuildLabel);
    else controls.append(quantityLabel, expandLabel, optionalLabel);
    const status = node("p"); status.dataset.wledPreviewStatus = "";
    const actions = node("div"); actions.style.cssText = "display:flex;flex-wrap:wrap;gap:8px";
    const locate = node("button", "Highlight remaining components"); locate.type = "button"; locate.disabled = true;
    locate.dataset.bomLocate = "";
    const refresh = node("button", "Refresh component preview"); refresh.type = "button";
    const off = node("button", "All off"); off.type = "button";
    actions.append(locate, refresh, off);
    const result = node("p"); result.dataset.wledResult = "";
    const checklist = node("div"); checklist.dataset.pickingChecklist = "";
    const detailSection = node("details");
    detailSection.style.minWidth = "0";
    detailSection.append(node("summary", "Component details and stock"));
    const content = node("div"); content.style.overflowX = "auto";
    detailSection.append(content);
    target.append(controls, status, actions, result, checklist, detailSection);
    registerPanel(target, context);
    let plan = null;
    const picking = createPickingChecklist(checklist, {storageKey: context.picking_storage_key, buildMode,
        renderThumbnail: part => thumbnail(part, 72), onChange: syncPicking});
    if (picking.savedOptions) {
        if (buildMode) subbuild.checked = picking.savedOptions.include_subbuilds;
        else {
            quantity.value = String(picking.savedOptions.quantity);
            expand.checked = picking.savedOptions.expand;
            optional.checked = picking.savedOptions.include_optional;
        }
    }

    function syncPicking() {
        const remaining = new Set(picking.remainingIds());
        setControlDisabled(locate, !plan?.can_locate || !plan.components.some(row => row.can_locate && remaining.has(row.part.id)));
        for (const button of content.querySelectorAll("button[data-highlight-part]")) {
            const id = Number(button.dataset.highlightPart);
            const row = plan?.components.find(item => item.part.id === id);
            setControlDisabled(button, !row?.can_locate || !remaining.has(id));
        }
    }

    function options() {
        if (buildMode) return {include_subbuilds: subbuild.checked};
        const count = Number(quantity.value);
        if (!/^\d+$/.test(quantity.value) || !Number.isSafeInteger(count) || count < 1 || count > 10000) {
            throw new Error("Enter an assembly quantity from 1 to 10000.");
        }
        return {quantity: count, expand: expand.checked, include_optional: optional.checked};
    }

    function invalidate() {
        plan = null;
        picking.invalidate();
        setControlDisabled(locate, true);
        for (const button of content.querySelectorAll("button")) setControlDisabled(button, true);
        status.textContent = "Refresh the preview to check the current components and quantities.";
    }

    function render(payload) {
        const requested = options();
        const matchesTarget = buildMode
            ? payload.build?.id === context.build_id && payload.include_subbuilds === requested.include_subbuilds
            : payload.assembly?.id === context.part_id && payload.quantity === requested.quantity
                && payload.expand === requested.expand && payload.include_optional === requested.include_optional;
        if (!Array.isArray(payload.components) || typeof payload.can_locate !== "boolean"
                || !matchesTarget
                || !payload.summary || payload.components.some(row => !Number.isSafeInteger(row.part?.id) || row.part.id < 1
                    || typeof row.can_locate !== "boolean" || !Array.isArray(row.locations))
                || payload.can_locate !== payload.components.some(row => row.can_locate)
                || payload.summary.components !== payload.components.length
                || payload.summary.locatable_components !== payload.components.filter(row => row.can_locate).length) {
            throw new Error("Invalid component preview. Refresh before highlighting.");
        }
        plan = payload;
        const summary = payload.summary;
        status.textContent = `${summary.locatable_components} of ${summary.components} component types can be highlighted across ${summary.unique_locations} locations. ${summary.short_components} component types are short for this quantity.`;
        if (buildMode) {
            status.textContent = `${payload.build.reference}: build quantity ${payload.build.quantity}, completed ${payload.build.completed}. ${summary.builds} active build order(s) included. ` + status.textContent;
            if (!payload.build.active) status.textContent = "This build is complete or cancelled. No outstanding components will be highlighted.";
        }
        if (summary.optional_lines_skipped) status.textContent += ` ${summary.optional_lines_skipped} optional BOM lines excluded.`;
        if (payload.expand) status.textContent += " Expanded view shows raw components instead of finished subassemblies.";
        content.replaceChildren();
        if (!payload.components.length) {
            content.append(node("p", "No required components in this BOM for the selected options."));
        } else {
            const table = node("table"); table.style.cssText = "width:100%;border-collapse:collapse;font-size:14px";
            const head = node("thead"); const headings = node("tr");
            for (const label of ["Component / BOM references", buildMode ? "Remaining" : "Required", "In stock", buildMode ? "Usable incl. allocated" : "Available", "Locations / status", ""]) headings.append(node("th", label));
            head.append(headings); table.append(head);
            const body = node("tbody");
            for (const row of payload.components) {
                const tr = node("tr"); tr.dataset.bomPart = String(row.part.id);
                const identity = node("td");
                const title = node("div"); title.style.cssText = "display:flex;gap:8px;align-items:center";
                title.append(thumbnail(row.part), node("strong", row.part.full_name || row.part.name));
                identity.append(title);
                const refs = (row.sources || []).map(source => `${source.build?.reference || source.assembly.name}: ${source.reference || "No reference"}${buildMode ? ` (remaining ${amount(source.quantity)}, short ${amount(source.shortage)})` : ""}`);
                if (refs.length) identity.append(node("small", refs.join("; ")));
                const units = row.part.units ? ` ${row.part.units}` : "";
                tr.append(identity, node("td", amount(row.required_quantity) + units), node("td", amount(row.stock_quantity) + units), node("td", amount(row.available_quantity) + units));
                const details = node("td");
                for (const group of row.locations) {
                    const line = node("p", `${group.location?.path || "No assigned location"} — ${amount(group.available_quantity)} available`);
                    line.style.margin = "0 0 5px";
                    if (group.reason) line.append(document.createTextNode(`; ${group.reason}`));
                    else if (group.indicators?.length) line.append(document.createTextNode(`; ${displayIndicators(group.indicators)}`));
                    details.append(line);
                }
                if (!row.locations.length) details.append(node("p", "No on-hand stock"));
                if (Number(row.shortage) > 0) details.append(node("strong", `Short: ${amount(row.shortage)}`));
                if (buildMode) {
                    details.append(node("p", `Allocated: ${amount(row.allocated_quantity)}; usable allocated: ${amount(row.allocated_available_quantity)}; consumed: ${amount(row.consumed_quantity)}.`));
                    for (const group of row.locations) {
                        if (Number(group.allocated_quantity) > 0) details.append(node("p", `Allocated stock: ${(group.stock_parts || []).join(", ")} — ${amount(group.allocated_quantity)} at ${group.location?.path || "no assigned location"}.`));
                    }
                    for (const planned of row.planned_outputs || []) details.append(node("p", `Sub-build ${planned.build}: ${planned.quantity} output(s) remaining. Planned outputs are not counted as stock.`));
                } else if (Number(row.stock_quantity) > Number(row.available_quantity)) details.append(node("p", "Reserved quantities excluded from availability and highlighting."));
                if (row.virtual) details.append(node("p", "Virtual part has no physical stock to highlight."));
                if (row.unexpanded_assembly) details.append(node("p", "Subassembly has no required component BOM to expand."));
                if ((row.sources || []).some(source => !source.validated)) details.append(node("p", "BOM line not validated."));
                const cell = node("td"); const button = node("button", "Highlight"); button.type = "button";
                button.dataset.highlightPart = String(row.part.id);
                setControlDisabled(button, !row.can_locate);
                button.addEventListener("click", () => action("locate", row.part.id)); cell.append(button);
                tr.append(details, cell); body.append(tr);
            }
            table.append(body);
            for (const cell of table.querySelectorAll("th, td")) cell.style.cssText = "text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #aaa";
            content.append(table);
        }
        content.append(node("p", buildMode
            ? "Usable stock includes this scope's allocations and unreserved stock for uncovered requirements. Reservations for other work are excluded. Source-location restrictions apply to unreserved stock. Shared stock is counted once; availability is an estimate, not a reservation. Already allocated alternatives are listed by their actual stock part; new alternatives are not selected. Sub-builds use their own saved requirements; planned outputs are not physical stock."
            : "Available quantities exclude reservations. Only exact BOM parts are shown; variants and substitutes are not selected automatically."));
        picking.update(payload, requested);
    }

    async function load() {
        invalidate();
        status.textContent = "Checking component stock and locations…";
        try {
            const payload = await fetchJson(context.preview_url, {method: "POST", payload: options(), csrfToken: context.csrf_token});
            if (target.isConnected) render(payload);
        } catch (error) {
            invalidate();
            status.textContent = `${error.message} Use Refresh component preview to retry.`;
        }
    }

    async function action(kind, componentId) {
        if (panelRequestPending() || (kind === "locate" && !plan?.can_locate)) return;
        if (kind === "locate" && !picking.remainingIds().some(id => plan.components.some(row => row.part.id === id && row.can_locate))) return;
        if (componentId && (picking.isCollected(componentId) || !plan.components.some(row => row.part.id === componentId && row.can_locate))) return;
        let payload;
        try { payload = kind === "off" ? {} : {...options(), ...picking.selection(), ...(componentId ? {component_id: componentId} : {})}; }
        catch (error) { invalidate(); status.textContent = error.message; return; }
        await withPanelLoading(async () => {
            result.textContent = kind === "off" ? "Turning lights off…" : "Highlighting available component locations…";
            try {
                const response = await fetchJson(kind === "off" ? context.off_url : context.locate_url,
                    {method: "POST", payload, csrfToken: context.csrf_token});
                if (kind === "locate" && (response.action !== (buildMode ? "build-component-locate" : "component-locate") || !Number.isSafeInteger(response.highlighted_components)
                        || response.highlighted_components < 1 || !Number.isSafeInteger(response.highlighted_locations) || response.highlighted_locations < 1)) {
                    const error = new Error("The highlighting result could not be verified.");
                    error.uncertain = true;
                    throw error;
                }
                result.textContent = kind === "off" ? "All locator lights are off." : `Highlighted ${response.highlighted_components} component types across ${response.highlighted_locations} locations.`;
            } catch (error) {
                result.textContent = `${error.message}${error.uncertain ? " Some lights may have changed; check them before retrying." : ""}`;
            }
            await load();
        });
    }

    quantity.addEventListener("input", invalidate);
    for (const control of [quantity, expand, optional, subbuild]) control.addEventListener("change", () => {
        result.textContent = "";
        try { picking.changeOptions(options()); } catch { /* load() reports invalid input. */ }
        void withPanelLoading(load);
    });
    refresh.addEventListener("click", () => { if (!panelRequestPending()) void withPanelLoading(load); });
    locate.addEventListener("click", () => action("locate"));
    off.addEventListener("click", () => action("off"));
    void withPanelLoading(load);
}
