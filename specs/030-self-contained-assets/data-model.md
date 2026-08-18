# Data Model: Self-Contained Slot-Pose Assets

## Portable path mode

- `legacy_asset.path_mode`: `legacy` (default, preserving historical behavior) or `config_relative_v1`.
- In `config_relative_v1`, `annotation_path` and `reference_path` are relative to the directory containing `config.json`.
- `source_path` follows the same rule only for `external_file`; portable production bundles require `bundled_module` and therefore omit it.
- Loaded in-memory paths are canonical absolute strings so downstream adapters remain unchanged.

## Portable bundle manifest

- `schemaVersion`: constant `slot-pose-portable-bundle/1`.
- `bundleId`: stable non-empty deployment identifier.
- `algorithm`: `branch`, lowercase 40-character `commit`, bundled module name and source SHA-256.
- `configuration`: path, source config SHA-256, portable config SHA-256, effective config SHA-256.
- `files`: exactly the required bundle payload entries, each with:
  - `path`: unique confined POSIX relative path.
  - `role`: one of `runtime_config`, `annotation`, `reference_image`, `operator_instructions`.
  - `sizeBytes`: non-negative integer.
  - `sha256`: lowercase SHA-256.
- `archive`: deterministic format/version metadata; the archive hash is reported beside the artifact rather than recursively embedded.

## State transitions

1. `source_verified`: reviewed config loads and all declared source bytes match.
2. `staged`: required files copied byte-for-byte into a new external directory.
3. `manifested`: config and payload entries recorded; no external paths.
4. `verified`: independent verifier confirms structure, hashes, config semantics and effective identity.
5. `archived`: deterministic archive emitted and hashed.

Any validation failure terminates without replacing an existing artifact.

## Invariants

- No bundle-relative path escapes the extraction root.
- Manifest and `SHA256SUMS` enumerate the same immutable payload.
- The annotation's `imagePath` basename equals the packaged reference basename.
- Portable and source effective configuration hashes match.
- Bundle building changes deployment representation only, never detector/pose values.
