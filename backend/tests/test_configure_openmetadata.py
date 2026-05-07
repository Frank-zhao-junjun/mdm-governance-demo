from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.configure_openmetadata import extract_token, normalize_host, write_env_values


def test_normalize_host_accepts_ui_and_api_urls():
    assert normalize_host("http://localhost:8585") == "http://localhost:8585/api"
    assert normalize_host("http://localhost:8585/api/") == "http://localhost:8585/api"


def test_extract_token_finds_nested_common_keys():
    assert extract_token({"accessToken": "abc"}) == "abc"
    assert extract_token({"data": {"jwtToken": "nested"}}) == "nested"
    assert extract_token({"data": [{"token": "list-token"}]}) == "list-token"


def test_write_env_values_preserves_and_updates(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SQLALCHEMY_DATABASE_URL=sqlite:///./old.db\nOM_ENABLED=false\n", encoding="utf-8")

    write_env_values(env_file, {
        "OM_ENABLED": "true",
        "OPENMETADATA_HOST": "http://localhost:8585/api",
        "OPENMETADATA_TOKEN": "secret-token",
    })

    content = env_file.read_text(encoding="utf-8")
    assert "SQLALCHEMY_DATABASE_URL=sqlite:///./old.db" in content
    assert "OM_ENABLED=true" in content
    assert "OPENMETADATA_HOST=http://localhost:8585/api" in content
    assert "OPENMETADATA_TOKEN=secret-token" in content