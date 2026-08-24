import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from development import installer


def parse_args(*args: str):
    return installer.get_args_parser().parse_args(args)


def make_bench(tmp_path: Path, *apps: str) -> Path:
    bench_dir = tmp_path / "frappe-bench"
    apps_dir = bench_dir / "apps"
    apps_dir.mkdir(parents=True)
    for app in apps:
        (apps_dir / app).mkdir()
    (bench_dir / "env" / "bin").mkdir(parents=True)
    (bench_dir / "env" / "bin" / "python").touch()
    (bench_dir / "sites").mkdir()
    (bench_dir / "sites" / "apps.txt").touch()
    (bench_dir / "sites" / "common_site_config.json").write_text("{}")
    (bench_dir / "Procfile").write_text("web: bench serve --port 8005\n")
    return bench_dir


def test_parser_rejects_unknown_database():
    with pytest.raises(SystemExit):
        parse_args("--db-type", "sqlite")


def test_parser_defaults_to_frappe_only():
    args = parse_args()

    assert args.frappe_branch == "version-16"
    assert args.apps_json is None
    assert args.db_name is None
    assert args.db_password is None


def test_parser_rejects_a_custom_bench_name():
    with pytest.raises(SystemExit):
        parse_args("--bench-name", "other-bench")


def test_parser_rejects_a_custom_site_name():
    with pytest.raises(SystemExit):
        parse_args("--site-name", "other.localhost")


def test_existing_bench_is_reconfigured_without_initialization(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.init_bench_if_not_exist(parse_args())

    assert len(calls) == 7
    assert all(call[0][0][0:2] == ["bench", "set-config"] for call in calls)
    assert calls[4][0][0][-2:] == ["webserver_port", "8000"]
    assert calls[5][0][0][-2:] == ["socketio_port", "9000"]
    assert (bench_dir / "Procfile").read_text() == "web: bench serve --port 8000\n"


def test_incomplete_existing_bench_fails_clearly(tmp_path, monkeypatch):
    bench_dir = tmp_path / "frappe-bench"
    (bench_dir / "apps" / "frappe").mkdir(parents=True)
    (bench_dir / "sites").mkdir()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="incomplete Bench directory") as error:
        installer.init_bench_if_not_exist(parse_args())

    assert "env/bin/python" in str(error.value)
    assert "sites/apps.txt" in str(error.value)
    assert "Move it aside" in str(error.value)


def test_bench_init_quotes_user_supplied_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, "_set_procfile_web_port", lambda *args: None)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    args = parse_args(
        "--node-version",
        "20; echo unsafe",
        "--frappe-branch",
        "branch name",
    )

    installer.init_bench_if_not_exist(args)

    init_command = calls[0][0][0]
    assert init_command[:3] == ["/bin/bash", "-i", "-c"]
    assert shlex.split(init_command[3]) == [
        "nvm",
        "use",
        "20; echo unsafe",
        "&&",
        "bench",
        "init",
        "--skip-redis-config-generation",
        "--frappe-path=https://github.com/frappe/frappe",
        "--frappe-branch=branch name",
        "frappe-bench",
    ]
    assert all(call[1]["check"] is True for call in calls)
    assert calls[0][1]["env"]["FRAPPE_DOCKER_BUILD"] == "1"


def test_bench_init_accepts_optional_apps_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, "_set_procfile_web_port", lambda *args: None)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.init_bench_if_not_exist(
        parse_args("--apps-json", "custom apps.json")
    )

    init_command = shlex.split(calls[0][0][0][3])
    assert "--apps_path=custom apps.json" in init_command


def test_create_mariadb_site_with_sorted_apps(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "payments", "erpnext")
    (bench_dir / "apps" / "README.txt").write_text("not an app")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args())

    assert calls[0][0][0] == [
        "bench",
        "set-config",
        "-g",
        "db_host",
        "mariadb",
    ]
    assert calls[1][0][0] == [
        "bench",
        "new-site",
        "--set-default",
        "--force",
        "--no-mariadb-socket",
        "--db-host=mariadb",
        "--db-type=mariadb",
        "--db-root-username=root",
        "--db-root-password=123",
        "--admin-password=admin",
        "--install-app=erpnext",
        "--install-app=payments",
        "localhost",
    ]
    assert all(
        call[1] == {"cwd": bench_dir, "env": None, "check": True} for call in calls
    )


