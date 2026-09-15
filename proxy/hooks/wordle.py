"""Bot/solver extension point for NYT Wordle traffic.

Define request(flow) and/or response(flow) here to inspect or modify
Wordle's HTTP traffic (mitmproxy.http.HTTPFlow). Both are optional and
no-ops by default.
"""

from mitmproxy import http


def request(flow: http.HTTPFlow) -> None:
    pass


def response(flow: http.HTTPFlow) -> None:
    pass
