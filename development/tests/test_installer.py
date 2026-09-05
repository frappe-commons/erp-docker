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
    assert args.admin_password == "1212"
    assert args.apps_json is None
    assert args.sites_json is None
    assert args.db_name is None
    assert args.db_password is None


def test_parser_rejects_a_custom_bench_name():
    with pytest.raises(SystemExit):
        parse_args("--bench-name", "other-bench")


def test_parser_rejects_a_custom_site_name():
    with pytest.raises(SystemExit):
        parse_args("--site-name", "other.localhost")


def test_site_manifest_defines_multiple_isolated_sites(tmp_path):
    manifest = tmp_path / "sites.json"
    manifest.write_text("""[
          {"name": "client-one.localhost", "apps": ["erpnext", "client_one"],
           "set_default": true},
          {"name": "client-two.localhost", "apps": ["erpnext", "client_two"],
           "set_default": false}
        ]""")

    specs = installer.load_site_specs(parse_args("--sites-json", str(manifest)))

    assert [spec["name"] for spec in specs] == [
        "client-one.localhost",
        "client-two.localhost",
    ]
    assert specs[0]["apps"] == ["erpnext", "client_one"]
    assert specs[0]["set_default"] is True
    assert specs[0]["restore"] is False
    assert all(spec["reconcile_apps"] is True for spec in specs)


@pytest.mark.parametrize(
    "content, message",
    [
        ("[]", "at least one site"),
        (
            '[{"name":"same.localhost","apps":[],"set_default":true},'
            '{"name":"same.localhost","apps":[],"set_default":false}]',
            "duplicate site name",
        ),
        (
            '[{"name":"one.localhost","apps":[],"set_default":true},'
            '{"name":"two.localhost","apps":[],"set_default":true}]',
            "exactly one default site",
        ),
    ],
)
def test_site_manifest_rejects_unsafe_layouts(tmp_path, content, message):
    manifest = tmp_path / "sites.json"
    manifest.write_text(content)

    with pytest.raises(RuntimeError, match=message):
        installer.load_site_specs(parse_args("--sites-json", str(manifest)))


def test_multi_site_rejects_one_shared_explicit_database(tmp_path):
    manifest = tmp_path / "sites.json"
    manifest.write_text('[{"name":"one.localhost","apps":[],"set_default":true}]')

    with pytest.raises(RuntimeError, match="separate database and user per site"):
        installer.load_site_specs(
            parse_args(
                "--sites-json",
                str(manifest),
                "--db-name",
                "shared_database",
            )
        )


def test_app_source_preflight_checks_configured_branch(tmp_path, monkeypatch):
    manifest = tmp_path / "apps.json"
    manifest.write_text(
        '[{"url": "git@github.com:example/private-app.git", ' '"branch": "version-15"}]'
    )
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: (
            calls.append((args, kwargs)) or SimpleNamespace(returncode=0)
        ),
    )

    installer.validate_app_sources(str(manifest))

    assert calls[0][0][0] == [
        "git",
        "ls-remote",
        "--exit-code",
        "git@github.com:example/private-app.git",
        "refs/heads/version-15",
        "refs/tags/version-15",
        "refs/tags/version-15^{}",
    ]
    assert calls[0][1]["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert calls[0][1]["stdin"] is subprocess.DEVNULL


def test_app_source_preflight_fails_before_setup(tmp_path, monkeypatch):
    manifest = tmp_path / "apps.json"
    manifest.write_text(
        '[{"url": "git@github.com:example/private-app.git", ' '"branch": "missing"}]'
    )
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2),
    )

    with pytest.raises(RuntimeError, match="branch or tag 'missing' does not exist"):
        installer.validate_app_sources(str(manifest))


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

    installer.init_bench_if_not_exist(parse_args("--apps-json", "custom apps.json"))

    init_command = shlex.split(calls[0][0][0][3])
    assert "--apps_path=custom apps.json" in init_command


