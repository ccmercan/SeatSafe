# Learning and ownership plan

## Goal

The project owner should be able to reconstruct the system on a whiteboard, explain every consequential decision, diagnose failures, and change the implementation without depending on generated explanations.

## Learning loop

For each milestone:

1. **Explain:** Define the problem and unfamiliar concepts in plain language.
2. **Compare:** Evaluate realistic alternatives and tradeoffs.
3. **Decide:** The owner accepts or changes the recommendation.
4. **Build:** Implement the smallest useful vertical slice.
5. **Verify:** Run tests and inspect results, including at least one intentional failure when safe.
6. **Reflect:** Record limitations and what would change at larger scale.
7. **Defend:** Practice a two-minute answer and likely follow-up questions.

## Ownership checkpoints

At the end of a milestone, the owner should be able to answer:

- What problem did this milestone solve?
- What alternatives did we consider?
- Why did we select this design?
- Where is the behavior implemented?
- Which tests provide confidence, and why are they at those layers?
- What could still fail?
- What evidence did CI or local execution produce?
- What would need to change in a production-scale system?

If these answers are unclear, pause new implementation and close the knowledge gap.

## Topics to own deeply

- The seat and hold state machines
- Database uniqueness, transactions, and concurrency behavior
- Idempotency and safe retries
- Client state management and dependency injection
- Swift structured concurrency, task lifetime, and cancellation propagation
- Main-actor isolation versus actor-isolated shared state
- Stale-response prevention and ambiguous server outcomes
- Online versus cached data semantics
- Test pyramid and risk-based coverage choices
- Deterministic test data
- UI synchronization and flake prevention
- CI quality gates and diagnostic artifacts
- Accessibility as product quality

## Topics to recognize without memorizing

- Framework boilerplate and generated configuration
- Exact command-line flags
- Generated project metadata
- Library APIs that can be looked up safely

## Evidence notebook

For each milestone, add a short entry to `docs/interview-project-defense.md` containing:

- One accepted decision
- One difficult failure or uncertainty
- One measured result
- One limitation
- One concise interview answer

Do not prewrite success stories for work that has not happened.

## Pairing rules for Codex

- Ask the owner to choose only when alternatives materially change the project.
- Explain important code before or alongside its introduction.
- Keep changes small enough to review.
- Provide commands the owner can rerun.
- Use comments to clarify non-obvious intent, not ordinary syntax.
- Prefer questions that test understanding after evidence exists, rather than trivia before implementation.
