#!/usr/bin/env python3
import argparse
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
REDIS_CONFIG = {
    "redis_cache": "redis://redis-cache:6379",
    "redis_queue": "redis://redis-queue:6379",
    # Kept for backward compatibility with older Frappe releases.
    "redis_socketio": "redis://redis-queue:6379",
}
SENSITIVE_OPTIONS = {
    "--admin-password",
    "--db-password",
    "--db-root-password",
}


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
    return 0


def get_args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and configure a Frappe development bench."
    )
    parser.add_argument(
        "-j",
        "--apps-json",
        help="Path to apps.json (default: apps.json)",
        default="apps.json",
    )
    parser.add_argument(
        "-b",
        "--bench-name",
        help="Bench directory name (default: frappe-bench)",
        default="frappe-bench",
    )
    parser.add_argument(
        "-s",
        "--site-name",
        help="Site name (default: srv)",
        default="srv",
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
        help="Frappe branch (default: version-15)",
        default="version-15",
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
        help="MariaDB database name (default: srv)",
        default="srv",
    )
    parser.add_argument(
        "--db-password",
        help="MariaDB site database password (default: 1212)",
        default="1212",
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
        f"--apps_path={args.apps_json}",
    ]
    if args.verbose:
        command.append("--verbose")
    command.append(args.bench_name)

    bench_command = " ".join(shlex.quote(argument) for argument in command)
    if args.node_version:
        return f"nvm use {shlex.quote(args.node_version)} && {bench_command}"
    return bench_command


def _set_config(bench_dir: Path, key: str, value: str, *flags: str) -> None:
    _run(["bench", "set-config", *flags, key, value], cwd=bench_dir)


def init_bench_if_not_exist(args: argparse.Namespace) -> None:
    workspace = Path.cwd()
    bench_dir = workspace / args.bench_name
    if bench_dir.exists():
        cprint("Bench already exists. Only site will be created", level=3)
        return

    env = os.environ.copy()
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

    for key, value in REDIS_CONFIG.items():
        cprint(f"Setting {key} to {value}", level=3)
        _set_config(bench_dir, key, value, "-g")

    cprint("Enabling developer_mode", level=3)
    _set_config(bench_dir, "developer_mode", "1", "-gp")


def _installed_apps(bench_dir: Path):
    apps_dir = bench_dir / "apps"
    return sorted(
        path.name
        for path in apps_dir.iterdir()
        if path.is_dir() and path.name != "frappe"
    )


def _new_site_command(args: argparse.Namespace, apps):
    database = DATABASES[args.db_type]
    command = [
        "bench",
        "new-site",
        f"--db-host={database['host']}",
        f"--db-type={args.db_type}",
        f"--db-root-username={database['root_username']}",
        f"--db-root-password={args.db_root_password}",
        f"--admin-password={args.admin_password}",
    ]
    if args.db_type == "mariadb":
        command[2:2] = [
            "--force",
            f"--db-name={args.db_name}",
            f"--db-password={args.db_password}",
            "--no-mariadb-socket",
        ]

    command.extend(f"--install-app={app}" for app in apps)
    command.append(args.site_name)
    return command


def create_site_in_bench(args: argparse.Namespace) -> None:
    bench_dir = Path.cwd() / args.bench_name
    database = DATABASES[args.db_type]

    cprint(f"Setting db_host to {database['host']}", level=3)
    _set_config(bench_dir, "db_host", database["host"], "-g")

    command = _new_site_command(args, _installed_apps(bench_dir))
    cprint(f"Creating Site {args.site_name} ...", level=2)
    _run(command, cwd=bench_dir)


if __name__ == "__main__":
    raise SystemExit(main())
