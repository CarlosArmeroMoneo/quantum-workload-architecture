# QPU Adapter Surface

Status: roadmap.

The QPU adapter surface is an optional future lane for recording submitted quantum hardware jobs and returned evidence. It is not implemented in the current repository.

## Intent

- Normalize job metadata and result payloads into the Atlas evidence model.
- Preserve provider, backend, queue, shot, calibration, and result provenance.
- Keep QPU evidence separate from exact tensor-network simulation evidence.

## Non-Claims

- No QPU provider adapter is implemented today.
- No QPU execution evidence is pinned today.
- QPU access remains optional and future-facing.
