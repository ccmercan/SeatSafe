# ADR-013: Use lightweight SwiftUI feature models for the iOS client

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

Phase 2 needs an iOS client that loads event-seat availability and later supports
selection, holds, and reservation confirmation. As a learning portfolio, its structure
should be easy to follow and make asynchronous behavior straightforward to test.

## Options considered

### Option A: SwiftUI views, observable feature models, injected async services

Views render state and forward user actions. A focused `@Observable @MainActor` model
owns feature state and calls an injected async service protocol. The service performs I/O.

Advantages:

- Few layers, with clear responsibilities and seams for test doubles.
- Fits the initial app and ADR-002's structured-concurrency decision.
- Loading, success, and failure states are testable without UI automation.

Disadvantages:

- Feature models can grow too large unless responsibilities stay focused.
- Shared complex workflows may eventually need another abstraction.

### Option B: Layered MVVM with use cases and repositories

Advantages:

- Separates orchestration and data access for larger feature sets.
- Gives teams explicit places for reusable business operations.

Disadvantages:

- Adds abstractions before the app has demonstrated a need for them.
- More files and indirection make the first vertical slice harder to learn.

### Option C: A reducer/store architecture such as TCA

Advantages:

- Makes state transitions, effects, and test control explicit.
- Can help with many interacting features and complex navigation.

Disadvantages:

- Adds a third-party framework and a larger conceptual model.
- Unnecessary for the current scope and could obscure native Swift concurrency learning.

## Decision

Choose **Option A**. Use lightweight SwiftUI views, focused `@Observable @MainActor`
feature models, and injected async service protocols. Keep networking and response
decoding in the service implementation. Add layers only when a concrete responsibility
cannot remain clear within this structure.

## Consequences

- UI state is owned by main-actor-isolated feature models.
- Service protocols permit deterministic test doubles.
- Views do not construct URL requests or decode API responses.
- Feature models coordinate UI behavior but do not duplicate backend reservation rules.
- The first slice covers seat loading only; event discovery and reservation actions await
  their API contracts and later review.

## Validation

1. Unit tests exercise loading, success, empty, and failure states using injected services.
2. An iOS simulator build verifies the native target and iOS 17 deployment setting.
3. A service test verifies decoding of the existing seat-snapshot response contract.
4. A reviewer can trace a view action through the model to the service without hidden
   framework behavior.

## Owner review

Accepted by the project owner on 2026-09-22 as **Option A**.
