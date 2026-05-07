"""Configure OpenMetadata connection settings for the local backend.

Examples:
    python tools/configure_openmetadata.py --host http://localhost:8585 --token <jwt> --save-env
    python tools/configure_openmetadata.py --host http://localhost:8585 --email admin@example.com --password-stdin --save-env
"""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests


DEFAULT_HOST = "http://localhost:8585/api"
TOKEN_KEYS = ("accessToken", "jwtToken", "token", "id_token", "access_token")


def normalize_host(host: str) -> str:
    """Normalize OpenMetadata UI/API URL to the API base URL."""
    cleaned = host.strip().rstrip("/")
    return cleaned if cleaned.endswith("/api") else f"{cleaned}/api"


def build_url(host: str, endpoint: str) -> str:
    """Build a full OpenMetadata API URL from a normalized or raw host."""
    return f"{normalize_host(host)}{endpoint if endpoint.startswith('/') else f'/{endpoint}'}"


def extract_token(payload: Any) -> Optional[str]:
    """Find a token in common OpenMetadata login response shapes."""
    if isinstance(payload, dict):
        for key in TOKEN_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            token = extract_token(value)
            if token:
                return token
    if isinstance(payload, list):
        for value in payload:
            token = extract_token(value)
            if token:
                return token
    return None


def request_token(host: str, email: str, password: str, timeout: int = 10) -> str:
    """Try common OpenMetadata login endpoints and return a JWT/access token."""
    attempts = (
        ("/v1/users/login", {"email": email, "password": password}),
        ("/v1/users/login", {"username": email, "password": password}),
        ("/v1/auth/login", {"email": email, "password": password}),
        ("/v1/auth/login", {"username": email, "password": password}),
    )
    errors = []
    for endpoint, payload in attempts:
        url = build_url(host, endpoint)
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            if response.status_code >= 400:
                errors.append(f"{endpoint}: HTTP {response.status_code}")
                continue
            token = extract_token(response.json())
            if token:
                return token
            errors.append(f"{endpoint}: token not found in response")
        except requests.RequestException as exc:
            errors.append(f"{endpoint}: {exc}")
        except ValueError:
            errors.append(f"{endpoint}: response is not JSON")
    raise RuntimeError("Unable to obtain OpenMetadata token. " + "; ".join(errors))


def verify_connection(host: str, token: Optional[str], timeout: int = 10) -> Dict[str, Any]:
    """Verify OpenMetadata is reachable and, when provided, token is usable."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    health = requests.get(build_url(host, "/v1/health-check"), headers=headers, timeout=timeout)
    health.raise_for_status()

    if token:
        auth_errors = []
        for endpoint in ("/v1/users/loggedInUser", "/v1/users?limit=1"):
            try:
                response = requests.get(build_url(host, endpoint), headers=headers, timeout=timeout)
                if response.status_code in (401, 403):
                    auth_errors.append(f"{endpoint}: HTTP {response.status_code}")
                    continue
                response.raise_for_status()
                return {"status": "connected", "auth": "verified", "health": health.json() if health.content else {}}
            except requests.RequestException as exc:
                auth_errors.append(f"{endpoint}: {exc}")
        raise RuntimeError("OpenMetadata is healthy, but token verification failed. " + "; ".join(auth_errors))

    return {"status": "connected", "auth": "not_checked", "health": health.json() if health.content else {}}


def read_env_lines(env_file: Path) -> list[str]:
    return env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []


def write_env_values(env_file: Path, values: Dict[str, str]) -> None:
    """Update or append dotenv values while preserving unrelated lines."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    lines = read_env_lines(env_file)
    seen = set()
    updated = []

    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in values:
            updated.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            updated.append(line)

    if updated and updated[-1] != "":
        updated.append("")
    for key, value in values.items():
        if key not in seen:
            updated.append(f"{key}={value}")

    env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")


def mask_token(token: str) -> str:
    if len(token) <= 12:
        return "***"
    return f"{token[:6]}...{token[-6:]}"


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure OpenMetadata for RalphLoop backend.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="OpenMetadata UI or API URL. Default: http://localhost:8585/api")
    parser.add_argument("--token", help="Existing OpenMetadata JWT/API token.")
    parser.add_argument("--email", help="OpenMetadata user email/username for token login fallback.")
    parser.add_argument("--password", help="OpenMetadata password. Prefer --password-stdin or interactive prompt.")
    parser.add_argument("--password-stdin", action="store_true", help="Prompt for password without echoing it.")
    parser.add_argument("--save-env", action="store_true", help="Write OM_ENABLED, OPENMETADATA_HOST, and OPENMETADATA_TOKEN to .env.")
    parser.add_argument("--env-file", default=".env", help="Dotenv file path relative to current directory or absolute path.")
    parser.add_argument("--skip-verify", action="store_true", help="Save configuration without calling OpenMetadata.")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    host = normalize_host(args.host)
    token = args.token

    if not token and args.email:
        password = args.password
        if args.password_stdin:
            password = getpass.getpass("OpenMetadata password: ")
        if not password:
            raise SystemExit("Password is required when --email is used without --token.")
        token = request_token(host, args.email, password)

    if not token:
        raise SystemExit("Provide --token, or provide --email with --password/--password-stdin to obtain one.")

    if not args.skip_verify:
        result = verify_connection(host, token)
        print(f"OpenMetadata {result['status']}; token {result['auth']}.")

    if args.save_env:
        env_file = Path(args.env_file).resolve()
        write_env_values(env_file, {
            "OM_ENABLED": "true",
            "OPENMETADATA_HOST": host,
            "OPENMETADATA_TOKEN": token,
        })
        print(f"Saved OpenMetadata configuration to {env_file}")

    print(f"Host: {host}")
    print(f"Token: {mask_token(token)}")
    print("Restart the FastAPI backend for changes to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())