# ADR-012: Set the minimum iOS deployment target to iOS 17

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

Phase 2 starts the native SwiftUI client. Its state model should support the accepted
ADR-002 decision to keep observable feature state on the main actor and use Swift
structured concurrency. The project also needs a deployment target that supports the
selected UI model without unnecessarily restricting the portfolio app to only the newest
iOS release.

The development machine has Xcode 26.4.1, Swift 6.3, and an iOS 26.4 Simulator runtime.
The locally available simulator can run the app, but it does not by itself validate
behavior on the minimum supported iOS version.

## Options considered

### Option A: iOS 17 minimum

Advantages:

- Supports SwiftUI's Observation integration and `@Observable` feature models.
- Allows the app to run on iOS 17 and later rather than only recent releases.
- Fits the small SwiftUI app without requiring older observation patterns.

Disadvantages:

- Newer APIs still need availability checks if used below their introduction version.
- The local simulator runtime is iOS 26.4, so minimum-version runtime testing needs a
  separate simulator runtime or CI configuration.

### Option B: iOS 18 minimum

Advantages:

- Narrows compatibility testing to a newer OS baseline.
- Retains the Observation-based SwiftUI model.

Disadvantages:

- No Phase 2 requirement currently depends on an iOS 18-only API.
- Excludes iOS 17 devices without a corresponding project benefit.

### Option C: iOS 26 minimum

Advantages:

- Matches the only iOS Simulator runtime currently installed on the development machine.
- Permits use of current platform APIs without older-OS compatibility checks.

Disadvantages:

- Makes the portfolio app needlessly specific to the newest OS generation.
- Weakens the value of testing compatibility and availability boundaries.

## Decision

Choose **Option A: iOS 17 minimum**.

Use iOS 17 as the deployment target. Use the installed Xcode 26.4.1 toolchain and iOS
26.4 Simulator for local builds and simulator tests. Do not claim that local testing on
iOS 26.4 proves runtime behavior on iOS 17; add minimum-runtime coverage when an iOS 17
runtime is available in the development or CI environment.

## Rationale

Apple's SwiftUI Observation support begins with iOS 17, so this target lets the project
use the modern observable feature-state approach selected in ADR-002. Choosing the
latest OS as the minimum would save compatibility work that this small app does not need
to avoid.

## Consequences

- The Xcode project must set `IPHONEOS_DEPLOYMENT_TARGET` to `17.0`.
- SwiftUI feature models may use Observation and `@MainActor` without an older-OS fallback.
- APIs newer than iOS 17 require availability checks or an explicit decision to raise the
  minimum deployment target.
- Local simulator runs validate against iOS 26.4 until an iOS 17 runtime is installed.

## Validation

Before treating the decision as implemented:

1. Confirm the Xcode project deployment target is iOS 17.0.
2. Build and run the app with the installed Xcode 26.4.1 toolchain.
3. Run client tests on the available iOS 26.4 Simulator.
4. Add iOS 17 runtime coverage when a matching simulator runtime is available; until then,
   document this as a validation limitation.

## Revisit triggers

Reconsider the target if:

- Product requirements depend on APIs unavailable in iOS 17.
- Measured user or portfolio needs justify dropping iOS 17 support.
- CI cannot reliably obtain a simulator runtime compatible with the chosen baseline.

## Owner review

Accepted by the project owner on 2026-09-22.
