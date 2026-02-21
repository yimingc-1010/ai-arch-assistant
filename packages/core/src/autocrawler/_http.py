"""Shared HTTP session utilities."""

import requests

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
)


def make_session(extra_headers: dict | None = None) -> requests.Session:
    """Return a pre-configured requests.Session."""
    session = requests.Session()
    headers = {'User-Agent': DEFAULT_USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    session.headers.update(headers)
    return session


def fix_encoding(response: requests.Response) -> None:
    """Fix ISO-8859-1 misdetection common on Chinese sites (in-place)."""
    if response.encoding == 'ISO-8859-1':
        response.encoding = response.apparent_encoding
