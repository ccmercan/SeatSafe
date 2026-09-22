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

Status: complete. The backend foundation, disposable PostgreSQL environment, schema migrations, hold creation, deterministic demo seeding, seat-retrieval snapshot, and reservation confirmation with database-backed idempotency are implemented. ADR-014 extends idempotency to hold creation. PostgreSQL integration tests prove that competing requests produce one hold, same-key hold retries replay one result, a key reused for another seat is rejected, and database failures roll back the hold and replay record together. Confirmation retry and rollback behavior is also covered.

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

Exit condition: met. PostgreSQL concurrency tests demonstrate one valid hold winner for competing callers; confirmation and hold tests demonstrate safe retries; forced database constraint failures demonstrate each operation's state change and idempotency record commit or roll back together.

## Phase 2: Native iOS vertical slice

Status: in progress. ADR-002 selects Swift structured concurrency and main-actor feature
state; ADR-012 sets the iOS deployment target to 17; ADR-013 selects lightweight SwiftUI
feature models with injected async services. Seat-snapshot loading and local selection
of one available seat are implemented and unit tested. ADR-014 defines database-backed
retry behavior for creating a server-side hold; ADR-015 chooses UserDefaults to preserve
the client attempt across flow exits and app restarts. Hold creation and ambiguous-result
recovery are now implemented. The next client step is confirming a hold as a reservation.

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
