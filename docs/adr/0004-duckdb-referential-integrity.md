# ADR 0004 — Use application-level referential checks in the bootstrap warehouse

## Status
Accepted

## Context
DuckDB does not support cross-schema foreign keys, while the monorepo warehouse is intentionally namespaced (`meta`, `corpus`, `planning`, `execution`, `profiling`, `arch`).

## Decision
Keep the schema namespaces and remove cross-schema foreign key declarations from the bootstrap schema. Enforce referential integrity through command-layer checks and later warehouse QA jobs.

## Consequences
- `schema.sql` applies cleanly on a fresh DuckDB file.
- Logical relationships stay explicit in column names.
- Integrity checks move into code and regression tests during the bootstrap phase.
