"""MSAL device code flow for user-level Power BI authentication.

Provides interactive login for DAX queries against RLS-enabled models,
where service principal authentication is not supported.
Token cache is persisted locally with DPAPI encryption on Windows.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import msal

from powerbi_mcp.config.settings import Settings

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".powerbi-mcp"
CACHE_FILE = str(CACHE_DIR / "token_cache.bin")
CLIENT_ID = "9ed15462-1e96-49b9-b362-aa86c139a177"
SCOPES = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]


def _build_cache() -> msal.SerializableTokenCache:
    """Build a persistent MSAL token cache with encryption where available.

    Returns:
        Token cache backed by encrypted file on Windows, plain file otherwise.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from msal_extensions import (
            FilePersistenceWithDataProtection,
            PersistedTokenCache,
        )

        persistence = FilePersistenceWithDataProtection(CACHE_FILE)
        cache = PersistedTokenCache(persistence)
        cache._is_encrypted = True
        return cache
    except (ImportError, RuntimeError):
        pass

    try:
        from msal_extensions import FilePersistence, PersistedTokenCache

        persistence = FilePersistence(CACHE_FILE)
        cache = PersistedTokenCache(persistence)
        cache._is_encrypted = False
        return cache
    except ImportError:
        logger.warning("msal-extensions not available, using in-memory token cache")
        cache = msal.SerializableTokenCache()
        cache._is_encrypted = False
        return cache


def _build_app(cache: msal.SerializableTokenCache | None = None) -> msal.PublicClientApplication:
    """Build an MSAL PublicClientApplication for device code flow.

    Args:
        cache: Optional token cache for persistence.

    Returns:
        Configured MSAL public client application.
    """
    authority = f"https://login.microsoftonline.com/{Settings.FABRIC_TENANT_ID}"
    return msal.PublicClientApplication(
        CLIENT_ID,
        authority=authority,
        token_cache=cache,
    )


def login() -> dict[str, str]:
    """Run device code flow for interactive user authentication.

    Prints the device code URL and user code to stderr (stdout reserved for MCP).
    Blocks until the user completes authentication in the browser.

    Returns:
        Dict with username and account_id.

    Raises:
        RuntimeError: If device code flow fails or tenant ID is not configured.
    """
    if not Settings.FABRIC_TENANT_ID:
        msg = "FABRIC_TENANT_ID must be set in .env for user authentication."
        raise RuntimeError(msg)

    cache = _build_cache()
    app = _build_app(cache)

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        msg = flow.get("error_description", "Failed to initiate device code flow")
        raise RuntimeError(msg)

    print(flow["message"], file=sys.stderr)

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        claims = result.get("id_token_claims", {})
        username = claims.get("preferred_username", claims.get("upn", "unknown"))
        return {"username": username, "account_id": result.get("account", {}).get("home_account_id", "")}

    msg = result.get("error_description", result.get("error", "Unknown authentication error"))
    raise RuntimeError(msg)


def logout() -> bool:
    """Remove cached user tokens.

    Returns:
        True if tokens were cleared, False if no cached tokens found.
    """
    cache = _build_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    for account in accounts:
        app.remove_account(account)

    cache_path = Path(CACHE_FILE)
    path_existed = cache_path.exists()
    if path_existed:
        cache_path.unlink()

    return bool(accounts) or path_existed


def get_user_token() -> str | None:
    """Acquire a user token silently from the persistent cache.

    This function NEVER prompts for interaction. If no cached token is
    available or the refresh token has expired, it returns None and
    DAX queries fall back to the service principal.

    Returns:
        Access token string, or None if unavailable.
    """
    try:
        cache = _build_cache()
        app = _build_app(cache)
        accounts = app.get_accounts()
        if not accounts:
            return None

        result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

        logger.warning("User token refresh failed. Run 'python -m powerbi_mcp login' to re-authenticate.")
        return None
    except Exception:
        logger.debug("User token acquisition failed", exc_info=True)
        return None


def get_auth_status() -> dict[str, Any]:
    """Return current authentication state for the status command.

    Returns:
        Dict with sp_configured, user_cached, username, cache_location, cache_encrypted.
    """
    sp_ok = Settings.has_service_principal()

    try:
        cache = _build_cache()
        app = _build_app(cache)
        accounts = app.get_accounts()
        encrypted = getattr(cache, "_is_encrypted", False)
    except Exception:
        accounts = []
        encrypted = False

    return {
        "sp_configured": sp_ok,
        "user_cached": len(accounts) > 0,
        "username": accounts[0]["username"] if accounts else None,
        "cache_location": CACHE_FILE,
        "cache_encrypted": encrypted,
    }
