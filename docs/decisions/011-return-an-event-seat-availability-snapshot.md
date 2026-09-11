# ADR-011: Return one event-seat availability snapshot

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

The future iOS seat-selection screen needs stable seat identifiers, display location,
price, and current availability. The API contract should be small enough to understand
while still representing the server-owned inventory state clearly.

In plain language, the client should be able to ask one question—"what seats can I
show for this event right now?"—without assembling the answer from several requests.

An availability response is only a snapshot. It must not imply that a seat remains
available after the response is sent. Hold creation continues to lock and re-check the
authoritative database row.

## Options considered

### Option A: One event-seat list with computed availability

Return each event seat's identifier, location, price, and one computed status:
`available`, `held`, or `reserved`.

Advantages:

- Gives the client one coherent response for its seat-selection screen
- Keeps database records and internal lifecycle details out of the API
- Makes contract and state-calculation tests focused and readable

Disadvantages:

- The response can become stale immediately under concurrent activity
- A larger venue may eventually need pagination or a more compact representation

### Option B: Separate layout and availability endpoints

Return stable seat geometry from one endpoint and changing inventory from another.

Advantages:

- Static layout can be cached independently
- Availability responses can be smaller

Disadvantages:

- The client must join two responses and handle mismatched versions
- Adds coordination complexity before SeatSafe has measured a need for it

### Option C: Embed all seats in the event-details response

Return the event, venue, and seat inventory as one large resource.

Advantages:

- One request can populate multiple screens
- Simple for a very small demonstration

Disadvantages:

- Couples event metadata to frequently changing inventory
- Makes later caching and endpoint evolution harder to explain

## Decision

Choose **Option A**.

`GET /v1/events/{event_id}/seats` returns an event identifier and a deterministically
ordered list. Each item exposes:

- `event_seat_id`
- `section`
- `row`
- `number`
- `price_cents`
- `status`, one of `available`, `held`, or `reserved`

An active reservation takes precedence over a hold. An active hold is reported as
`held` only while its expiration is later than the server's injected clock. An expired
hold therefore reads as `available`, but hold creation remains responsible for changing
the stored hold status within its locking transaction.

The read path does not lock inventory. The response communicates observed state, not a
promise. `POST /v1/holds` remains the authoritative operation.

## Rationale

This is the smallest contract that supports the next iOS screen and exposes the real
engineering concept: reading availability and claiming inventory are different
operations. It also preserves a clean boundary between PostgreSQL facts and the public
status vocabulary.

## Consequences

- Clients must handle a hold conflict even after seeing `available`.
- Status-calculation behavior belongs in the application service and can use an
  injected clock in deterministic tests.
- PostgreSQL queries return the facts needed to calculate status without exposing hold
  owners or reservation records.
- Pagination and layout versioning are deferred until measurements justify them.

## Validation

1. A deterministic seed produces one event and a stable ordered seat layout.
2. Application tests cover available, unexpired-held, expired-held, and reserved states.
3. API tests cover the success contract and the standard not-found problem.
4. PostgreSQL integration tests prove the real query and ordering.
5. A manual caller can retrieve a seeded event, select an `event_seat_id`, and create a
   hold while still handling a possible `409 seat_unavailable` response.

## Owner review

Accepted by the project owner on 2026-09-11.
