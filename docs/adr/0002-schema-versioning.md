# ADR 0002 — Version the warehouse schema explicitly

## Status
Accepted

## Decision
All DB initialization goes through `schema.sql` plus a `meta.schema_registry` row so runs can be tied to a schema version.
