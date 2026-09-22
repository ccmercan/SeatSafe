# ADR-015: Persist the pending hold attempt in UserDefaults

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

ADR-014 makes a repeated hold request safe only when the client repeats the same
`event_seat_id` with the same `Idempotency-Key`. If the app loses either value after the
server accepts a request but before the response arrives, it cannot safely recover the
original hold.

In plain language, the client needs to keep the seat number and the retry receipt together
until the server gives it a definite answer.

## Options considered

### Option A: Store one pending attempt in UserDefaults

Save the selected event-seat ID and idempotency key as one small Codable value before
sending the request. Keep it after transport errors or cancellation. Clear it after a
successful response or a definitive `seat_unavailable` response.

Advantages:

- Survives leaving the screen and restarting the app.
- Uses an iOS-provided key/value store without adding a dependency.
- The identifiers are not credentials or other secrets, so Keychain is unnecessary.

Disadvantages:

- A tiny persistence boundary and lifecycle behavior must be tested.
- UserDefaults is local to this installation; deleting the app loses the pending attempt.

### Option B: Keep the attempt only in memory

Advantages:

- Simplest storage and no persistence code.

Disadvantages:

- App termination forgets the key, so an ambiguous accepted request becomes inaccessible.
- Does not meet FR-CON-007 across app restarts.

### Option C: Add a backend endpoint to look up the user's active hold

Advantages:

- The backend could help recover even if local attempt data is lost.

Disadvantages:

- Adds a new API contract and ownership-sensitive query.
- Requires defining behavior for expired holds and multiple active holds.
- More work than persisting the two values required by the existing retry contract.

## Decision

Choose **Option A**. Use an injected `PendingHoldAttemptStore` protocol and a
`UserDefaultsPendingHoldAttemptStore` implementation. Store at most one pending attempt for
the current single-seat flow. The persisted value contains only the event-seat UUID and
idempotency key.

- Persist the pair before starting the network request.
- A transport failure, task cancellation, or undecodable response is ambiguous; retain the
  pair and offer a retry with exactly the same values.
- A successful hold response clears the pending attempt after it is received.
- A definitive `seat_unavailable` response clears the attempt; the user may make a new
  attempt, which receives a new key.
- An `idempotency_key_reused` response preserves the attempt and blocks another submission;
  the client must not guess which request the stored key represents.
- Restoring a saved attempt preselects that seat and offers retry even if the latest
  availability snapshot now says `held`.
- While the outcome is ambiguous, do not silently switch to another seat or create a new
  key. The server remains authoritative for whether a hold exists.

## Rationale

The app needs only a tiny, non-secret pair to use the recovery contract already accepted
in ADR-014. UserDefaults meets the restart requirement without turning this small flow into
a database or adding a backend endpoint.

## Validation

1. A persistence adapter round-trips the pending attempt through UserDefaults.
2. Model tests prove the attempt is stored before the request and cleared after success or
   definitive unavailability.
3. A simulated lost response retains the key; retry sends the same seat and key and can
   receive the backend's original result.
4. A restored attempt remains available for retry when the refreshed seat snapshot reports
   the seat as held.
5. The iOS test target builds and its tests pass on the available simulator.

## Revisit triggers

- Add account identity: scope pending attempts to the signed-in user and clear or segregate
  them on logout.
- Support multiple pending seats or carts: replace the single-attempt storage shape.
- Add a backend reconciliation API or change hold-expiry/ownership behavior.

## Owner review

Accepted by the project owner on 2026-09-22 as **Option A**.
