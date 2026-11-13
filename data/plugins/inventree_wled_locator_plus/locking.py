"""Coordinate complete hardware actions across server and worker processes."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path


_held_lock = ContextVar("wled_locator_hardware_lock", default=None)


class LocatorBusyError(RuntimeError):
    """Another process is currently operating the locator controllers."""


def lock_path() -> Path:
    """Use the media volume shared by all InvenTree server/worker containers."""
    from django.conf import settings

    return Path(settings.MEDIA_ROOT) / ".wled-locator-plus.lock"


@contextmanager
def hardware_action():
    """Reject overlapping actions; nested calls share the already-held lock.

    Keep the lock file in place: unlinking it would let a second process lock a
    different inode. The OS releases the lock if a worker exits unexpectedly.
    """
    if _held_lock.get() is not None:
        yield
        return

    with lock_path().open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LocatorBusyError("Another locate action is running; please try again") from exc
        token = _held_lock.set(handle)
        try:
            yield
        finally:
            _held_lock.reset(token)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def serialized_action(method):
    """Protect standalone clear/set calls as well as complete locate actions."""
    @wraps(method)
    def wrapped(*args, **kwargs):
        with hardware_action():
            return method(*args, **kwargs)

    return wrapped
