"""Entry point for: python -m powerbi_mcp [command]."""

from __future__ import annotations

import sys


def main() -> None:
    """Dispatch CLI commands."""
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if command == "serve":
        from powerbi_mcp.server import mcp

        mcp.run()
    elif command == "login":
        _cmd_login()
    elif command == "logout":
        _cmd_logout()
    elif command == "status":
        _cmd_status()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Usage: python -m powerbi_mcp [serve|login|logout|status]", file=sys.stderr)
        sys.exit(1)


def _cmd_login() -> None:
    """Run device code flow for user authentication."""
    from powerbi_mcp.config.auth import login

    try:
        result = login()
        print(f"Logged in as: {result['username']}")
        print("User token cached. DAX queries will now use your identity.")
    except RuntimeError as e:
        print(f"Login failed: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_logout() -> None:
    """Clear cached user tokens."""
    from powerbi_mcp.config.auth import logout

    if logout():
        print("User tokens cleared. DAX queries will fall back to service principal.")
    else:
        print("No cached tokens found.")


def _cmd_status() -> None:
    """Show current authentication state."""
    from powerbi_mcp.config.auth import get_auth_status

    status = get_auth_status()
    print("Power BI MCP Authentication Status")
    print("=" * 40)
    print(f"  Service Principal: {'Configured' if status['sp_configured'] else 'Not configured'}")
    print(f"  User Token Cached: {'Yes' if status['user_cached'] else 'No'}")
    if status.get("username"):
        print(f"  Username: {status['username']}")
    print(f"  Cache Location: {status['cache_location']}")
    print(f"  Cache Encrypted: {'Yes (DPAPI)' if status['cache_encrypted'] else 'No'}")


main()
