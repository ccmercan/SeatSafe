# Test strategy

## Quality mission

Provide evidence that SeatSafe preserves reservation correctness and gives users understandable outcomes when inventory changes, requests are retried, holds expire, or connectivity is lost.

The objective is not maximum test count. It is fast, maintainable feedback with deeper validation where the risk justifies it.

## Highest risks

| Risk | User impact | Primary prevention or detection |
|---|---|---|
| Two users reserve one seat | Broken trust and invalid inventory | Database constraint, transaction design, concurrent API test |
| A retry creates a duplicate | Duplicate reservation and confusing state | Idempotency record, API integration tests |
| An expired hold blocks inventory | Seat becomes unavailable indefinitely | Injectable clock, service tests, scheduled cleanup test |
| Client displays stale availability as guaranteed | Failed checkout and misleading UI | Explicit cached state, server-authoritative confirmation |
| UI automation is flaky | CI loses credibility | Deterministic data, stable identifiers, explicit state synchronization |
| Failure evidence is incomplete | Slow diagnosis and repeated reruns | Correlation IDs, logs, screenshots, test-result artifacts |
| Test controls reach production | Security and integrity exposure | Build-time configuration and negative deployment check |
| A late response overwrites the current screen | User sees data for the wrong event or query | Cancellable structured tasks, request identity, controlled completion-order tests |
| A repeated tap launches duplicate work | Confusing UI and unnecessary server traffic | In-flight state guard, idempotency key, client and API tests |
| Local cancellation is mistaken for server cancellation | Reservation exists but the client reports failure | Reconciliation behavior and ambiguous-result tests |

## Test layers

### Swift unit and component tests

Cover deterministic client behavior:

- Model decoding and formatting
- View-model state transitions
- Hold countdown and expiration
- Error mapping and retry decisions
- Cache behavior and migrations
- Accessibility-facing labels derived from state
- Late-response suppression after navigation or a newer search
- Cancellation before and after an operation reaches the service boundary
- Repeated actions while a reservation task is in flight
- Main-actor UI-state updates
- Isolation of any genuinely shared mutable cache or credential state

Dependencies such as networking, persistence, identifiers, and time should be injectable when doing so enables meaningful behavior tests.

Concurrency tests should use controllable fakes that suspend until the test explicitly completes them. They should never rely on arbitrary sleeps to guess which task will finish first.

### Python unit tests

Cover domain behavior without starting the full service:

- Hold eligibility
- Expiration rules
- Reservation transitions
- Idempotency decisions
- Error mapping

### API and database integration tests

Run against the real application and an isolated PostgreSQL database:

- Contract and validation behavior
- Authorization boundaries when authentication is introduced
- Transaction correctness
- Constraints and migrations
- Idempotent retries
- Concurrent hold and confirmation attempts
- Data cleanup and test isolation

Mocks are not substitutes for database behavior that forms part of a correctness guarantee.

### XCUITest journeys

Keep the UI suite small and high value:

1. Browse an event and reserve an available seat.
2. Recover when a selected seat becomes unavailable.
3. Handle hold expiration.
4. Retrieve a cached reservation while offline.
5. Cancel a reservation.
6. Complete the critical journey with large text.
7. Complete the critical journey in one additional locale.

UI tests should use screen objects or similarly focused interaction helpers. Assertions must remain visible in the test cases; abstractions should not hide the behavior being verified.

### Performance and contention tests

Start with measurement, not invented thresholds:

- Establish event-list and seat-map latency baselines.
- Measure reservation behavior under contention.
- Measure application launch or one critical client operation.
- Convert a baseline into a release threshold only after repeated, controlled measurements.

### Exploratory testing

Automated coverage will be complemented by focused charters for:

- Rapid connectivity changes
- Accessibility and screen-reader behavior
- Unexpected navigation during a hold
- Time-zone and clock-boundary behavior
- Visual clarity of stale, conflicting, and expired states

## Test data strategy

Required properties:

- Stable identifiers for core fixtures
- Scenario-specific data with no dependence on execution order
- Isolated database state for integration tests
- A documented local seed command
- A reset mechanism restricted to test environments
- No dependency on a commercial API

The exact reset mechanism is not decided yet. It will require an ADR because endpoint-based resets, direct fixtures, and disposable databases have different security and fidelity tradeoffs.

## CI test allocation

### Pull request

- Formatting and static analysis
- Swift and Python unit tests
- API/database integration tests
- iOS build
- One critical XCUITest smoke journey
- Machine-readable results and failure artifacts

### Scheduled regression

- Complete XCUITest suite
- Multiple simulator and locale configurations
- Contention and performance scenarios
- Repeated execution used to measure flake rate
- Dependency and environment checks

## Flaky-test policy

A test is flaky when identical code and controlled inputs produce inconsistent outcomes.

When flakiness is observed:

1. Preserve failure evidence.
2. Reproduce under controlled repetition.
3. Classify the source: product race, test race, environment, data leakage, or infrastructure.
4. Fix the underlying cause when possible.
5. Quarantine only when necessary, with an owner, issue, and removal condition.
6. Do not use unreported retries to turn an unstable test green.

## Traceability

Tests should reference requirement identifiers when the relationship is not obvious. Defect case studies should connect:

```text
Requirement -> Risk -> Test -> Failure evidence -> Root cause -> Fix -> Regression test
```

## Metrics

Track only measured values that help make a decision:

- Feedback time by workflow
- Pass and failure counts by layer
- Flake rate across controlled repetitions
- Critical-risk coverage
- Defects detected and escaped
- API and application performance baselines

Coverage percentage may be recorded, but it is not a proxy for quality or a standalone goal.
