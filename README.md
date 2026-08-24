<div align="center">
  <img src="docs/public/frappe-docker.png" alt="Frappe Docker" width="80" />
  <h1>Frappe Docker</h1>
  <p>Docker images and orchestration for Frappe applications.</p>
  <p>
    <a href="https://github.com/frappe/frappe_docker/actions/workflows/core-build-stable.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/frappe/frappe_docker/core-build-stable.yml?branch=main&label=Build%20Stable" alt="Build Stable" />
    </a>
    <a href="https://github.com/frappe/frappe_docker/actions/workflows/core-build-develop.yml">
      <img src="https://img.shields.io/github/actions/workflow/status/frappe/frappe_docker/core-build-develop.yml?branch=main&label=Build%20Develop" alt="Build Develop" />
    </a>
    <a href="https://frappe.github.io/frappe_docker/">
      <img src="https://img.shields.io/badge/Docs-Open%20Site-0A7EA4" alt="Docs" />
    </a>
  </p>
</div>

## Start here for company development

Install and start [Docker Desktop](https://docs.docker.com/desktop/), then clone
this repository:

```sh
git clone https://github.com/bhickta/erp-docker.git
cd erp-docker
```

Continue with [Company developer onboarding](#company-developer-onboarding-macos).
Your company administrator will provide the required `apps.json` and `.env`
files separately through a secure channel. You do not need a company-specific
Git branch.

## What is this?

This repository is the official container setup for Frappe applications.

It provides Docker images, Compose configurations, and documentation for running Frappe applications, including ERPNext, CRM, Helpdesk, and other Frappe apps, in containers.

Use it if you want to:

- run ERPNext, CRM, Helpdesk, or other Frappe apps with Docker
- start from a quick demo setup
- use production-ready Docker images and Compose setups
- build custom app images
- deploy and operate Frappe in production

## Repository Structure

```bash
frappe_docker/
├── .devcontainer/        # Cross-platform development environment
├── development/          # Development workspace, bootstrap, and unit tests
├── docs/                 # Complete documentation and VitePress site
├── images/               # Docker image definitions
├── overrides/            # Optional production Compose configurations
├── resources/            # Runtime scripts and configuration templates
├── tests/                # Integration tests and shared test dependencies
├── compose.yaml          # Canonical production Compose entry point
├── pwd.yml               # Disposable single-file demo
└── docker-bake.hcl       # Canonical image-build definition
```

> This section describes the structure of **this repository**, not the Frappe framework itself.
> Root-level files are limited to standard project metadata and entry points
> discovered there by Docker, GitHub, Git, pre-commit, and test tooling.

### Key Components

- `docs/` - Canonical documentation for all deployment and operational workflows
- `overrides/` - Opinionated Compose overrides for common deployment patterns
- `compose.yaml` - Base compose file for production setups (production)
- `pwd.yml` - Disposable demo environment (non-production)
- `.devcontainer/` - Local development environment for macOS, Windows, and Linux

## Documentation

The full `frappe_docker` documentation is available in [`docs/`](docs/) and published at [frappe.github.io/frappe_docker](https://frappe.github.io/frappe_docker/).

### Recommended entry points:

- **New here:** [Getting Started Guide](docs/getting-started.md)
- **Choosing a setup:** [Deployment methods](docs/01-getting-started/01-choosing-a-deployment-method.md)
- **ARM64 notes:** [ARM64](docs/01-getting-started/03-arm64.md)
- **Container setup overview:** [Container Setup Overview](docs/02-setup/01-overview.md)
- **Running in production:** [Production docs](docs/03-production/)
- **Operating a deployment:** [Operations docs](docs/04-operations/)
- **Development workflows:** [Development](docs/05-development/01-development.md)
- **Mac/company developers:** [macOS company setup](docs/05-development/04-macos-development.md)
- **FAQ:** [Frequently Asked Questions](https://github.com/frappe/frappe_docker/wiki/Frequently-Asked-Questions)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose v2](https://docs.docker.com/compose/)
- [git](https://docs.github.com/en/get-started/getting-started-with-git/set-up-git)

> For Docker basics and best practices refer to Docker's [documentation](http://docs.docker.com)

## Company developer onboarding (macOS)

The company administrator sends each developer two local configuration files
through a secure channel:

- an `apps.json` manifest containing the company's Frappe applications
- a `.env` file containing the local site configuration and backup credential

Save the supplied files under a company profile after cloning. For example:

```text
.apps-json/example-company/apps.json
.devcontainer/example-company.env
```

Both paths are ignored by Git. Do not rename, commit, paste into an issue, or
send the `.env` file through an unsecured channel.

The command-line workflow below accepts the named environment file explicitly.
VS Code Dev Containers instead loads `.devcontainer/.env`. To use the same
named profile when reopening the repository in a Dev Container, create a
relative symlink from the repository root:

```sh
ln -s example-company.env .devcontainer/.env
```

For example, a profile stored as `.devcontainer/srv.env` uses
`ln -s srv.env .devcontainer/.env`. Create only one `.env` link at a time.

Install and start [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/),
then run:

```sh
git clone https://github.com/bhickta/erp-docker.git
cd erp-docker

# Copy the two supplied files to the paths shown above, then:
development/dev-env.sh \
  --apps-json .apps-json/example-company/apps.json \
  --env-file .devcontainer/example-company.env \
  validate

development/dev-env.sh \
  --apps-json .apps-json/example-company/apps.json \
  --env-file .devcontainer/example-company.env \
  up
```

Open `http://localhost:8000` after the environment becomes healthy. See the
[macOS company setup guide](docs/05-development/04-macos-development.md) for
backup restoration, status, logs, stopping the environment, and Mac-specific
troubleshooting.

## Development quick start

After cloning the repository, macOS, Windows, and Linux users can create and
start the complete development environment with the same command:

```sh
docker compose -f .devcontainer/docker-compose.yml up --detach --wait
```

Docker pulls the required images, creates MariaDB and Redis, initializes a
Frappe Bench and `development.localhost` site when missing, and waits until
Frappe is ready. Open `http://localhost:8000` and sign in as `Administrator`
with password `admin`.

The default is a framework-only Frappe environment. To include ERPNext or
other apps on the first run, configure an optional apps JSON file as described
in the [development guide](docs/05-development/01-development.md#work-with-apps).

The command is safe to run again: an existing Bench and site are reused. See
the [complete development environment guide](docs/05-development/01-development.md)
for configuration, daily commands, persistence, updates, troubleshooting,
reset instructions, and optional VS Code Dev Containers integration.

## Demo setup

The fastest way to try Frappe locally is with the single-file demo setup in `pwd.yml`.

### Try on your environment

> **⚠️ Disposable demo only**
>
> **This setup is intended for short-lived evaluation only.** You will not be able to install custom apps to this setup. For production deployments, custom configurations, and detailed explanations, see the full documentation.

First clone the repo:

```sh
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
```

Then run:

```sh
docker compose -f pwd.yml up -d
```

Wait for a couple of minutes for ERPNext site to be created or check `create-site` container logs before opening browser on port `8080`. (username: `Administrator`, password: `admin`)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

This repository is only for container related stuff. You also might want to contribute to:

## Resources

- [Frappe framework](https://github.com/frappe/frappe),
- [ERPNext](https://github.com/frappe/erpnext),
- [Frappe Bench](https://github.com/frappe/bench).

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE) for details.
