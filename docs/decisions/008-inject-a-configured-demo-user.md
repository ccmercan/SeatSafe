# ADR-008: Inject a server-configured demo user in Phase 1

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

Holds and reservations belong to a user. The service must know the current user's identity to enforce ownership, but full account registration and authentication are not part of the first vertical slice.

In plain language, the reservation code needs a trustworthy name tag for the current user. For Phase 1, the server supplies that name tag from configuration. Later, a login system can supply it instead without changing the reservation rules.

## Options considered

### Option A: Implement production-style authentication now

Add account registration or seeded credentials, password handling, token issuance, token validation, and expiration behavior.

Advantages:

- Provides a realistic security boundary
- Supports multiple users through the public API

Disadvantages:

- Expands the first slice substantially
- Introduces security-sensitive behavior before the reservation core is proven
- Adds many tests unrelated to the highest initial risk

### Option B: Inject a server-configured demo user

FastAPI resolves a `CurrentUser` dependency from trusted server configuration. Tests replace that dependency or call services with explicit user identities.

Advantages:

- Keeps identity explicit in routes and services
- Does not trust a caller-supplied user identifier
- Allows tests to simulate different owners
- Can be replaced by authentication without changing the reservation use cases

Disadvantages:

- Does not provide real authentication
- The running demo represents one configured user at a time
- Multi-user HTTP demonstrations require test dependency overrides or separate configured instances

### Option C: Trust a user identifier supplied in an HTTP header

Read a header such as `X-User-ID` and treat it as the authenticated identity.

Advantages:

- Convenient for API demonstrations and tests
- Allows callers to switch users easily

Disadvantages:

- Callers can impersonate any user
- Resembles an authentication mechanism without providing its security
- Requires a strict test-only configuration boundary

## Decision

Choose **Option B** for Phase 1.

- Routes receive a `CurrentUser` through FastAPI dependency injection.
- The initial provider resolves one seeded demo-user identifier from server-owned configuration.
- Client-controlled headers or request bodies do not determine the trusted current-user identity.
- Application services receive the resolved identity as explicit input and enforce hold ownership.
- Unit tests pass explicit user identities to services.
- API tests may replace the identity dependency to exercise different owners.
- The identity interface will allow a future authentication provider to replace the demo provider without changing reservation-domain behavior.
- Documentation must state that Phase 1 does not implement production authentication or authorization security.

For example, an API test can override the provider so Alice creates a hold and Bob attempts to confirm it. The service rejects Bob because his injected identity does not match the hold owner. A normal caller cannot become Bob merely by adding an untrusted user-ID header.

## Rationale

This decision keeps ownership behavior real while deferring a separate authentication project. An explicit identity dependency avoids baking demo assumptions into the domain service and preserves a clean future replacement point.

## Consequences

- The initial locally running API acts as one configured demo user.
- Authorization tests can still cover multiple identities below the public production configuration.
- Configuration parsing must fail clearly when the seeded user is missing or invalid.
- No claim of production-ready authentication may be made for the first release.
- Introducing real authentication will require a separate security decision and threat review.

## Validation

Before this decision is considered successfully implemented:

1. Routes obtain identity through the dependency rather than request-provided user IDs.
2. A service test proves that only the hold owner may confirm or release it.
3. An API test overrides identity to prove a different user receives the defined rejection.
4. The normal application configuration ignores or rejects attempts to select an identity through an untrusted header.
5. Replacing the identity provider requires no change to reservation-service rules.
6. The README clearly states the authentication limitation.

## Revisit triggers

Reconsider this decision if:

- A milestone requires multiple real users through the public API.
- Authentication or authorization becomes a target-role requirement.
- The application is prepared for any environment beyond a local portfolio demonstration.

## Owner review

Accepted by the project owner on 2026-09-11.

