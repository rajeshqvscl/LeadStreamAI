"""
Shared HTTP Client with proper SSL verification.
Replaces all verify=False calls with a configurable, secure client.
"""
import logging
import os

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def _get_ssl_verify() -> bool | str:
    """
    Returns SSL verification setting.
    - True: Use system certifi bundle (default, secure)
    - Path to CA bundle: For internal services with custom CAs
    - False: ONLY for local development with DEBUG=True
    """
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        logger.warning("SSL verification DISABLED - DEBUG mode only!")
        return False

    # Check for custom CA bundle for internal services (e.g., RAG service)
    custom_ca = os.getenv("RAG_CA_BUNDLE_PATH")
    if custom_ca and os.path.exists(custom_ca):
        return custom_ca

    # Default: Use Mozilla CA bundle via certifi
    return certifi.where()


def _create_session() -> requests.Session:
    """Create a requests session with retry logic and proper SSL."""
    session = requests.Session()

    # Configure retries with exponential backoff
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# Global session instance (thread-safe for reads)
_http_session: requests.Session | None = None


def get_http_session() -> requests.Session:
    """Get or create the shared HTTP session."""
    global _http_session
    if _http_session is None:
        _http_session = _create_session()
    return _http_session


def secure_request(
    method: str,
    url: str,
    *,
    timeout: int = 30,
    verify: bool | str | None = None,
    **kwargs
) -> requests.Response:
    """
    Make an HTTP request with proper SSL verification.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Target URL
        timeout: Request timeout in seconds
        verify: SSL verification (True, cert path, or False for DEBUG only)
        **kwargs: Additional arguments passed to requests.request()

    Returns:
        requests.Response object

    Raises:
        requests.RequestException: On network/HTTP errors
    """
    session = get_http_session()

    # Use provided verify or fall back to secure default
    if verify is None:
        verify = _get_ssl_verify()

    # Log SSL mode for debugging (without exposing cert paths)
    ssl_mode = "custom_ca" if isinstance(verify, str) else ("disabled" if verify is False else "system_ca")
    logger.debug(f"HTTP {method} {url} - SSL verify: {ssl_mode}")

    return session.request(
        method=method,
        url=url,
        timeout=timeout,
        verify=verify,
        **kwargs
    )


# Convenience methods
def get(url: str, **kwargs) -> requests.Response:
    return secure_request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return secure_request("POST", url, **kwargs)


def put(url: str, **kwargs) -> requests.Response:
    return secure_request("PUT", url, **kwargs)


def delete(url: str, **kwargs) -> requests.Response:
    return secure_request("DELETE", url, **kwargs)


# For file uploads that need multipart/form-data
def post_multipart(url: str, files: dict, **kwargs) -> requests.Response:
    """POST with multipart file upload."""
    # Don't set Content-Type header - requests will set it with boundary
    headers = kwargs.pop("headers", {})
    headers.pop("Content-Type", None)  # Let requests set multipart boundary
    return secure_request("POST", url, files=files, headers=headers, **kwargs)


# --- Bounded single-attempt calls (no auto-retry) ---
#
# The shared session above retries up to 3x with backoff. That is fine for
# idempotent GETs, but it is actively harmful for two cases:
#   1. Non-idempotent upload endpoints (e.g. RAG /process /ingest) where a
#      retry can double-process the same document.
#   2. Any upstream that accepts the connection but never responds: a hung
#      call can block the caller for `retries * timeout` seconds (e.g. 3 x 300s
#      = 15 minutes) inside a reply-processing path.
#
# `secure_request_bounded()` uses its own session with auto-retry disabled, so
# each call fails after exactly one `timeout` window. Pick a timeout that the
# healthy upstream comfortably beats and treat the call as enrichment-only:
# if it fails, the caller must continue without the result.
_bounded_session: requests.Session | None = None


def get_bounded_session() -> requests.Session:
    """Session with auto-retry disabled — one attempt per call."""
    global _bounded_session
    if _bounded_session is None:
        session = requests.Session()
        no_retry = Retry(total=0, connect=0, read=0, status=0, redirect=0, other=0)
        adapter = HTTPAdapter(max_retries=no_retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _bounded_session = session
    return _bounded_session


def secure_request_bounded(
    method: str,
    url: str,
    *,
    timeout: int = 30,
    verify: bool | str | None = None,
    **kwargs
) -> requests.Response:
    """
    Single-attempt HTTP request (no auto-retry, no backoff waits).

    Use for non-idempotent uploads and for upstreams that may hang — the call
    returns/raises after exactly one `timeout` window. SSL verification follows
    the same rules as :func:`secure_request`.
    """
    if verify is None:
        verify = _get_ssl_verify()
    return get_bounded_session().request(
        method=method,
        url=url,
        timeout=timeout,
        verify=verify,
        **kwargs
    )
