# Investigation 001: Dataless dependencies and memory pressure slowed verification

- **Status:** Mitigated; monitoring required
- **Date:** 2026-09-11
- **Classification:** Local environment and infrastructure

## Symptom

After Docker Desktop, PostgreSQL, and the project virtual environment were started for the first time, Python imports and pytest collection became unusually slow. One Ruff process ended with exit code 137, which indicates that the operating system sent `SIGKILL`.

## Impact

The product and database remained responsive, but local feedback became too slow to trust at a glance. A developer could incorrectly classify the delay as a hung or flaky test.

## Evidence collected

- `vm_stat` reported 3,628 free 16-KiB pages, approximately 57 MiB of immediately free memory.
- The memory compressor held 141,899 pages, approximately 2.17 GiB.
- `docker stats --no-stream` reported that the PostgreSQL container itself used about 73.41 MiB.
- Ruff later exited with code 137 during the high-pressure period.
- After the disposable container and Docker Desktop were stopped, free pages rose to 86,793, approximately 1.32 GiB.
- The same Ruff check then completed successfully with `All checks passed!`.
- `stat` showed installed virtual-environment files with zero local blocks and the `dataless` flag, meaning the cloud file provider had replaced them with placeholders.
- A virtual environment created under `/private/tmp` installed the same declared dependencies without dataless files.
- The complete suite then ran 19 tests in 0.71 seconds.

## Root-cause assessment

Two environment mechanisms were involved. Cloud-managed dataless dependency files caused long pauses while Python materialized imports, and host memory pressure caused the Ruff process to receive `SIGKILL`. Docker Desktop's virtual machine contributed to total host pressure, but PostgreSQL was not the main memory consumer. Running the same project from a materialized, non-synced virtual environment restored fast deterministic feedback.

## Mitigation

- Start Docker Desktop only for database-backed work.
- Tear down the disposable container after integration validation.
- Stop Docker Desktop when returning to client-only or unit-test work on a constrained machine.
- Mark the project as **Keep Downloaded** before creating an in-project virtual environment, or place the virtual environment outside cloud-synced storage.
- Keep integration and lower-layer test commands independently runnable so failures can be isolated.

## Regression protection

This is an environment-capacity issue rather than product behavior, so an automated product regression test is not appropriate. Feedback time and exit codes will be monitored during future milestones, especially when Xcode and the iOS simulator are introduced.

## Remaining risk

Xcode, the iOS simulator, Docker Desktop, and PostgreSQL running together may exceed comfortable memory capacity. If measured feedback remains poor, revisit ADR-010 and compare reduced Docker Desktop resource limits with a lighter container runtime.

## Interview explanation

> A local check appeared to hang and one formatter process was killed. I separated the product layers, inspected host and container memory, and found both severe host memory pressure and Python dependencies replaced by cloud placeholders. PostgreSQL itself used only about 73 MiB. A materialized virtual environment restored a 0.71-second full-suite run. I fixed the environment instead of adding retries or calling the tests flaky.
