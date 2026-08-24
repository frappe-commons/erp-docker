import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPOSITORY_ROOT / ".devcontainer" / "docker-compose.yml"
DEVCONTAINER_FILE = REPOSITORY_ROOT / ".devcontainer" / "devcontainer.json"


def render_compose_config(tmp_path, env=None):
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")

    devcontainer = tmp_path / ".devcontainer"
    devcontainer.mkdir()
    shutil.copy2(COMPOSE_FILE, devcontainer / "docker-compose.yml")
    if env is not None:
        (devcontainer / ".env").write_text(
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
            ".devcontainer/docker-compose.yml",
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
    assert config["services"]["frappe"]["environment"]["SITE_NAME"] == (
        "development.localhost"
    )
    assert set(config["volumes"]) == {"mariadb-data"}


def test_devcontainer_preserves_compose_startup_command():
    config = json.loads(DEVCONTAINER_FILE.read_text(encoding="utf-8"))

    assert config["overrideCommand"] is False
    assert config["forwardPorts"] == [8000, 9000]
    assert "postCreateCommand" not in config
    assert "remoteEnv" not in config


def test_devcontainer_env_is_loaded_from_compose_directory(tmp_path):
    config = render_compose_config(
        tmp_path,
        {
            "COMPOSE_PROJECT_NAME": "compose-env-test",
            "HTTP_PORT": "18080",
            "SOCKETIO_PORT": "19090",
            "SITE_NAME": "compose-test.localhost",
            "APPS_JSON": "apps.json",
        },
    )

    assert config["name"] == "compose-env-test"
    assert config["services"]["frappe"]["environment"]["SITE_NAME"] == (
        "compose-test.localhost"
    )
    assert config["services"]["frappe"]["environment"]["APPS_JSON"] == "apps.json"
    published_ports = {
        port["target"]: str(port["published"])
        for port in config["services"]["frappe"]["ports"]
    }
    assert published_ports == {8000: "18080", 9000: "19090"}
