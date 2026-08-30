# Product

Status: DRAFT — RECOVERING INTENT FROM AN EXISTING PROJECT

This project existed before Roach did. This file is being reconstructed from
what is already built plus what the owner now wants, and the two are not the
same thing.

**The job during this first discovery cycle is to separate them.** Read the
code, the README, the commit history, and any issues, then draft each section
below. Present it to the owner as a summary they can correct — not as a
questionnaire. They already know what their project is; you are checking that
you do, and finding out what they want next.

Three distinctions worth getting right:

- **What the project does** versus **what it was supposed to do.** Where they
  differ, ask which one is now correct.
- **Deliberate behaviour** versus **accidents nobody has removed.** Do not
  write an accident into a requirement.
- **Kept scope** versus **abandoned scope.** Half-finished features are common;
  ask before enshrining or deleting them.

Delete this preamble once the sections below are real.

## Vision

What this product is, why it exists, and the outcome the owner cares about most
now. Written from the owner's perspective, not the code's.

## Goals

- Replace with the outcomes that matter from here forward, not a history of
  what was already built.

## Non-Goals

- Record scope the owner has deliberately decided against, including things the
  codebase already gestures at but should not become.

## Users / Audience

Who actually uses this, and any materially different roles.

## Core Experience

The journeys that matter most, described the way a user would describe them.

## Requirements

Current accepted scope with stable IDs: `FR-###` functional, `QR-###`
quality. Declare each on its own line — a list item, a table row, or a heading.

Existing behaviour the owner wants **kept** belongs here as a requirement, even
though it is already built. That is what makes the existing codebase traceable
to current intent rather than invisible to it. Planning covers each one with a
done verification record and concise evidence rather than inventing
implementation work that has already happened.

Existing behaviour the owner is indifferent to does **not** need a requirement.
Do not manufacture coverage for every function that happens to exist.

- **FR-001**: Replace with something this product must do, that it may or may
  not already do.
- **QR-001**: Replace with a measurable quality expectation appropriate to the
  domain.

Rules:

- keep each active requirement testable enough to plan and verify;
- do not create requirements for speculative future ideas;
- do not recycle a retired ID for a different meaning;
- when a requirement is retired, remove it here and preserve the rationale in
  Git or DECISIONS.

## Constraints

Constraints that materially bind the work: target platforms, existing stack and
why it cannot change cheaply, data that must not break, users already relying
on current behaviour, privacy or compliance obligations, budget.

For an existing project, the most important constraints are usually the ones
already committed to — a database schema in production, a published API, a
platform the users are on.

## Success Criteria

How the owner and future workers will know this is succeeding from here.
Observable or measurable, not adjectives.

## Open Questions

Unresolved questions that could materially change behaviour, scope, or
architecture. For an adopted project this usually includes anything found in
the code that nobody can explain.

## Known Debt

Optional but usually worth keeping for an adopted project: things that are
wrong and known to be wrong, so a fresh worker does not mistake them for intent
or quietly "fix" something load-bearing.

## Future / Possibilities

Attractive ideas that are explicitly not committed scope. These generate no
requirements and no tasks.
