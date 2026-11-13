"""Short-lived services shared by one request or native locate operation."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


_current_operation = ContextVar("wled_locator_operation", default=None)


class Operation:
    """Keep caches out of the long-lived InvenTree plugin instance."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.settings = {}
        self.wled = None
        self.locator = None
        self.finder = None


def current_operation(plugin):
    """Return this plugin's operation, without creating a persistent cache."""
    current = _current_operation.get()
    return current if current is not None and current.plugin is plugin else None


@contextmanager
def operation(plugin):
    """Reuse nested operations and discard their caches even after failure."""
    current = current_operation(plugin)
    if current is not None:
        yield current
        return

    current = Operation(plugin)
    token = _current_operation.set(current)
    try:
        yield current
    finally:
        _current_operation.reset(token)


def scoped_operation(method):
    """Scope a plugin method or PluginViews callback to a single operation."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        plugin = getattr(self, "plugin", self)
        with operation(plugin):
            return method(self, *args, **kwargs)

    return wrapped
