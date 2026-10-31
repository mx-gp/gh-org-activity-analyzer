import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

GITHUB_API_URL = "https://api.github.com"


class GitHubAuthManager:
    """Multi-source GitHub Authentication Provider:

    1. GitHub App (App ID + Private Key .pem + Installation ID)
    2. GitHub CLI ('gh auth token')
    3. Personal Access Token (PAT) via environment variable or direct input
    """

    @staticmethod
    def get_gh_cli_token() -> Optional[str]:
        """Detect and extract active token from GitHub CLI if installed and authenticated."""
        if not shutil.which("gh"):
            return None
        try:
            res = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            token = res.stdout.strip()
            if res.returncode == 0 and token and not token.startswith("error"):
                return token
        except Exception:
            pass
        return None

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @classmethod
    def generate_jwt(cls, app_id: str, private_key_pem: str) -> str:
        """Create a signed JWT for GitHub App authentication using openssl CLI."""
        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),  # 10 minutes maximum allowed by GitHub
            "iss": str(app_id),
        }

        header_b64 = cls._b64url_encode(json.dumps(header).encode("utf-8"))
        payload_b64 = cls._b64url_encode(json.dumps(payload).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

        # Sign using openssl CLI
        with tempfile.NamedTemporaryFile("w+", delete=False) as key_file:
            key_file.write(private_key_pem.strip() + "\n")
            key_path = key_file.name

        try:
            proc = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", key_path],
                input=signing_input,
                capture_output=True,
                check=True,
            )
            signature = proc.stdout
            sig_b64 = cls._b64url_encode(signature)
            return f"{header_b64}.{payload_b64}.{sig_b64}"
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)

    @classmethod
    def get_app_installation_token(
        cls, app_id: str, private_key_pem: str, installation_id: str
    ) -> str:
        """Exchange GitHub App JWT for a repository/organization installation access token."""
        jwt_token = cls.generate_jwt(app_id, private_key_pem)
        url = f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "gh-org-activity-analyzer",
            },
            method="POST",
            data=b"{}",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["token"]
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub App Token Exchange Failed ({e.code}): {err}")

    @classmethod
    def resolve_token(
        cls,
        token_input: Optional[str] = None,
        app_id: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Resolves authentication token with precedence:

        1. GitHub App (if app_id, private_key_pem, installation_id provided)
        2. Direct token input from user
        3. Environment variable GITHUB_TOKEN
        4. GitHub CLI ('gh auth token')
        Returns: (token, auth_method_name, metadata)
        """
        # 1. GitHub App
        if app_id and private_key_pem and installation_id:
            inst_token = cls.get_app_installation_token(app_id, private_key_pem, installation_id)
            return inst_token, "GitHub App", {
                "app_id": app_id,
                "installation_id": installation_id,
                "type": "App Installation Token"
            }

        # 2. Direct PAT token input
        if token_input and token_input.strip():
            return token_input.strip(), "Personal Access Token (User Input)", {
                "masked": f"{token_input[:4]}...{token_input[-4:]}" if len(token_input) > 8 else "***"
            }

        # 3. Environment Variable
        env_token = os.environ.get("GITHUB_TOKEN")
        if env_token and env_token.strip():
            return env_token.strip(), "Environment Variable (GITHUB_TOKEN)", {
                "masked": f"{env_token[:4]}...{env_token[-4:]}" if len(env_token) > 8 else "***"
            }

        # 4. GitHub CLI
        gh_token = cls.get_gh_cli_token()
        if gh_token:
            return gh_token, "GitHub CLI (gh auth)", {
                "cli": "gh",
                "masked": f"{gh_token[:4]}...{gh_token[-4:]}" if len(gh_token) > 8 else "***"
            }

        raise ValueError(
            "No authentication found. Provide a token, configure GitHub App credentials, or authenticate with `gh auth login`."
        )

    @classmethod
    def detect_available_methods(cls) -> Dict[str, Any]:
        """Detect which authentication methods are currently available in the environment."""
        gh_cli_available = False
        gh_cli_token = cls.get_gh_cli_token()
        if gh_cli_token:
            gh_cli_available = True

        env_available = bool(os.environ.get("GITHUB_TOKEN"))

        return {
            "github_cli": {
                "installed": bool(shutil.which("gh")),
                "authenticated": gh_cli_available,
            },
            "environment_token": env_available,
            "github_app_supported": bool(shutil.which("openssl")),
        }
