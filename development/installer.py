#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path

COLORS = {
    1: "\033[31m",
    2: "\033[92m",
    3: "\033[93m",
}
RESET_COLOR = "\033[0m"
DATABASES = {
    "mariadb": {"host": "mariadb", "root_username": "root"},
    "postgres": {"host": "postgresql", "root_username": "postgres"},
}
COMMON_BENCH_CONFIG = {
    "redis_cache": "redis://redis-cache:6379",
    "redis_queue": "redis://redis-queue:6379",
    # Kept for backward compatibility with older Frappe releases.
    "redis_socketio": "redis://redis-queue:6379",
    # Bench otherwise increments these when another Bench directory exists.
    "webserver_port": "8000",
    "socketio_port": "9000",
}
REQUIRED_BENCH_PATHS = (
    "apps/frappe",
    "env/bin/python",
    "sites/apps.txt",
    "sites/common_site_config.json",
    "Procfile",
)
SENSITIVE_OPTIONS = {
    "--admin-password",
    "--db-password",
    "--db-root-password",
}
BENCH_NAME = "frappe-bench"
SITE_NAME = "localhost"


def cprint(*args, level: int = 1) -> None:
    """Print a color-coded installer message."""
    color = COLORS.get(level, "")
    message = " ".join(map(str, args))
    print(f"{color}{message}{RESET_COLOR if color else ''}")  # noqa: T201


def main() -> int:
    args = get_args_parser().parse_args()
    try:
        init_bench_if_not_exist(args)
        create_site_in_bench(args)
    except subprocess.CalledProcessError as error:
        command = _format_command(error.cmd)
        cprint(f"Command failed with exit code {error.returncode}: {command}", level=1)
        return error.returncode
    except (OSError, RuntimeError) as error:
        cprint(error, level=1)
        return 1
    return 0


def get_args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and configure a Frappe development bench."
    )
    parser.add_argument(
        "-j",
        "--apps-json",
        help="Optional path to an apps.json file",
    )
    parser.add_argument(
        "--skip-app-install",
        action="store_true",
        help="Create a base site without installing manifest apps",
    )
    parser.add_argument(
        "-r",
        "--frappe-repo",
        help="Frappe repository URL",
        default="https://github.com/frappe/frappe",
    )
    parser.add_argument(
        "-t",
        "--frappe-branch",
        help="Frappe branch (default: version-16)",
        default="version-16",
    )
    parser.add_argument(
        "-p",
        "--py-version",
        help="Python version to select through pyenv",
    )
    parser.add_argument(
        "-n",
        "--node-version",
        help="Node.js version to select through nvm",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose bench output",
    )
    parser.add_argument(
        "-a",
        "--admin-password",
        help="Administrator password for the site (default: admin)",
        default="admin",
    )
    parser.add_argument(
        "-d",
        "--db-type",
        choices=tuple(DATABASES),
        help="Database type (default: mariadb)",
        default="mariadb",
    )
    parser.add_argument(
        "--db-name",
        help="Optional MariaDB database name",
    )
    parser.add_argument(
        "--db-password",
        help="Optional MariaDB site database password",
    )
    parser.add_argument(
        "--db-root-password",
        help="Database root password (default: DB_PASSWORD or 123)",
        default=os.getenv("DB_PASSWORD", "123"),
    )
    return parser


