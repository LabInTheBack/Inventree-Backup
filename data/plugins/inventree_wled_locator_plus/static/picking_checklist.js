import {setControlDisabled} from "./panel_common.js";

function element(tag, text) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    return item;
}

function amount(value) {
    return String(value).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
}

function validOptions(value, build) {
    return value && typeof value === "object" && !Array.isArray(value) && (build
        ? Object.keys(value).length === 1 && typeof value.include_subbuilds === "boolean"
        : Object.keys(value).length === 3 && Number.isSafeInteger(value.quantity) && value.quantity >= 1 && value.quantity <= 10000
            && typeof value.expand === "boolean" && typeof value.include_optional === "boolean");
}

function optionKey(value, build) {
    return build ? String(value.include_subbuilds) : `${value.quantity}/${value.expand}/${value.include_optional}`;
}

export function createPickingChecklist(target, {storageKey, buildMode, renderThumbnail, onChange}) {
    let picked = new Map();
    let savedOptions = null;
    let currentOptions = null;
    let plan = null;
    let ready = false;
    let storageOK = Boolean(storageKey);
    let resetCount = 0;
    try {
        const raw = storageKey ? localStorage.getItem(storageKey) : null;
        if (raw && raw.length <= 131072) {
            const record = JSON.parse(raw);
            if (record && typeof record === "object" && record.version === 1 && validOptions(record.options, buildMode) && Array.isArray(record.collected) && record.collected.length <= 1000) {
                const entries = record.collected;
                if (entries.every(row => row && Number.isSafeInteger(row.id) && row.id > 0 && typeof row.fingerprint === "string" && /^[0-9a-f]{64}$/.test(row.fingerprint))
                        && new Set(entries.map(row => row.id)).size === entries.length) {
                    savedOptions = record.options;
                    picked = new Map(entries.map(row => [row.id, row.fingerprint]));
                }
            }
        }
    } catch (error) {
        if (!(error instanceof SyntaxError)) storageOK = false;
    }

    function save() {
        if (!storageOK || !currentOptions) return;
        try {
            localStorage.setItem(storageKey, JSON.stringify({version: 1, options: currentOptions,
                collected: Array.from(picked, ([id, fingerprint]) => ({id, fingerprint}))}));
        } catch { storageOK = false; }
    }

    function isCollected(id) { return picked.has(id); }

    function render() {
        target.replaceChildren();
        const heading = element("h3", "Pick by storage location");
        heading.style.margin = "0";
        const progress = element("p", `Picking progress: ${picked.size} of ${plan?.components.length || 0} component types collected.`);
        progress.dataset.pickingProgress = "";
        progress.setAttribute("role", "status");
        progress.setAttribute("aria-live", "polite");
        target.append(heading, progress);
        if (!ready) {
            target.append(element("p", "Picking needs a current preview from the updated backend. Restart InvenTree after updating, then refresh the preview."));
            return;
        }
        target.append(element("p", "Check Collected after gathering the full quantity for that component across its locations. Matching checkboxes move together. This checklist does not change stock or allocations."));
        if (resetCount) target.append(element("p", `${resetCount} collected checkmark(s) reset because their requirements changed.`));
        if (!storageOK) target.append(element("p", "Progress cannot be saved in this browser; it will last only on this page."));
        const reset = element("button", "Reset picking progress");
        reset.type = "button";
        setControlDisabled(reset, picked.size === 0);
        reset.addEventListener("click", () => {
            picked.clear(); resetCount = 0; save(); render(); onChange();
        });
        target.append(reset);
        const parts = new Map(plan.components.map(row => [row.part.id, row]));
        const itemRow = (entry, missing) => {
            const row = parts.get(entry.part_id);
            const item = element("li");
            item.dataset.pickPart = String(entry.part_id);
            item.style.cssText = "display:grid;grid-template-columns:minmax(0,1fr) 72px;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #ccc";
            const details = element("div");
            details.style.cssText = "display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-width:0";
            const label = element("label");
            const check = element("input"); check.type = "checkbox";
            check.checked = isCollected(entry.part_id);
            check.dataset.pickCollected = String(entry.part_id);
            check.setAttribute("aria-label", `Collected ${row.part.full_name || row.part.name} (all locations)`);
            setControlDisabled(check, false);
            label.append(check, document.createTextNode(" Collected"));
            const name = element("strong", row.part.full_name || row.part.name);
            name.style.cssText = "min-width:0;overflow-wrap:anywhere";
            const units = row.part.units ? ` ${row.part.units}` : "";
            const text = element("span", `${missing ? "Still needed" : "Collect here"}: ${amount(entry.quantity)}${units} (${amount(row.required_quantity)}${units} total)`);
            if (check.checked) { name.style.textDecoration = "line-through"; text.style.opacity = "0.6"; }
            details.append(label, name, text);
            if (!missing && entry.reason) details.append(element("small", entry.reason));
            const picture = renderThumbnail(row.part);
            picture.dataset.pickImage = "";
            item.append(details, picture);
            check.addEventListener("change", () => {
                if (!ready) return;
                if (check.checked) picked.set(row.part.id, row.picking_fingerprint);
                else picked.delete(row.part.id);
                save(); render(); onChange();
            });
            return item;
        };
        for (const group of plan.picking.locations) {
            const section = element("section");
            section.dataset.pickingLocation = String(group.location?.id || "unassigned");
            const title = element("h4", group.location?.path || "Stock without an assigned location");
            title.style.overflowWrap = "anywhere";
            section.append(title);
            const list = element("ul"); list.style.cssText = "list-style:none;padding:0;margin:0";
            for (const item of group.items) list.append(itemRow(item, false));
            section.append(list); target.append(section);
        }
        if (plan.picking.shortages.length) {
            const section = element("section");
            section.dataset.pickingShortages = "";
            section.append(element("h4", "Still needed — no suggested stock"));
            const list = element("ul"); list.style.cssText = "list-style:none;padding:0;margin:0";
            for (const item of plan.picking.shortages) list.append(itemRow(item, true));
            section.append(list); target.append(section);
        }
    }

    return {
        savedOptions,
        isCollected,
        remainingIds: () => ready ? plan.components.filter(row => !isCollected(row.part.id)).map(row => row.part.id) : [],
        selection: () => ({remaining_component_ids: plan.components.filter(row => !isCollected(row.part.id)).map(row => row.part.id), picking_revision: plan.picking.revision}),
        invalidate() {
            ready = false;
            for (const control of target.querySelectorAll("input, button")) setControlDisabled(control, true);
        },
        changeOptions(options) {
            if (!validOptions(options, buildMode)) return;
            if (currentOptions && optionKey(currentOptions, buildMode) !== optionKey(options, buildMode)) picked.clear();
            currentOptions = options;
            save();
        },
        update(value, options) {
            plan = value;
            currentOptions = options;
            const ids = new Set(value.components.map(row => row.part.id));
            ready = value.picking?.version === 1 && typeof value.picking.revision === "string" && /^[0-9a-f]{64}$/.test(value.picking.revision)
                && Array.isArray(value.picking.locations) && Array.isArray(value.picking.shortages)
                && value.components.every(row => typeof row.picking_fingerprint === "string" && /^[0-9a-f]{64}$/.test(row.picking_fingerprint))
                && value.picking.locations.every(group => Array.isArray(group.items) && group.items.every(item => ids.has(item.part_id)))
                && value.picking.shortages.every(item => ids.has(item.part_id));
            resetCount = 0;
            if (ready) {
                const valid = new Map(value.components.map(row => [row.part.id, row.picking_fingerprint]));
                for (const [id, fingerprint] of picked) {
                    if (valid.get(id) !== fingerprint) { picked.delete(id); resetCount += 1; }
                }
            }
            render();
            onChange();
        },
    };
}
