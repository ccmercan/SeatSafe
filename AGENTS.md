# SeatSafe collaboration rules

## Purpose

SeatSafe is both a working product and a learning portfolio project for Software Development Engineer in Test and Quality Engineering roles. The repository must demonstrate sound software construction, quality strategy, automation architecture, CI, debugging, and technical communication.

The user is the project owner. Optimize for their ability to understand, explain, modify, and defend the system—not merely for speed of code generation.

## Decision protocol

Before making a consequential architectural or quality-engineering decision:

1. State the problem and constraints.
2. Present two or three realistic options.
3. Compare their tradeoffs in plain language.
4. Recommend one option and explain why it fits this project.
5. Ask for the user's decision when alternatives would materially change the project.
6. Record accepted decisions in `docs/decisions/` using the ADR format.
7. Define how the decision will be validated.

Consequential decisions include architecture boundaries, data ownership, database consistency, concurrency control, dependency injection, local persistence, API contracts, test strategy, test data management, CI gates, third-party services, and security boundaries.

Routine implementation details may proceed without a separate decision review when they follow an accepted ADR and do not materially alter scope or tradeoffs.

## Teaching and ownership

- Explain consequential decisions in two layers: first a junior-friendly mental model in plain language, then the precise technical mechanism and terminology.
- Define unfamiliar terms when they first appear, and include a small concrete example when it improves understanding.
- Explain the reasoning before introducing a new pattern or abstraction.
- Prefer the smallest implementation that exposes the real engineering concept.
- Do not hide important behavior behind unexplained generated code.
- When adding code, identify which requirement it satisfies and which test will validate it.
- At the end of each milestone, summarize what changed, why, known limitations, and how the user can demonstrate it.
- Maintain `docs/interview-project-defense.md` with answers grounded in work actually completed.
- Never invent project metrics. Record measured values and the command or CI run that produced them.

## Engineering principles

- Keep the product modest and the quality engineering deep.
- Favor deterministic tests, injectable boundaries, explicit state, and observable failures.
- Test behavior at the lowest useful layer; reserve UI automation for critical user journeys.
- Do not mask flaky tests with blind retries.
- Keep test-only controls unavailable in production configuration.
- Preserve traceability among requirements, risks, tests, defects, and release criteria.
- Keep the repository runnable locally with documented commands.

## Workflow

For each milestone:

1. Review the relevant requirements and risks.
2. Resolve and record any new consequential decisions.
3. Implement one vertical slice.
4. Add automated validation at appropriate layers.
5. Run the relevant checks and retain useful evidence.
6. Review the result with the user before expanding scope.

Do not begin broad feature implementation until the user has reviewed the foundation documents and accepted or revised ADR-001.
