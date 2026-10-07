"""Existing tunnel identity, credential handling, and logging boundaries."""

import json
import os

import pytest

from scripts.run_phase_a_release_tunnel import tunnel_settings


def configure(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    user_root = tmp_path / "user"
    config_dir = user_root / ".config/tunnel-client"
    config_dir.mkdir(parents=True)
    tunnel_id = "tunnel_" + "a" * 32
    (project / ".env").write_text(
        "AUTH0_DOMAIN=synthetic.auth.example\nAUTH0_CLIENT_ID=synthetic-client\n"
        "AUTH0_CLIENT_SECRET=synthetic-only\nAUTH0_SECRET=synthetic-only\n"
        "APP_BASE_URL=http://localhost:5000\n"
    )
    (project / ".env.poc").write_text(
        "CAREERGROUND_POC_ISSUER=https://synthetic.auth.example/\n"
        "CAREERGROUND_POC_RESOURCE_URL=https://public.synthetic.example/v1/mcp/" + tunnel_id + "\n"
    )
    config = config_dir / "careerground-dev-poc.yaml"
    config.write_text(
        "control_plane:\n  base_url: https://control.synthetic.example\n  tunnel_id: "
        + tunnel_id
        + "\n  api_key: env:CONTROL_PLANE_API_KEY\nlog:\n  http_raw_unsafe: true\n"
    )
    key = config_dir / "careerground-dev-poc.env"
    key.write_text("CONTROL_PLANE_API_KEY='synthetic private canary'\n")
    for path in (config, key):
        os.chmod(path, 0o600)
    return project, user_root, config, key


def test_existing_id_binding_works_with_distinct_control_and_resource_hosts(tmp_path):
    project, user_root, config, key = configure(tmp_path)
    before = (config.read_bytes(), key.read_bytes())
    command, env = tunnel_settings(project, user_root)
    assert env["CONTROL_PLANE_API_KEY"] == "synthetic private canary"
    assert "synthetic private canary" not in json.dumps(command)
    assert "--log.http-raw-unsafe=false" in command
    # An empty path streams to stdout; the literal "stdout" creates a file.
    assert command[command.index("--log.file") + 1] == ""
    assert "--allow-remote-ui=false" in command
    assert "--open-web-ui=false" in command
    assert "127.0.0.1:18081" in command
    assert "url=http://127.0.0.1:8001/mcp" in command
    assert before == (config.read_bytes(), key.read_bytes())


def test_a_different_tunnel_id_is_refused_without_modifying_configuration(tmp_path):
    project, user_root, config, key = configure(tmp_path)
    config.write_text(config.read_text().replace("tunnel_" + "a" * 32, "tunnel_" + "b" * 32))
    before = (config.read_bytes(), key.read_bytes())
    with pytest.raises(ValueError, match="binding required"):
        tunnel_settings(project, user_root)
    assert before == (config.read_bytes(), key.read_bytes())


def test_public_credential_file_is_refused(tmp_path):
    project, user_root, _config, key = configure(tmp_path)
    os.chmod(key, 0o644)
    with pytest.raises(ValueError, match="Owner-only"):
        tunnel_settings(project, user_root)


def test_credential_in_config_is_not_accepted_as_an_existing_env_reference(tmp_path):
    project, user_root, config, _key = configure(tmp_path)
    config.write_text(config.read_text().replace("env:CONTROL_PLANE_API_KEY", "synthetic-canary"))
    with pytest.raises(ValueError) as failure:
        tunnel_settings(project, user_root)
    assert "synthetic-canary" not in str(failure.value)
