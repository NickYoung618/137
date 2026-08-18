# Phase 0 Research: Self-Contained Slot-Pose Assets

## Decision 1 — Explicit config-relative mode at the config boundary

**Decision**: Add `legacy_asset.path_mode: config_relative_v1`; absence means `legacy` and preserves the existing `Path.resolve()` behavior. Resolve portable file fields relative to the configuration's directory during `load_config`.

**Rationale**: The loader knows the config origin and is the single boundary shared by CLIs and adapters. Adapter code can continue receiving canonical absolute paths and preserve existing hash checks.

**Alternatives considered**:

- Change working directory before replay: rejected because it is implicit and brittle.
- Expand environment variables: rejected because Mac would still need external setup and path identity would be ambiguous.
- Resolve inside the adapter: rejected because other config consumers would see different semantics.

## Decision 2 — Confinement before file access

**Decision**: Portable paths must be lexical relatives without `..`, POSIX roots, Windows drive/UNC prefixes, and their resolved target must remain under the real config directory. Existing symlinks escaping the root are rejected.

**Rationale**: A self-contained bundle must not silently regain external dependencies or disclose/read arbitrary host files.

**Alternatives considered**:

- Permit `../shared`: rejected because it violates one-bundle independence.
- Hash-only trust of external paths: rejected because correct bytes at packaging time do not guarantee later independence.

## Decision 3 — One deterministic data archive, code stays in Git

**Decision**: Build a deterministic `.tar.gz` containing config, two assets, manifest, checksum list, and instructions. The algorithm implementation remains in the specified Git revision.

**Rationale**: The user already pulls the algorithm branch. Keeping large/private BMP data outside Git complies with the Constitution while reducing Mac setup to one additional download.

**Alternatives considered**:

- Commit BMP/annotation assets: rejected by large/private-data governance.
- Package Python/runtime binaries: rejected as unnecessary scope and cross-platform complexity.
- Ask Mac to fetch two server paths separately: rejected because that is the reported defect.

## Decision 4 — Preserve byte identity and effective identity

**Decision**: Copy annotation/reference byte-for-byte. Require the annotation's internal `imagePath` to resolve by basename to the packaged reference; reject instead of rewriting. Continue excluding machine paths/config ID from effective identity.

**Rationale**: Rewriting annotation would change its locked SHA and therefore effective behavior identity. The reviewed annotation currently uses a colocated basename, so copying both files together is sufficient.

**Alternatives considered**:

- Rewrite annotation and accept a new effective hash: rejected because this is deployment-only work.
- Remove annotation hash from effective identity: rejected because it weakens provenance globally.

## Decision 5 — Separate build and verify commands

**Decision**: Builder performs pre/post verification and creates the archive; verifier independently checks archive/directory structure, manifest schema-compatible shape, checksums, path confinement, and effective config hash.

**Rationale**: An operator/reviewer needs a read-only verification path that does not trust builder success.

**Alternatives considered**:

- Shell-only checksum instructions: rejected because they cannot validate config semantics or path confinement consistently on Mac.

## Decision 6 — Equivalence, not accuracy, is the real-data gate

**Decision**: Replay frozen 140 observed inputs with both configs and compare results after a narrow allowlist for time and deployment identity fields.

**Rationale**: No algorithm behavior changes are authorized, and these 140 are observed diagnostic data rather than unseen accuracy acceptance data.

**Alternatives considered**:

- Claim the prior 99/41 outcome as sufficient: rejected because relocation could still alter reference loading.
- Retune failures during this feature: rejected as scope expansion and data leakage.
