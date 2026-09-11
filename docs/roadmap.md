# Roadmap

The roadmap is organized around demonstrable engineering outcomes rather than feature volume.

## Phase 0: Foundation

Status: complete. ADR-001 was accepted by the project owner on 2026-09-11.

Deliverables:

- Product brief
- Traceable requirements
- Initial risk-based test strategy
- Learning and ownership agreement
- ADR-001 proposal
- Initialized Git repository

Exit condition: the owner reviews the documents and accepts or revises ADR-001.

## Phase 1: Reservation-core vertical slice

Status: in progress. The backend foundation, disposable PostgreSQL environment, initial schema migration, hold creation, deterministic demo seeding, and seat-retrieval snapshot were created on 2026-09-11. Reservation confirmation, idempotency, and concurrent request testing remain pending.

Scope:

- One seeded event and a small seat layout
- Retrieve seats
- Hold one seat
- Confirm one reservation
- Prevent a duplicate active reservation
- Unit and PostgreSQL integration tests

Key decisions:

- Backend framework and dependency boundaries
- Database schema and concurrency-control strategy
- Test database lifecycle

Exit condition: the core invariant is demonstrated by an automated concurrent test.

## Phase 2: Native iOS vertical slice

Scope:

- Event display
- Seat selection
- Hold and confirmation UI
- Clear conflict and failure states
- XCTest coverage for client state

Key decisions:

- Minimum iOS and Xcode versions
- Client architecture
- Networking and dependency injection
- Local state representation
- Structured task ownership and cancellation
- Main-actor and shared-state isolation boundaries

Exit condition: the critical flow works in the simulator, is covered below the UI layer, and remains correct when requests complete out of order, are cancelled, or are triggered repeatedly.

## Phase 3: UI automation and testability

Scope:

- Stable accessibility identifiers
- Deterministic scenario control
- Critical XCUITest smoke journey
- Conflict, expiration, and error scenarios
- Failure screenshots and result bundles

Key decisions:

- UI test abstraction style
- Test scenario injection
- Data reset mechanism

Exit condition: UI tests can run repeatedly without manual setup and produce useful diagnostics.

## Phase 4: CI and release signals

Scope:

- Pull-request workflow
- Scheduled regression workflow
- Machine-readable test reports
- Retained diagnostic artifacts
- Documented quality gates

Key decisions:

- Workflow split and expected feedback time
- Simulator matrix
- Flake measurement and quarantine policy

Exit condition: a clean checkout is validated automatically and a deliberate failure is diagnosable from artifacts.

## Phase 5: Offline, accessibility, and performance

Scope:

- Cached reservations with explicit stale state
- Large-text and accessibility validation
- Additional locale
- Performance baselines
- Contention scenario

Exit condition: nonfunctional behavior is measured and documented without overstating production scale.

## Phase 6: Portfolio release

Scope:

- Three defect case studies
- Architecture diagram
- Short demonstration video
- Measured outcomes
- Resume bullets grounded in evidence
- Interview project-defense review

Exit condition: a reviewer can understand, run, and evaluate the project without private explanation.
