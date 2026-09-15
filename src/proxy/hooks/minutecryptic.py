"""Bot/solver extension point for minutecryptic.com traffic.

Define request(flow) and/or response(flow) here to inspect or modify
minutecryptic's HTTP traffic (mitmproxy.http.HTTPFlow). Both are optional
and no-ops by default.
"""

from mitmproxy import http


def request(flow: http.HTTPFlow) -> None:
    pass


def response(flow: http.HTTPFlow) -> None:
    pass