def test_create_site_preserves_app_manifest_dependency_order(tmp_path, monkeypatch):
    make_bench(tmp_path, "frappe", "srv_erp", "erpnext", "demo_erpnext")
    manifest = tmp_path / "apps.json"
    manifest.write_text(
        """[
          {"url": "https://github.com/frappe/erpnext.git"},
          {"url": "git@github.com:example/demo-erpnext.git"},
          {"url": "git@github.com:example/srv-erp.git"}
        ]"""
    )
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--apps-json", str(manifest)))

    install_options = [
        argument
        for argument in calls[1][0][0]
        if argument.startswith("--install-app=")
    ]
    assert install_options == [
        "--install-app=erpnext",
        "--install-app=demo_erpnext",
        "--install-app=srv_erp",
    ]


def test_backup_site_creation_skips_manifest_apps(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext", "srv_erp")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--skip-app-install"))

    command = calls[1][0][0]
    assert command[-1] == "localhost"
    assert not any(argument.startswith("--install-app=") for argument in command)
    assert calls[1][1]["cwd"] == bench_dir


def test_create_mariadb_site_accepts_explicit_database_credentials(
    tmp_path, monkeypatch
):
    bench_dir = make_bench(tmp_path, "frappe")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(
        parse_args("--db-name", "custom_db", "--db-password", "custom_password")
    )

    command = calls[1][0][0]
    assert "--db-name=custom_db" in command
    assert "--db-password=custom_password" in command
    assert calls[1][1]["cwd"] == bench_dir


def test_create_postgres_site_uses_postgres_credentials(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--db-type", "postgres"))

    command = calls[1][0][0]
    assert calls[0][0][0][-1] == "postgresql"
    assert "--db-host=postgresql" in command
    assert "--set-default" in command
    assert "--db-root-username=postgres" in command
    assert "--force" not in command
    assert not any(arg.startswith("--db-name=") for arg in command)
    assert command[-1] == "localhost"
    assert calls[1][1]["cwd"] == bench_dir


def test_existing_site_is_preserved(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext")
    site_dir = bench_dir / "sites" / "localhost"
    site_dir.mkdir(parents=True)
    (site_dir / "site_config.json").write_text("{}")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args())

    assert len(calls) == 2
    assert calls[0][0][0] == [
        "bench",
        "set-config",
        "-g",
        "db_host",
        "mariadb",
    ]
    assert calls[1][0][0] == ["bench", "use", "localhost"]


def test_subprocess_failures_are_reported_without_secrets(monkeypatch, capsys):
    error = subprocess.CalledProcessError(
        7,
        [
            "bench",
            "new-site",
            "--db-root-password=database-secret",
            "--admin-password",
            "admin-secret",
        ],
    )
    parsed_args = parse_args()
    parser = SimpleNamespace(parse_args=lambda: parsed_args)
    monkeypatch.setattr(installer, "get_args_parser", lambda: parser)
    monkeypatch.setattr(installer, "init_bench_if_not_exist", lambda args: None)

    def fail_to_create_site(args):
        raise error

    monkeypatch.setattr(installer, "create_site_in_bench", fail_to_create_site)

    assert installer.main() == 7
    output = capsys.readouterr().out
    assert "database-secret" not in output
    assert "admin-secret" not in output
    assert "'--db-root-password=***'" in output
    assert "--admin-password '***'" in output


def test_invalid_bench_error_is_reported(monkeypatch, capsys):
    parsed_args = parse_args()
    parser = SimpleNamespace(parse_args=lambda: parsed_args)
    monkeypatch.setattr(installer, "get_args_parser", lambda: parser)

    def fail_to_initialize(args):
        raise RuntimeError("invalid bench")

    monkeypatch.setattr(installer, "init_bench_if_not_exist", fail_to_initialize)

    assert installer.main() == 1
    assert "invalid bench" in capsys.readouterr().out
