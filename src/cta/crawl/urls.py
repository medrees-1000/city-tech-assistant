"""URL normalization and the host/login rules shared by the crawler."""

from urllib.parse import urljoin, urlsplit, urlunsplit

LOGIN_WORDS = ("login", "logout", "signin", "sso", "cas/")


def normalize_url(url: str) -> str:
    """Return an https URL with a lowercase host, default port and no fragment."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"not an http(s) URL: {url!r}")
    netloc = parts.hostname.lower()
    if parts.port and parts.port not in (80, 443):
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))


def resolve_redirect(current_url: str, location: str) -> str:
    """Resolve a Location header (possibly relative) against the current URL and normalize it."""
    return normalize_url(urljoin(current_url, location))


def host_of(url: str) -> str:
    return urlsplit(url).hostname or ""


def looks_like_login(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(word in path for word in LOGIN_WORDS)
