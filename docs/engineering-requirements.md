# Engineering requirements

Requirement identifiers will be referenced by tests, defect reports, and release criteria.

## Functional requirements

### Events

- **FR-EVT-001:** The service shall return upcoming events with stable identifiers.
- **FR-EVT-002:** The client shall display relevant loading, empty, success, and recoverable-error states.
- **FR-EVT-003:** The user shall be able to search events by title or venue.

### Seat availability

- **FR-SEAT-001:** The service shall return the seat layout and current availability for an event.
- **FR-SEAT-002:** The client shall expose an accessible label and stable automation identifier for every seat.
- **FR-SEAT-003:** The client shall treat server availability as authoritative when creating a hold.

### Holds

- **FR-HOLD-001:** An available seat may be held for a configurable duration.
- **FR-HOLD-002:** Only one active, unexpired hold may exist for an event seat.
- **FR-HOLD-003:** Only the hold owner may confirm or release the hold.
- **FR-HOLD-004:** An expired hold shall no longer prevent another user from holding the seat.

### Reservations

- **FR-RES-001:** A valid hold may be confirmed as exactly one reservation.
- **FR-RES-002:** Repeating a confirmation with the same idempotency key shall not create a duplicate reservation.
- **FR-RES-003:** Competing requests for one seat shall produce at most one active reservation.
- **FR-RES-004:** A user shall be able to retrieve their reservations.
- **FR-RES-005:** A user shall be able to cancel an active reservation.

### Offline behavior

- **FR-OFF-001:** Previously retrieved reservations shall remain readable without network connectivity.
- **FR-OFF-002:** The client shall indicate when displayed information came from a cache.
- **FR-OFF-003:** Seat availability shall not be presented as guaranteed while offline.

### Client concurrency

- **FR-CON-001:** Client service operations shall expose asynchronous APIs using Swift structured-concurrency primitives.
- **FR-CON-002:** Observable UI state shall be isolated to the main actor.
- **FR-CON-003:** A response belonging to an obsolete screen, query, or event selection shall not overwrite newer UI state.
- **FR-CON-004:** Repeated reservation actions shall not create uncontrolled duplicate client operations. Server-side idempotency and database guarantees shall remain authoritative.
- **FR-CON-005:** Cancellation shall produce a defined state. The client shall not assume that cancelling a local task cancelled work already accepted by the server.
- **FR-CON-006:** Shared mutable client state shall be isolated explicitly when required; actors shall not be introduced where immutable values or main-actor isolation are sufficient.
- **FR-CON-007:** Leaving and returning to a reservation flow shall reconcile ambiguous in-flight results with the server.

## Quality requirements

- **QR-TEST-001:** Tests shall be deterministic under documented local and CI environments.
- **QR-TEST-002:** Test data shall be resettable without manual database editing.
- **QR-TEST-003:** UI tests shall use stable accessibility identifiers instead of localized display text for element lookup.
- **QR-TEST-004:** A failed CI run shall retain enough evidence to diagnose the failure without immediately rerunning it.
- **QR-TEST-005:** Automatic retries shall not be used to conceal unstable tests.
- **QR-TEST-006:** Client concurrency tests shall control suspension and completion order without fixed-duration sleeps.
- **QR-TEST-007:** Tests shall verify state transitions and externally visible behavior rather than depending on task scheduling order.

- **QR-CI-001:** Pull requests shall run formatting, static analysis, unit tests, backend integration tests, a client build, and a critical UI smoke test.
- **QR-CI-002:** Longer regression, configuration, contention, and performance tests shall run on a scheduled workflow.
- **QR-CI-003:** CI shall publish machine-readable test results and relevant diagnostics.

- **QR-PERF-001:** Performance targets shall be based on measured baselines before they become release gates.
- **QR-ACC-001:** The critical reservation flow shall remain usable with larger text sizes.
- **QR-ACC-002:** Interactive controls shall provide meaningful accessibility labels and traits.

- **QR-SEC-001:** Secrets shall not be committed to the repository.
- **QR-SEC-002:** Test-control endpoints shall be unavailable in production configuration.
- **QR-OBS-001:** Requests involved in holds and reservations shall carry a correlation identifier through logs.

## Initial API surface

```text
GET    /v1/events
GET    /v1/events/{event_id}
GET    /v1/events/{event_id}/seats
POST   /v1/holds
DELETE /v1/holds/{hold_id}
POST   /v1/reservations
GET    /v1/reservations
GET    /v1/reservations/{reservation_id}
DELETE /v1/reservations/{reservation_id}
GET    /health
```

Test-environment controls are a separate design decision and are not yet accepted API requirements.

## Initial data entities

```text
User
Venue
Event
Seat
EventSeat
SeatHold
Reservation
IdempotencyRecord
AuditEvent
```

The exact schema and transaction strategy require a separate ADR before implementation.

## First vertical-slice acceptance criteria

The first slice should intentionally be narrower than the final product:

1. A seeded event and seat can be retrieved from the service.
2. A client or API caller can hold and confirm one available seat.
3. A second confirmation cannot create another active reservation for that seat.
4. Unit and integration tests establish the behavior.
5. The design and limitations are documented.
