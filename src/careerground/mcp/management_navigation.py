"""Server-configured management URLs; never derive trust from request headers."""

from urllib.parse import urlsplit


def validate_management_origin(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("Invalid management origin")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid management origin") from None
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or any(c.isspace() or ord(c) < 32 for c in value)
        or "\\" in value
        or "%" in parsed.netloc
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("Invalid management origin")
    return value.rstrip("/")
