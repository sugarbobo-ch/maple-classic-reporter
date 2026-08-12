from urllib.parse import urlsplit


def is_safe_https_url(value: str) -> bool:
    """Allow only ordinary HTTPS URLs before handing them to the OS browser."""

    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and bool(hostname)
        and port in (None, 443)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )
