# ADR-010: Use Docker Desktop for local containers

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

ADR-004 requires a disposable PostgreSQL environment for integration tests. The development machine does not currently have Docker, Colima, Podman, or a local PostgreSQL server installed.

In plain language, SeatSafe needs a repeatable box for PostgreSQL that can be created for tests and discarded afterward. A container provides that box without mixing test data into a long-lived personal database.

## Options considered

### Option A: Docker Desktop

Use Docker Desktop's macOS application, container engine, Docker command-line tool, and Compose support.

Advantages:

- Provides a visual view of containers, logs, ports, and resource use
- Uses the widely documented Docker and Compose workflow
- Reduces initial command-line setup for a developer learning containers

Disadvantages:

- Uses more memory and disk space than lightweight alternatives
- Requires a desktop application and initial startup
- Organizational licensing must be reviewed before workplace use

### Option B: Colima with the Docker command-line tool

Run a lightweight Linux virtual machine and control it primarily from the terminal.

Advantages:

- Lightweight and scriptable
- Compatible with common Docker commands

Disadvantages:

- Adds virtual-machine and context concepts during troubleshooting
- Provides less visual guidance for a developer new to containers

### Option C: Install PostgreSQL directly through Homebrew

Run PostgreSQL as a local macOS service without containers.

Advantages:

- Avoids a container runtime
- Direct access to PostgreSQL tools

Disadvantages:

- Makes clean creation and disposal less obvious
- Risks mixing project state with a long-lived local service
- Differs from the planned containerized CI workflow

## Decision

Choose **Option A** for local development and test containers.

- Docker Desktop supplies the local container engine and Docker Compose.
- Compose defines the disposable PostgreSQL service used by SeatSafe.
- Database data used by automated integration tests must be disposable and must not share a production volume.
- Container startup, readiness, reset, and teardown commands will be documented.
- CI may use its platform's container service rather than Docker Desktop itself; the portable contract is the PostgreSQL container and its configuration.

## Rationale

Docker Desktop offers the clearest learning experience on the current macOS machine and matches the container terminology used by common CI systems. The project accepts its higher local resource use in exchange for easier inspection and troubleshooting.

## Consequences

- Contributors need a compatible container runtime for database integration tests.
- Docker Desktop must be running before Compose commands succeed locally.
- The repository must not assume the Docker Desktop graphical application exists in CI.
- Image versions and configuration must be explicit enough to keep results reproducible.
- Any workplace use remains subject to the workplace's licensing policy.

## Validation

Before this decision is considered successfully implemented:

1. `docker version` can contact the local engine.
2. `docker compose config` validates the repository configuration.
3. A documented command starts PostgreSQL and waits for readiness.
4. Integration tests connect to the container with independent sessions.
5. Teardown removes disposable test data.
6. The owner can inspect the PostgreSQL container and logs in Docker Desktop.

## Revisit triggers

Reconsider this decision if:

- Docker Desktop resource use interferes with Xcode or the iOS simulator.
- A target development or CI environment requires another container engine.
- Licensing or organizational policy prevents its use.

## Owner review

Accepted by the project owner on 2026-09-11.

