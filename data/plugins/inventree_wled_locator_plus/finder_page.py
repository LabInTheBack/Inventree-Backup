"""Render the typed finder without loading inventory or contacting controllers."""

from pathlib import Path
from string import Template

from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils.html import escape, json_script

from .constants import BASE_URL
from .finder import MAX_QUERIES, MAX_QUERY_LENGTH, MAX_QUERY_TERMS, MAX_SELECTED_PARTS


def render_finder_page(request):
    """Inline the small local assets so activation needs no static collection."""
    root = Path(__file__).parent
    user_id = getattr(getattr(request, "user", None), "pk", None)
    config = {
        "storage_key": f"wled-locator-plus.finder.v1.user.{user_id}" if user_id is not None else None,
        "search_url": f"{BASE_URL}finder/search/",
        "preview_url": f"{BASE_URL}finder/preview/",
        "locate_url": f"{BASE_URL}finder/locate/",
        "off_url": f"{BASE_URL}finder/off/",
        "max_queries": MAX_QUERIES,
        "max_query_length": MAX_QUERY_LENGTH,
        "max_query_terms": MAX_QUERY_TERMS,
        "max_selected_parts": MAX_SELECTED_PARTS,
    }
    html = Template((root / "templates" / "finder.html").read_text()).substitute(
        csrf_token=escape(get_token(request)),
        dashboard_url=escape(BASE_URL),
        config=json_script(config, "finder-config"),
        styles=(root / "static" / "finder_page.css").read_text(),
        script=(root / "static" / "finder_page.js").read_text(),
        max_queries=MAX_QUERIES,
    )
    response = HttpResponse(html)
    response["Cache-Control"] = "no-store"
    return response
