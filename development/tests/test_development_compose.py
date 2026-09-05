import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPOSITORY_ROOT / ".config" / "docker-compose.yml"
DEVCONTAINER_FILE = REPOSITORY_ROOT / ".devcontainer" / "devcontainer.json"
DEV_ENV_FILE = REPOSITORY_ROOT / "development" / "dev-env.sh"
START_DEVELOPMENT_FILE = REPOSITORY_ROOT / ".devcontainer" / "start-development.sh"
SETUP_HOST_CLI_FILE = REPOSITORY_ROOT / ".devcontainer" / "setup-host-cli.sh"


def render_compose_config(tmp_path, env=None):
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")

    config_directory = tmp_path / ".config"
    config_directory.mkdir()
    shutil.copy2(COMPOSE_FILE, config_directory / "docker-compose.yml")
    if env is not None:
        (config_directory / ".env").write_text(
            "\n".join(
                (
                    *(f"{key}={value}" for key, value in env.items()),
                    "",
                )
            ),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            "docker",
            "compose",
            "--file",
            ".config/docker-compose.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_devcontainer_defaults_are_project_agnostic(tmp_path):
    config = render_compose_config(tmp_path)

    assert config["name"] == "frappe_development"
    assert config["services"]["frappe"]["environment"]["APPS_JSON"] == ""
    assert config["services"]["frappe"]["environment"]["SITES_JSON"] == ""
    assert "BENCH_NAME" not in config["services"]["frappe"]["environment"]
    assert config["services"]["frappe"]["environment"]["BACKUP_URL"] == ""
    assert config["services"]["frappe"]["environment"]["FRAPPE_API_TOKEN"] == ""
    assert "SITE_NAME" not in config["services"]["frappe"]["environment"]
    assert config["services"]["frappe"]["environment"]["SOURCE_SITE_URL"] == ""
    assert config["services"]["frappe"]["environment"]["SSH_AUTH_SOCK"] == (
        "/run/host-services/ssh-auth.sock"
    )
    mount_targets = {
        mount["target"] for mount in config["services"]["frappe"]["volumes"]
    }
    assert "/home/frappe/.ssh/config" in mount_targets
    assert "/home/frappe/.ssh/known_hosts" in mount_targets
    assert "/run/host-services/ssh-auth.sock" in mount_targets
    assert set(config["volumes"]) == {"mariadb-data"}


def test_devcontainer_preserves_compose_startup_command():
    config = json.loads(DEVCONTAINER_FILE.read_text(encoding="utf-8"))

    assert config["overrideCommand"] is False
    assert config["shutdownAction"] == "none"
    assert config["forwardPorts"] == [8000, 9000]
    assert config["postCreateCommand"] == (
        "bash /workspace/.devcontainer/watch-setup.sh"
    )
    assert config["waitFor"] == "postCreateCommand"
    assert "remoteEnv" not in config


def test_devcontainer_waits_for_manual_bench_start():
    startup = START_DEVELOPMENT_FILE.read_text(encoding="utf-8")
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "exec bench start" not in startup
    assert "exec sleep infinity" in startup
    assert 'touch "$setup_marker"' in startup
    assert 'set-admin-password "$ADMIN_PASSWORD"' in startup
    assert ".development-backup-restore" in startup
    assert "installer_args+=(--skip-app-install)" in startup
    assert "/tmp/frappe-bench-setup-complete" in compose


def test_backup_restore_uses_configured_bench_and_site():
    script = DEV_ENV_FILE.read_text(encoding="utf-8")

    assert "cd -- frappe-bench" in script
    assert '"$1" "$2"' in script
    assert "site_name=localhost" in script


def test_host_cli_bridge_does_not_override_bench_toolchain():
    startup = START_DEVELOPMENT_FILE.read_text(encoding="utf-8")
    host_cli_setup = SETUP_HOST_CLI_FILE.read_text(encoding="utf-8")

    assert (
        'export PATH="${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}:$PATH"'
        not in startup
    )
    assert (
        "shell_hook='export PATH=\"$PATH:${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}\"'"
        in host_cli_setup
    )


def test_devcontainer_env_is_loaded_from_compose_directory(tmp_path):
    config = render_compose_config(
        tmp_path,
        {
            "COMPOSE_PROJECT_NAME": "compose-env-test",
            "HTTP_PORT": "18080",
            "SOCKETIO_PORT": "19090",
            "APPS_JSON": "apps.json",
            "SITES_JSON": "sites.json",
            "FRAPPE_API_TOKEN": "key:secret",
        },
    )

    assert config["name"] == "compose-env-test"
    assert config["services"]["frappe"]["environment"]["APPS_JSON"] == "apps.json"
    assert config["services"]["frappe"]["environment"]["SITES_JSON"] == "sites.json"
    assert config["services"]["frappe"]["environment"]["FRAPPE_API_TOKEN"] == (
        "key:secret"
    )
    published_ports = {
        port["target"]: str(port["published"])
        for port in config["services"]["frappe"]["ports"]
    }
    assert published_ports == {8000: "18080", 9000: "19090"}
