from mitmproxy.test import tflow, tutils

from src.proxy.hooks import chess


def test_chess_keeps_api_calls_on_the_page_origin() -> None:
    script = (
        b"function vMe(e){let t=e.split(`.`);if(t.length<2)return e;let[n,...r]=t;"
        b"return n===`api`||n.startsWith(`api-`)?e:Ug()?[`api-${n}`,...r].join(`.`)"
        b":[`api`,...r].join(`.`)}"
        b"let e=new URL(t),n=window.location;if(e.origin!==n.origin)"
        b"if(n.hostname===`localhost`)t=t.replace(e.origin,n.origin);"
        b"x=window.location.hostname===`localhost`;y=a===`api`||b.startsWith(`api-`)?1:2"
    )
    flow = tflow.tflow(
        resp=tutils.tresp(
            content=script, headers=[(b"content-type", b"text/javascript")]
        )
    )
    chess.response(flow)
    assert flow.response is not None
    assert flow.response.content == (
        b"function vMe(e){let t=e.split(`.`);if(t.length<2)return e;let[n,...r]=t;"
        b"return !0?e:Ug()?[`api-${n}`,...r].join(`.`)"
        b":[`api`,...r].join(`.`)}"
        b"let e=new URL(t),n=window.location;if(e.origin!==n.origin)"
        b"if(!0)t=t.replace(e.origin,n.origin);"
        b"x=!0;y=a===`api`||b.startsWith(`api-`)?1:2"
    )
