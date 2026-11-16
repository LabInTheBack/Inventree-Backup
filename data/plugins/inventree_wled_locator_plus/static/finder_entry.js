const FINDER_PAGE = "/plugin/wled-locator-plus/finder/";

export function openFinder() {
    window.location.assign(FINDER_PAGE);
}

// Two arguments select InvenTree's DOM renderer rather than its React renderer.
export function renderFinderEntry(target, data) {
    const link = document.createElement("a");
    link.href = FINDER_PAGE;
    link.textContent = "Open Part Finder";
    target.replaceChildren(link);
    window.location.replace(FINDER_PAGE);
}

export function renderFinderShortcut(target, data) {
    const card = document.createElement("div");
    card.style.cssText = "display:grid;align-content:center;gap:10px;height:100%;padding:8px;";
    const title = document.createElement("strong");
    title.textContent = "Part Finder";
    const description = document.createElement("p");
    description.style.cssText = "margin:0;font-size:0.9rem;opacity:.8;";
    description.textContent = "Find several parts by text or voice, then light their stock locations.";
    const link = document.createElement("a");
    link.href = FINDER_PAGE;
    link.textContent = "Open Part Finder →";
    link.style.cssText = "justify-self:start;font:inherit;font-weight:600;padding:9px 14px;border-radius:8px;background:#2463a4;color:white;text-decoration:none;";
    card.append(title, description, link);
    target.replaceChildren(card);
}
