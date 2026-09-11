# ADR-002: Manage client work with Swift structured concurrency

- **Status:** Proposed
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

The iOS client will load events and seats, create holds, confirm reservations, maintain a countdown, cache results, and react to navigation. These operations may overlap or finish in an order different from the order in which the user started them.

Client concurrency is distinct from server concurrency. The iOS client must keep its interface responsive and internally consistent, while the backend and database remain responsible for the global one-reservation-per-seat invariant.

The client must address:

- A request finishing after the user has navigated elsewhere
- A newer search completing before an older search
- Rapid repeated taps on a reservation action
- Cancellation while an operation may already have reached the server
- Shared mutable cache or credential state
- UI updates that must occur on the main actor

## Options considered

### Option A: Independent unstructured tasks started directly by views

Advantages:

- Minimal initial code
- Easy to demonstrate in a small prototype

Disadvantages:

- Task lifetime is difficult to associate with feature lifetime
- Late results can overwrite current state
- Cancellation and repeated actions become scattered across views
- Tests tend to depend on timing rather than controlled behavior

### Option B: Structured async service APIs with main-actor feature state

Use `async`/`await` service boundaries, main-actor-isolated observable feature state, explicit ownership of longer-lived tasks, cancellation on replacement or feature exit, and actors only for state genuinely shared outside the main actor.

Advantages:

- Task ownership and UI-state isolation are explicit
- Cancellation and stale-result behavior can be tested deliberately
- Aligns concurrency behavior with feature boundaries
- Avoids introducing an actor for every type
- Supports controllable test doubles at async service boundaries

Disadvantages:

- Requires careful reasoning about cancellation and actor isolation
- Local task cancellation cannot guarantee that server work stopped
- Some task handles or request identities may still be necessary

### Option C: Model all asynchronous state with Combine publishers

Advantages:

- Strong stream-composition operators
- Mature patterns for cancellation and debouncing

Disadvantages:

- Adds a second concurrency model when Swift structured concurrency is a project learning goal
- Can obscure task lifetime for developers primarily learning `async`/`await`
- More framework surface than the initial application requires

## Proposed decision

Choose **Option B** for the initial release.

- Define networking and persistence boundaries with `async` functions where asynchronous work is required.
- Isolate observable feature state to `@MainActor`.
- Prefer structured child tasks when work belongs to a parent operation.
- Retain explicit task handles only when work must be replaced or cancelled across method boundaries.
- Cancel obsolete search, event-loading, or seat-loading work.
- Protect against stale results with task ownership or request identity rather than assuming cancellation always wins.
- Prevent repeated UI actions while an equivalent operation is in flight.
- Treat reservation cancellation as potentially ambiguous after the network request begins; reconcile with the backend when necessary.
- Introduce an actor only for shared mutable state that is not already confined to the main actor.

## Rationale

This option makes Swift concurrency a real correctness concern rather than a résumé keyword. It provides concrete scenarios involving cancellation, out-of-order completion, actor isolation, and server reconciliation while keeping the architecture small enough to explain.

## Consequences

- Feature state types will have explicit actor-isolation expectations.
- Async dependencies must support controlled suspension and completion in tests.
- Cancellation errors must be distinguished from ordinary product failures where behavior differs.
- The UI may suppress duplicate actions, but the server must still provide idempotency and database enforcement.
- Code review must consider task ownership and lifetime, not only whether an `await` call compiles.
- Actors will be justified individually; their use is not a project-wide default.

## Validation

Before this decision is considered successfully implemented:

1. A controlled test proves that an older event response cannot replace a newer selection.
2. A controlled test proves that replacing a search cancels or safely ignores the previous result.
3. A repeated reservation action produces one logical client operation and one stable idempotency key.
4. A cancellation test covers the ambiguous case in which the server may have accepted the operation.
5. Observable UI-state mutations satisfy main-actor isolation.
6. No concurrency test requires a fixed-duration sleep.
7. The owner can explain why server correctness cannot be delegated to the Swift client.

## Revisit triggers

Reconsider this decision if:

- The application develops complex event streams that are materially clearer with Combine.
- A shared subsystem requires isolation that the initial feature boundaries cannot provide.
- Deployment targets constrain the selected concurrency APIs.
- Measurements reveal actor contention or task-lifetime problems.

## Owner review

Before changing this ADR to **Accepted**, answer:

1. Does main-actor feature state match the client architecture we intend to use?
2. Which operations should be cancelled when a screen disappears, and which must be reconciled instead?
3. Can we identify any shared mutable state that truly requires its own actor in the first release?
4. Are we comfortable using Combine only if a concrete stream problem later justifies it?

