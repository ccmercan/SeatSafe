# ADR-016: Persist the hold and confirmation key in UserDefaults

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

The iOS app now creates holds and saves the seat/key pair while a hold result is
ambiguous. A successful hold response contains the hold ID required by
`POST /v1/reservations`. Confirmation is another server write with its own idempotency
key. If the app closes during confirmation, it must retain both the hold ID and the same
confirmation key to replay the original reservation response.

In plain language, after receiving the hold receipt, the app must keep it and prepare a
second stable receipt number for the confirmation request. If the response goes missing,
the same second receipt retrieves the same reservation result.

## Options considered

### Option A: Extend the existing UserDefaults flow record

Persist one in-progress client flow at a time: either a pending hold attempt, or a
successful hold plus its confirmation idempotency key.

Advantages:

- Survives leaving the flow and restarting the app.
- Continues the storage choice already accepted in ADR-015.
- Requires no new package or backend endpoint.
- Reuses the backend's existing confirmation idempotency contract.

Disadvantages:

- Local state transitions and clearing rules need explicit tests.
- The single-flow shape must evolve if the product supports carts or multiple holds.

### Option B: Keep the hold and confirmation key only in memory

Advantages:

- Smallest implementation.

Disadvantages:

- App termination loses the hold ID and retry key.
- An uncertain confirmation may leave the user unable to recover the reservation.

### Option C: Add a backend endpoint for flow reconciliation

Advantages:

- The server could reconstruct state if local app data is lost.

Disadvantages:

- Adds API surface, ownership rules, and expiry/reconciliation semantics.
- Larger than needed while the app supports one active demo flow.

## Decision

Choose **Option A**. Extend the injected local flow-store boundary so it saves one
Codable state value under one UserDefaults key:

- `pendingHold(attempt)`: the event-seat ID and hold-creation key, saved before the first
  hold request.
- `pendingConfirmation(hold, key)`: the successful hold response and a confirmation key,
  saved before the user sends confirmation.

Use a single persisted value so transitioning from a successful hold to a pending
confirmation replaces the prior record in one write rather than clearing the hold data
between steps.

- A successful hold response becomes `pendingConfirmation` with a newly generated stable
  key.
- Transport errors, local cancellation, or malformed success responses during
  confirmation retain the same hold and key; Retry resends both unchanged.
- Successful confirmation clears the pending flow after its response is decoded.
- Definite `hold_expired` or `seat_unavailable` responses clear the unusable flow and
  refresh availability.
- `idempotency_key_reused` preserves the flow and blocks further submission rather than
  guessing which request the key represents.

## Rationale

This is the smallest extension to the existing client recovery design. The saved hold ID
and confirmation key are not authentication credentials. UserDefaults is sufficient for
one in-progress demo flow; durable reservation history and multi-account scoping are
future work.

## Validation

1. The local store round-trips a pending confirmation across store instances.
2. The HTTP service sends `hold_id` and `Idempotency-Key` to `POST /v1/reservations`.
3. Simulated response loss followed by retry uses the same hold ID and key and handles the
   replayed success.
4. A restored confirmation remains retryable after app-model recreation.
5. Definitive expiration clears the unusable flow; an idempotency-key conflict does not.
6. The complete iOS test target passes on the available simulator.

## Revisit triggers

- Account authentication requires attempts to be scoped by signed-in user.
- Multiple simultaneous holds, carts, or saved reservations are introduced.
- Server-side reconciliation or durable reservation history is added.

## Owner review

Accepted by the project owner on 2026-09-22 as **Option 1** to extend UserDefaults for the
hold and confirmation flow.
