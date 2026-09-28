"""Network timeout guard.

akshare's internal requests.get() calls carry no timeout, so a hanging network
would block forever. This module monkeypatches requests to inject a default
timeout on every HTTP call, covering all akshare endpoints at once.

Import this module before any akshare call (import side-effect installs patch):
    from app.data import net_guard  # noqa: F401

requests raises on timeout and closes the underlying socket, so no threads are
left running (unlike a ThreadPoolExecutor timeout, which leaves the worker
thread alive).
"""

import functools

import requests

# Default timeout in seconds applied to any request that did not set one.
DEFAULT_TIMEOUT: float = 15.0

_orig_request = requests.sessions.Session.request


@functools.wraps(_orig_request)
def _request_with_timeout(self, method, url, **kwargs):
    if kwargs.get("timeout") is None:
        kwargs["timeout"] = DEFAULT_TIMEOUT
    return _orig_request(self, method, url, **kwargs)


requests.sessions.Session.request = _request_with_timeout
