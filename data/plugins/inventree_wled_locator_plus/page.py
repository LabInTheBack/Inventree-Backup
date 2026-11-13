"""Render the dashboard shell with local assets and a Django CSRF token."""

from pathlib import Path
from string import Template

from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils.html import escape, json_script

from .constants import BASE_URL


def render_index_page(plugin, request=None):
    root = Path(__file__).parent
    html = Template((root / "templates" / "dashboard.html").read_text()).substitute(
        csrf_token=escape(get_token(request)),
        finder_url=escape(f"{BASE_URL}finder/"),
        config=json_script({
            "data_url": f"{BASE_URL}dashboard/data/", "action_url": f"{BASE_URL}dashboard/action/",
        }, "dashboard-config"),
        styles=(root / "static" / "dashboard_page.css").read_text(),
        script=(root / "static" / "dashboard_page.js").read_text(),
    )
    response = HttpResponse(html)
    response["Cache-Control"] = "no-store"
    return response
