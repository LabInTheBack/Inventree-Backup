const LOCATOR_PAGE = "/plugin/wled-locator-plus/";

export function openLocatorPage() {
    window.location.href = LOCATOR_PAGE;
}

export async function openContextPanel() {
    const target = getCurrentTarget();

    if (!target) {
        window.location.href = LOCATOR_PAGE;
        return;
    }

    if (target.model === "part") {
        window.location.href = `/web/part/${target.id}/`;
        return;
    }

    if (target.model === "stock-item") {
        window.location.href = `/web/stock/item/${target.id}/assign-external-indicator-stock-item`;
        return;
    }

    if (target.model === "stock-location") {
        window.location.href = `/web/stock/location/${target.id}/assign-external-indicator-stock-location`;
        return;
    }

    window.location.href = LOCATOR_PAGE;
}

export async function assignStockItemLed() {
    const target = getCurrentTarget();

    if (target?.model === "stock-item") {
        window.location.href = `/web/stock/item/${target.id}/assign-external-indicator-stock-item`;
        return;
    }

    if (target?.model === "stock-location") {
        window.location.href = `/web/stock/location/${target.id}/assign-external-indicator-stock-location`;
        return;
    }

    window.location.href = LOCATOR_PAGE;
}

function getCurrentTarget() {
    const path = window.location.pathname;

    let match = path.match(/^\/web\/part\/(\d+)(?:\/|$)/);
    if (match) {
        return { model: "part", id: Number.parseInt(match[1], 10) };
    }

    match = path.match(/^\/web\/stock\/item\/(\d+)(?:\/|$)/);
    if (match) {
        return { model: "stock-item", id: Number.parseInt(match[1], 10) };
    }

    match = path.match(/^\/web\/stock\/location\/(\d+)(?:\/|$)/);
    if (match) {
        return { model: "stock-location", id: Number.parseInt(match[1], 10) };
    }

    return null;
}
