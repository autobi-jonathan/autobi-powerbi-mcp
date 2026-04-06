"""Configuration for Fabric API authentication."""

from __future__ import annotations

import logging
import os
import subprocess

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    """Fabric API settings loaded from environment variables."""

    FABRIC_TENANT_ID: str = os.getenv("FABRIC_TENANT_ID", "")
    FABRIC_CLIENT_ID: str = os.getenv("FABRIC_CLIENT_ID", "")
    FABRIC_CLIENT_SECRET: str = os.getenv("FABRIC_CLIENT_SECRET", "")
    FABRIC_DEFAULT_WORKSPACE_ID: str = os.getenv("FABRIC_DEFAULT_WORKSPACE_ID", "")

    @classmethod
    def has_service_principal(cls) -> bool:
        """Check if service principal credentials are configured."""
        return bool(cls.FABRIC_TENANT_ID and cls.FABRIC_CLIENT_ID and cls.FABRIC_CLIENT_SECRET)

    @classmethod
    def get_access_token(cls) -> str:
        """Get a Fabric API access token via service principal or Azure CLI fallback.

        Returns:
            Bearer token string for Fabric REST API.

        Raises:
            RuntimeError: If no authentication method succeeds.
        """
        if cls.has_service_principal():
            return cls._get_token_service_principal()
        return cls._get_token_azure_cli()

    @classmethod
    def _get_token_service_principal(cls) -> str:
        """Authenticate via service principal using azure-identity."""
        from azure.identity import ClientSecretCredential

        credential = ClientSecretCredential(
            tenant_id=cls.FABRIC_TENANT_ID,
            client_id=cls.FABRIC_CLIENT_ID,
            client_secret=cls.FABRIC_CLIENT_SECRET,
        )
        token = credential.get_token("https://api.fabric.microsoft.com/.default")
        return token.token

    @classmethod
    def _get_token_azure_cli(cls) -> str:
        """Authenticate via Azure CLI (interactive fallback)."""
        try:
            result = subprocess.run(
                ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com", "--query", "accessToken", "-o", "tsv"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            msg = f"Azure CLI authentication failed: {e}. Run 'az login' or configure service principal in .env."
            raise RuntimeError(msg) from e