def _run(command, *, cwd: Path, env=None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _format_command(command) -> str:
    if isinstance(command, str):
        return command

    redacted = []
    redact_next = False
    for argument in map(str, command):
        if redact_next:
            redacted.append("***")
            redact_next = False
            continue

        option, separator, _ = argument.partition("=")
        if option in SENSITIVE_OPTIONS:
            if separator:
                argument = f"{option}=***"
            else:
                redact_next = True
        redacted.append(argument)

    return " ".join(shlex.quote(argument) for argument in redacted)


def _bench_init_command(args: argparse.Namespace) -> str:
    command = [
        "bench",
        "init",
        "--skip-redis-config-generation",
        f"--frappe-path={args.frappe_repo}",
        f"--frappe-branch={args.frappe_branch}",
    ]
    if args.apps_json:
        command.append(f"--apps_path={args.apps_json}")
    if args.verbose:
        command.append("--verbose")
    command.append(BENCH_NAME)

    bench_command = " ".join(shlex.quote(argument) for argument in command)
    if args.node_version:
        return f"nvm use {shlex.quote(args.node_version)} && {bench_command}"
    return bench_command


def _set_config(bench_dir: Path, key: str, value: str, *flags: str) -> None:
    _run(["bench", "set-config", *flags, key, value], cwd=bench_dir)


def _set_procfile_web_port(bench_dir: Path, port: int) -> None:
    procfile = bench_dir / "Procfile"
    lines = procfile.read_text(encoding="utf-8").splitlines()

    for index, line in enumerate(lines):
        process, separator, command = line.partition(":")
        if not separator or process.strip() != "web":
            continue

        arguments = shlex.split(command)
        if arguments[:2] != ["bench", "serve"]:
            continue

        filtered = []
        skip_next = False
        for argument in arguments:
            if skip_next:
                skip_next = False
                continue
            if argument == "--port":
                skip_next = True
                continue
            if argument.startswith("--port="):
                continue
            filtered.append(argument)

        filtered.extend(("--port", str(port)))
        lines[index] = f"web: {shlex.join(filtered)}"
        procfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    raise RuntimeError(f"Could not find the Bench web process in {procfile}")


def init_bench_if_not_exist(args: argparse.Namespace) -> None:
    workspace = Path.cwd()
    bench_dir = workspace / BENCH_NAME
    if bench_dir.exists():
        missing_paths = [
            relative_path
            for relative_path in REQUIRED_BENCH_PATHS
            if not (bench_dir / relative_path).exists()
        ]
        if missing_paths:
            missing = ", ".join(missing_paths)
            raise RuntimeError(
                f"{bench_dir} is an incomplete Bench directory; missing: {missing}. "
                "Move it aside and restart initialization."
            )
        cprint("Bench already exists. Reusing it", level=3)
    else:
        env = os.environ.copy()
        # Bench otherwise probes and reloads Supervisor after each app install.
        # The development image includes supervisorctl but does not run a
        # Supervisor daemon, so that probe exits non-zero during bench init.
        env["FRAPPE_DOCKER_BUILD"] = "1"
        if args.py_version:
            env["PYENV_VERSION"] = args.py_version

        _run(
            ["/bin/bash", "-i", "-c", _bench_init_command(args)],
            env=env,
            cwd=workspace,
        )

    cprint("Configuring Bench ...", level=2)
    cprint(f"Setting db_type to {args.db_type}", level=3)
    _set_config(bench_dir, "db_type", args.db_type, "-g")

    for key, value in COMMON_BENCH_CONFIG.items():
        cprint(f"Setting {key} to {value}", level=3)
        _set_config(bench_dir, key, value, "-g")

    cprint("Enabling developer_mode", level=3)
    _set_config(bench_dir, "developer_mode", "1", "-gp")

    cprint("Setting Procfile web port to 8000", level=3)
    _set_procfile_web_port(bench_dir, 8000)


def _manifest_app_name(app: dict) -> str:
    if app.get("app_name"):
        return app["app_name"]

    repository = app.get("url", "").rstrip("/").rsplit("/", 1)[-1]
    return repository.removesuffix(".git").replace("-", "_")


def _installed_apps(bench_dir: Path, apps_json: str | None = None):
    apps_dir = bench_dir / "apps"
    installed = {
        path.name
        for path in apps_dir.iterdir()
        if path.is_dir() and path.name != "frappe"
    }
    ordered = []

    if apps_json:
        manifest = json.loads(Path(apps_json).read_text(encoding="utf-8"))
        for app in manifest:
            app_name = _manifest_app_name(app)
            if app_name in installed and app_name not in ordered:
                ordered.append(app_name)

    ordered.extend(sorted(installed.difference(ordered)))
    return ordered


def _new_site_command(args: argparse.Namespace, apps):
    database = DATABASES[args.db_type]
    command = [
        "bench",
        "new-site",
        "--set-default",
        f"--db-host={database['host']}",
        f"--db-type={args.db_type}",
        f"--db-root-username={database['root_username']}",
        f"--db-root-password={args.db_root_password}",
        f"--admin-password={args.admin_password}",
    ]
    if args.db_type == "mariadb":
        mariadb_options = ["--force", "--no-mariadb-socket"]
        if args.db_name:
            mariadb_options.append(f"--db-name={args.db_name}")
        if args.db_password:
            mariadb_options.append(f"--db-password={args.db_password}")
        command[3:3] = mariadb_options

    command.extend(f"--install-app={app}" for app in apps)
    command.append(SITE_NAME)
    return command


def create_site_in_bench(args: argparse.Namespace) -> None:
    bench_dir = Path.cwd() / BENCH_NAME
    database = DATABASES[args.db_type]

    cprint(f"Setting db_host to {database['host']}", level=3)
    _set_config(bench_dir, "db_host", database["host"], "-g")

    site_config = bench_dir / "sites" / SITE_NAME / "site_config.json"
    if site_config.is_file():
        cprint(f"Site {SITE_NAME} already exists. Reusing it", level=3)
        _run(["bench", "use", SITE_NAME], cwd=bench_dir)
        return

    apps = [] if args.skip_app_install else _installed_apps(bench_dir, args.apps_json)
    command = _new_site_command(args, apps)
    cprint(f"Creating Site {SITE_NAME} ...", level=2)
    _run(command, cwd=bench_dir)


if __name__ == "__main__":
    raise SystemExit(main())
