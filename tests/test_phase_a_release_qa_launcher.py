"""Restart/data-loss and configuration boundaries of the persistent QA launcher."""

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_qa_launcher", Path(__file__).parents[1] / "scripts/run_phase_a_release_qa.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def configure(project):
    (project / ".env").write_text(
        "AUTH0_DOMAIN=synthetic.auth.example\n"
        "AUTH0_CLIENT_ID=synthetic-client\n"
        "AUTH0_CLIENT_SECRET='synthetic secret with spaces'\n"
        "AUTH0_SECRET=synthetic-only\n"
        "APP_BASE_URL=http://localhost:5000\n"
        "DO_NOT_COPY_FROM_DOTENV=private-canary\n"
        "OPENAI_API_KEY=synthetic-unused\n"
        "CAREERGROUND_DATABASE_URL=production-canary\n"
    )
    (project / ".env.poc").write_text(
        "CAREERGROUND_POC_ISSUER=https://synthetic.auth.example/\n"
        "CAREERGROUND_POC_RESOURCE_URL=https://synthetic.mcp.example/mcp\n"
    )


def complete_pair(base):
    for name in ("state", "passkeys"):
        (base / name).mkdir(mode=0o700)
    database = base / "state/authenticated.sqlite"
    database.touch(mode=0o600)


def test_environment_is_bound_to_files_and_cannot_import_paid_or_database_configuration(tmp_path):
    configure(tmp_path)
    env = launcher.load_environment(
        tmp_path,
        {
            "PATH": "/synthetic",
            "AUTH0_DOMAIN": "other-shell.example",
            "CAREERGROUND_DATABASE_URL": "x",
        },
    )
    assert env["AUTH0_DOMAIN"] == "synthetic.auth.example"
    assert env["AUTH0_CLIENT_SECRET"] == "synthetic secret with spaces"
    assert env["PATH"] == "/synthetic"
    assert "DO_NOT_COPY_FROM_DOTENV" not in env
    assert "OPENAI_API_KEY" not in env
    assert "CAREERGROUND_DATABASE_URL" not in env


def test_nonlocal_origin_is_rejected_without_disclosing_config(tmp_path):
    configure(tmp_path)
    path = tmp_path / ".env"
    path.write_text(path.read_text().replace("http://localhost:5000", "https://production.example"))
    with pytest.raises(ValueError) as failure:
        launcher.load_environment(tmp_path, {})
    assert "production.example" not in str(failure.value)
    assert "synthetic secret" not in str(failure.value)


def test_initialize_once_and_restart_preserve_marker_and_create_no_database(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    before = (base / "qa.json").read_bytes()
    assert stat.S_IMODE(base.stat().st_mode) == 0o700
    assert stat.S_IMODE((base / "qa.json").stat().st_mode) == 0o600
    assert launcher.prepare(tmp_path, "trial") == base
    with pytest.raises(ValueError):
        launcher.prepare(tmp_path, "trial", initialize=True)
    assert (base / "qa.json").read_bytes() == before
    assert not (base / "state").exists()
    command = launcher.runtime_command(base)
    assert "--initialize-development-passkeys" in command
    assert "--require-development-deletion-mfa" not in command
    assert "--allow-development-retention" not in command


def test_missing_initialized_data_cannot_silently_create_a_new_store(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    launcher.write_marker(base, True)
    before = (base / "qa.json").read_bytes()
    with pytest.raises(ValueError, match="never recreate"):
        launcher.prepare(tmp_path, "trial")
    assert not (base / "state").exists()
    assert (base / "qa.json").read_bytes() == before


def test_partial_startup_is_preserved_and_not_auto_repaired(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    (base / "state").mkdir(mode=0o700)
    (base / "state/retained-canary").write_text("retained")
    with pytest.raises(ValueError, match="Incomplete QA"):
        launcher.prepare(tmp_path, "trial")
    assert (base / "state/retained-canary").read_text() == "retained"
    assert not (base / "passkeys").exists()


def test_symlink_project_is_rejected_before_writing_to_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        launcher.prepare(link, "trial", initialize=True)
    assert list(target.iterdir()) == []


def test_existing_passkeys_and_denials_are_reused_even_without_enable_flag(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    complete_pair(base)
    launcher.prepare(tmp_path, "trial")
    assert json.loads((base / "qa.json").read_text())["runtime_initialized"]
    denials = base / "connection-denials"
    denials.mkdir(mode=0o700)
    client = base / "observed-client.txt"
    client.write_text("synthetic-verified-client")
    os.chmod(client, 0o600)
    command = launcher.runtime_command(base)
    assert "--development-connection-denials-dir" in command
    assert "synthetic-verified-client" in command
    assert "--initialize-development-passkeys" not in command
    assert "--initialize-development-connection-denials" not in command
    client.unlink()
    with pytest.raises(FileNotFoundError):
        launcher.runtime_command(base)


def test_enabling_connections_requires_private_observed_client_and_no_registry_creation(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    with pytest.raises(FileNotFoundError):
        launcher.runtime_command(base, enable_connections=True)
    assert not (base / "connection-denials").exists()
    client = base / "observed-client.txt"
    client.write_text("synthetic-verified-client")
    os.chmod(client, 0o644)
    with pytest.raises(ValueError, match="Owner-only"):
        launcher.runtime_command(base, enable_connections=True)


def test_existing_marker_symlink_cannot_be_used_for_restart(tmp_path):
    base = launcher.prepare(tmp_path, "trial", initialize=True)
    marker = base / "qa.json"
    other = tmp_path / "other.json"
    other.write_bytes(marker.read_bytes())
    marker.unlink()
    marker.symlink_to(other)
    with pytest.raises(ValueError, match="Symlink"):
        launcher.prepare(tmp_path, "trial")
