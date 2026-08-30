# Product

Status: DRAFT — NOT YET ACCEPTED

This file is the durable, authoritative representation of what the owner intends the product to become. During discovery, update it incrementally as meaningful decisions are made. Preserve decisions and intent, not chat transcripts.

The required core sections below must remain recognizable because Roach validates them before product acceptance. Add project-specific sections when they genuinely improve clarity: for example Design Pillars and Core Gameplay Loop for a game, or User Roles and Data & Privacy for a business application.

## Vision

Describe the product in plain language: what it is, why it should exist, and the experience or outcome the owner cares about most.

## Goals

- Replace with concrete goals discovered with the owner.

## Non-Goals

- Record important scope boundaries so future workers do not silently expand the product.

## Users / Audience

Describe the primary user, player, operator, or audience and any materially different roles.

## Core Experience

Describe the most important journeys, workflows, interactions, or gameplay loop in user-centered language.

## Requirements

Define **current accepted scope** with stable IDs. Functional requirements use `FR-###`; quality/non-functional requirements use `QR-###`.

Examples only — replace or remove these during discovery:

- **FR-001**: The product MUST provide its primary user journey end to end.
- **QR-001**: The product MUST meet a measurable quality expectation appropriate to its domain.

Rules:

- keep each active requirement testable enough to plan and verify;
- do not create requirements for speculative future ideas;
- do not recycle an old requirement ID for a different meaning after product intent changes;
- when a requirement is retired, remove it from this active Requirements section and preserve important rationale in Git/DECISIONS or an optional Retired/Changed section; completed task history may still reference the old ID.

## Constraints

Record only constraints that materially affect the product or implementation: target platforms, privacy expectations, budget/cost boundaries, required integrations, offline behavior, accessibility, performance, or similar.

## Success Criteria

Define how the owner and future workers will know the product is succeeding. Prefer observable or measurable outcomes over adjectives such as "fast", "intuitive", or "robust".

## Open Questions

Track unresolved questions that could materially change product behavior, acceptance, scope, architecture, or validation. Remove questions when resolved and encode the answer in the appropriate section. A non-blocking question may remain if it is clearly identified as non-blocking.

## Future / Possibilities

Capture attractive ideas that are explicitly not committed scope yet. These do not automatically generate requirements or tasks.