def test_existing_bench_adds_apps_newly_added_to_manifest(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext")
    manifest = tmp_path / "apps.json"
    manifest.write_text("""[
          {"url": "https://github.com/frappe/erpnext.git", "branch": "version-15"},
          {"url": "git@github.com:example/client-app.git", "branch": "version-15"}
        ]""")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.sync_manifest_apps(parse_args("--apps-json", str(manifest)))

    assert len(calls) == 1
    assert calls[0][0][0] == [
        "bench",
        "get-app",
        "--branch",
        "version-15",
        "git@github.com:example/client-app.git",
    ]
    assert calls[0][1]["cwd"] == bench_dir


def test_app_git_remotes_expose_all_origin_branches(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=source, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=source, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source, check=True)
    (source / "README.md").write_text("main\n")
    subprocess.run(["git", "add", "README.md"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=source, check=True)
    subprocess.run(["git", "branch", "feature"], cwd=source, check=True)

    bench_dir = tmp_path / "frappe-bench"
    apps_dir = bench_dir / "apps"
    apps_dir.mkdir(parents=True)
    subprocess.run(
        [
            "git",
            "clone",
            "--single-branch",
            "--branch=main",
            "--origin=upstream",
            str(source),
            str(apps_dir / "demo"),
        ],
        check=True,
    )
    monkeypatch.chdir(tmp_path)

    installer.configure_app_git_remotes(parse_args())

    app_dir = apps_dir / "demo"
    assert set(
        subprocess.run(
            ["git", "remote"], cwd=app_dir, check=True, capture_output=True, text=True
        ).stdout.splitlines()
    ) == {"origin", "upstream"}
    assert (
        subprocess.run(
            ["git", "config", "--get-all", "remote.origin.fetch"],
            cwd=app_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "+refs/heads/*:refs/remotes/origin/*"
    )
    remote_branches = subprocess.run(
        ["git", "branch", "--remotes"],
        cwd=app_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "origin/feature" in remote_branches


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
        "--admin-password=1212",
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
    manifest.write_text("""[
          {"url": "https://github.com/frappe/erpnext.git"},
          {"url": "git@github.com:example/demo-erpnext.git"},
          {"url": "git@github.com:example/srv-erp.git"}
        ]""")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--apps-json", str(manifest)))

    install_options = [
        argument for argument in calls[1][0][0] if argument.startswith("--install-app=")
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

    assert len(calls) == 3
    assert calls[0][0][0] == [
        "bench",
        "set-config",
        "-g",
        "db_host",
        "mariadb",
    ]
    assert calls[1][0][0] == ["bench", "use", "localhost"]
    assert calls[2][0][0] == [
        "bench",
        "--site",
        "localhost",
        "set-admin-password",
        "1212",
    ]


def test_multi_site_creates_separate_sites_with_selected_apps(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext", "client_one", "client_two")
    manifest = tmp_path / "sites.json"
    manifest.write_text("""[
          {"name": "client-one.localhost", "apps": ["erpnext", "client_one"],
           "set_default": true},
          {"name": "client-two.localhost", "apps": ["erpnext", "client_two"],
           "set_default": false}
        ]""")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--sites-json", str(manifest)))

    first_site = calls[1][0][0]
    second_site = calls[2][0][0]
    assert first_site[-1] == "client-one.localhost"
    assert second_site[-1] == "client-two.localhost"
    assert "--set-default" in first_site
    assert "--set-default" not in second_site
    assert not any(argument.startswith("--db-name=") for argument in first_site)
    assert not any(argument.startswith("--db-name=") for argument in second_site)
    assert [arg for arg in first_site if arg.startswith("--install-app=")] == [
        "--install-app=erpnext",
        "--install-app=client_one",
    ]
    assert [arg for arg in second_site if arg.startswith("--install-app=")] == [
        "--install-app=erpnext",
        "--install-app=client_two",
    ]
    assert calls[3][0][0] == [
        "bench",
        "--site",
        "client-one.localhost",
        "set-admin-password",
        "1212",
    ]
    assert calls[4][0][0] == [
        "bench",
        "--site",
        "client-two.localhost",
        "set-admin-password",
        "1212",
    ]
    assert calls[5][0][0] == ["bench", "use", "client-one.localhost"]
    assert all(call[1]["cwd"] == bench_dir for call in calls)


def test_restore_site_is_created_without_app_initialization(tmp_path, monkeypatch):
    make_bench(tmp_path, "frappe", "erpnext", "client_app")
    manifest = tmp_path / "sites.json"
    manifest.write_text(
        '[{"name":"client.localhost","apps":["erpnext","client_app"],'
        '"restore":true,"set_default":true}]'
    )
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--sites-json", str(manifest)))

    new_site = calls[1][0][0]
    assert new_site[-1] == "client.localhost"
    assert not any(arg.startswith("--install-app=") for arg in new_site)


def test_multi_site_existing_site_only_installs_missing_requested_apps(
    tmp_path, monkeypatch
):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext", "client_app")
    site_dir = bench_dir / "sites" / "client.localhost"
    site_dir.mkdir()
    (site_dir / "site_config.json").write_text("{}")
    manifest = tmp_path / "sites.json"
    manifest.write_text(
        '[{"name":"client.localhost",'
        '"apps":["erpnext","client_app"],"set_default":true}]'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        installer, "_site_installed_apps", lambda *_: {"frappe", "erpnext"}
    )
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--sites-json", str(manifest)))

    assert calls[1][0][0] == [
        "bench",
        "--site",
        "client.localhost",
        "install-app",
        "client_app",
    ]
    assert calls[2][0][0] == [
        "bench",
        "--site",
        "client.localhost",
        "set-admin-password",
        "1212",
    ]
    assert calls[3][0][0] == ["bench", "use", "client.localhost"]


def test_multi_site_enforces_each_configured_admin_password(tmp_path, monkeypatch):
    make_bench(tmp_path, "frappe")
    for site in ("one.localhost", "two.localhost"):
        site_dir = tmp_path / "frappe-bench" / "sites" / site
        site_dir.mkdir()
        (site_dir / "site_config.json").write_text("{}")
    manifest = tmp_path / "sites.json"
    manifest.write_text(
        '[{"name":"one.localhost","apps":[],"admin_password":"first",'
        '"set_default":true},{"name":"two.localhost","apps":[],'
        '"admin_password":"second","set_default":false}]'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, "_site_installed_apps", lambda *_: {"frappe"})
    calls = []
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    installer.create_site_in_bench(parse_args("--sites-json", str(manifest)))

    commands = [call[0][0] for call in calls]
    assert [
        "bench",
        "--site",
        "one.localhost",
        "set-admin-password",
        "first",
    ] in commands
    assert [
        "bench",
        "--site",
        "two.localhost",
        "set-admin-password",
        "second",
    ] in commands


def test_installed_apps_accepts_frappe_v15_site_mapping(tmp_path, monkeypatch):
    bench_dir = make_bench(tmp_path, "frappe", "erpnext")
    monkeypatch.setattr(
        installer,
        "_capture",
        lambda *args, **kwargs: '{"client.localhost":["frappe","erpnext"]}',
    )

    apps = installer._site_installed_apps(bench_dir, "client.localhost")

    assert apps == {"frappe", "erpnext"}


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
    monkeypatch.setattr(installer, "sync_manifest_apps", lambda args: None)
    monkeypatch.setattr(installer, "configure_app_git_remotes", lambda args: None)

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
