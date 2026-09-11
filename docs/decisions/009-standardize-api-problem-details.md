# ADR-009: Standardize API errors with Problem Details

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

The iOS client and automated tests need to distinguish expected failures such as an unavailable seat, an expired hold, and an idempotency-key mismatch. English messages alone are not stable enough for program behavior, and request failures need a correlation identifier that connects the client response to server diagnostics.

In plain language, every error should use the same form. People receive a readable explanation, while software receives a stable code it can safely act on.

## Options considered

### Option A: Use FastAPI's default error body

Return the framework's default `detail` field for validation and application errors.

Advantages:

- Requires little custom code
- Familiar to FastAPI developers

Disadvantages:

- Does not provide one consistent contract for all failure categories
- Encourages clients to interpret changing human-readable text
- Does not include SeatSafe error codes or correlation identifiers by default

### Option B: Use RFC 9457 Problem Details with SeatSafe extensions

Return the standard Problem Details fields and add stable `code` and `correlation_id` extension members.

Advantages:

- Uses an established HTTP error format
- Separates human-readable detail from machine-readable behavior
- Supports consistent API tests and iOS error mapping
- Connects responses to diagnostic logs

Disadvantages:

- Requires centralized exception and validation-error mapping
- Extension fields must be documented and kept stable
- Care is required not to expose internal implementation details

### Option C: Invent a custom response envelope

Wrap all failures in a SeatSafe-specific structure.

Advantages:

- Complete control over the shape
- Can be optimized for one client

Disadvantages:

- Creates a format clients must learn without standards support
- Requires decisions already addressed by Problem Details
- Makes interoperability and explanation harder

## Decision

Choose **Option B**.

- Expected API failures use the `application/problem+json` media type.
- Responses include the standard `type`, `title`, `status`, and `detail` members.
- `type` is a stable URI identifier for the problem category.
- SeatSafe adds a stable machine-readable `code` extension.
- SeatSafe adds a `correlation_id` extension matching the request's diagnostic context.
- The public `detail` explains the user-relevant problem without exposing stack traces, SQL, credentials, or internal state.
- Request validation failures are normalized into the same overall contract.
- The iOS client branches on stable codes or typed mappings, not on English message text.

An unavailable seat, for example, uses HTTP `409 Conflict`, a stable `seat_unavailable` code, and a readable explanation. Changing that explanation does not break the client's conflict behavior.

The initial problem codes include:

- `seat_unavailable`
- `hold_expired`
- `hold_owner_mismatch`
- `idempotency_key_reused`
- `resource_not_found`
- `validation_failed`

## Rationale

Problem Details supplies a recognized contract while extension members cover SeatSafe's client and observability needs. Central mapping also keeps HTTP concerns out of domain services, consistent with ADR-005.

## Consequences

- Domain failures require centralized HTTP mappings.
- API contract tests must assert status, media type, code, and required fields.
- Human-readable details may evolve, but stable codes are compatibility-sensitive.
- Correlation middleware must establish an identifier before failures are handled.
- Unexpected failures return a safe generic problem while retaining detailed server diagnostics.

## Validation

Before this decision is considered successfully implemented:

1. A representative domain conflict returns the documented status and Problem Details body.
2. Validation errors use the standardized contract.
3. The response correlation identifier matches the identifier in captured logs.
4. Tests assert stable codes rather than full English sentences where behavior is the concern.
5. Unexpected errors do not expose stack traces or database details.
6. The owner can explain the difference between an HTTP status, a stable error code, and a human-readable detail.

## Revisit triggers

Reconsider this decision if:

- A published API specification requires another error format.
- Multiple clients need additional structured error metadata.
- Versioning reveals that existing problem codes are too broad.

## Owner review

Accepted by the project owner on 2026-09-11.

