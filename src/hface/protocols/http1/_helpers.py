from __future__ import annotations

_FIELD_NAME_CASE = {
    # https://www.iana.org/assignments/http-fields/http-fields.xhtml
    b"alpn": b"ALPN",
    b"amp": b"AMP",
    b"cdn": b"CDN",
    b"ch": b"CH",
    b"ct": b"CT",
    b"caldav": b"CalDAV",
    b"dasl": b"DASL",
    b"dav": b"DAV",
    b"ediint": b"EDIINT",
    b"etag": b"ETag",
    b"entityid": b"EntityId",
    b"gpc": b"GPC",
    b"getprofile": b"GetProfile",
    b"http2": b"HTTP2",
    b"id": b"ID",
    b"im": b"IM",
    b"md5": b"MD5",
    b"mime": b"MIME",
    b"maxversion": b"MaxVersion",
    b"odata": b"OData",
    b"oscore": b"OSCORE",
    b"oslc": b"OSLC",
    b"p3p": b"P3P",
    b"pep": b"PEP",
    b"pics": b"PICS",
    b"profileobject": b"ProfileObject",
    b"slug": b"SLUG",
    b"setprofile": b"SetProfile",
    b"soapaction": b"SoapAction",
    b"tcn": b"TCN",
    b"te": b"TE",
    b"ttl": b"TTL",
    b"uri": b"URI",
    b"www": b"WWW",
    b"websocket": b"WebSocket",
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers
    b"dns": b"DNS",
    b"dpr": b"DPR",
    b"ect": b"ECT",
    b"nel": b"NEL",
    b"rtt": b"RTT",
    b"sourcemap": b"SourceMap",
    b"ua": b"UA",
}


def _capitalize_word(part: bytes) -> bytes:
    if part in _FIELD_NAME_CASE:
        return _FIELD_NAME_CASE[part]
    return part.capitalize()


def capitalize_field_name(name: bytes) -> bytes:
    """
    Convert field (header) name to its canonical form.

    Header names are case-insensitive, but it is common to send
    capitalized in HTTP/1.1.
    """
    parts = name.lower().split(b"-")
    return b"-".join(_capitalize_word(part) for part in parts)
