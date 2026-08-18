# Feature Specification: Self-Contained Slot-Pose Assets

**Feature Branch**: `030-self-contained-assets`

**Created**: 2026-08-18

**Status**: Draft

**Input**: User description: "Mac deployment must be fully independent and must not search external gyj/yyh or server absolute paths for locked runtime assets."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Bundle Mac Replay (Priority: P1)

As the operator, I can pull the reviewed algorithm revision, download one deployment archive, extract it anywhere on macOS, and run A2 replay without creating Linux paths or retrieving any additional runtime file.

**Why this priority**: The reviewed configuration cannot initialize on macOS because it names two Linux-only asset paths, so no trustworthy 700-image replay can begin.

**Independent Test**: Copy the archive to a clean temporary directory whose absolute path differs from the build host, remove access to source asset locations, load its configuration, and run a representative real image successfully.

**Acceptance Scenarios**:

1. **Given** the algorithm checkout and the single deployment archive, **When** the archive is extracted anywhere on Mac, **Then** initialization requires no gyj, yyh, `/home/ubuntu`, or other out-of-bundle asset path.
2. **Given** the bundle moved to another directory and an unrelated current working directory, **When** it is loaded, **Then** its locked assets still resolve and verify.
3. **Given** a missing or modified bundled asset, **When** initialization or re-verification occurs, **Then** it fails closed with `ASSET_MISMATCH` before inference.

---

### User Story 2 - Auditable Portable Package (Priority: P2)

As a reviewer, I can verify exactly which configuration and immutable assets are in the archive, their sizes and hashes, and that deployed behavior is identical to the reviewed server configuration apart from physical location and deployment identity.

**Why this priority**: Portability must not weaken source provenance, hash locking, or substitution detection.

**Independent Test**: Validate the manifest and checksum list, then compare effective configuration identity and replay results with the reviewed 029 configuration.

**Acceptance Scenarios**:

1. **Given** a built archive, **When** its manifest is validated, **Then** every required file has a relative path, role, byte size, and matching SHA-256 and no source-host absolute path is present.
2. **Given** reviewed and portable configurations, **When** effective identities are computed, **Then** their hashes are identical.
3. **Given** the frozen 140-image observed-development set, **When** both configurations replay it, **Then** validity, error/stage, non-timing pose outputs, and algorithm diagnostics are equivalent under a documented comparison allowlist.

---

### User Story 3 - Backward-Compatible Existing Deployments (Priority: P3)

As an existing Linux deployment owner, I can continue loading historical absolute-path configurations unchanged while portable mode remains explicit and strictly validated.

**Why this priority**: Portable deployment must not silently reinterpret reviewed configurations.

**Independent Test**: Load existing absolute-path fixtures and confirm their semantics and effective identity remain unchanged.

**Acceptance Scenarios**:

1. **Given** a legacy configuration without a path-mode declaration, **When** loaded, **Then** paths retain historical absolute-path semantics.
2. **Given** a portable configuration containing an absolute path, parent traversal, or bundle escape, **When** loaded, **Then** it is rejected before adapter construction.

### Edge Cases

- The process current working directory is outside the extracted bundle.
- The bundle directory contains spaces or non-ASCII characters.
- A relative path uses `..`, POSIX absolute form, or a Windows drive prefix.
- A bundled asset symlink resolves outside the bundle.
- The archive is rebuilt from byte-identical inputs on the same revision.
- An output target exists or lies inside the Git working tree.
- The annotation internally names the reference image and must not retain an external dependency.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support explicit, versioned configuration-relative asset paths while preserving historical path behavior as the default.
- **FR-002**: Relative assets MUST resolve from the configuration file location, never the process current working directory.
- **FR-003**: Portable paths MUST be non-empty local relative paths confined to the bundle root; absolute paths, Windows drive paths, parent traversal, and resolved escape MUST be rejected.
- **FR-004**: The portable configuration MUST use the repository-bundled algorithm module and retain reviewed source, annotation, and reference SHA-256 locks.
- **FR-005**: Missing, unreadable, substituted, or hash-mismatched files MUST fail closed before inference, including long-lived adapter re-verification.
- **FR-006**: Packaging MUST produce one archive containing configuration, annotation, reference image, manifest, checksum list, and operator instructions.
- **FR-007**: Portable configuration and manifest paths MUST be bundle-relative and disclose no gyj/yyh or absolute source-host path.
- **FR-008**: The manifest MUST record schema version, bundle ID, algorithm branch/commit, source and portable config hashes, effective config hash, and every file's role, size, and SHA-256.
- **FR-009**: Packaging MUST verify source hashes before copying and verify the completed bundle before archiving.
- **FR-010**: Packaging MUST refuse silent overwrite and refuse generated deployment data inside the Git worktree.
- **FR-011**: Byte-identical inputs and the same declared revision MUST produce byte-identical package contents and archive bytes.
- **FR-012**: Relocating assets MUST NOT change effective configuration identity.
- **FR-013**: Portable and reviewed configurations MUST have equivalent non-timing outcomes on the frozen 140-image set; no thresholds or algorithm decisions may change.
- **FR-014**: The package MUST remain usable after original server asset locations become inaccessible.
- **FR-015**: The packaged annotation MUST reference the packaged reference image without weakening either hash check.
- **FR-016**: This feature MUST NOT merge main, modify PLC/HMI, read sealed part-006, or claim accuracy improvement.
- **FR-017**: Large/private assets and archives MUST stay outside Git; only implementation, schemas, tests, and documentation belong in the repository.

### Key Entities

- **Portable Runtime Configuration**: A reviewed configuration using explicit config-relative locked files with unchanged effective behavior identity.
- **Portable Bundle Manifest**: Versioned provenance and integrity record for one archive.
- **Bundle File Entry**: A relative path with role, size, and SHA-256.
- **Deployment Archive**: The single transferable non-code runtime artifact used with the reviewed checkout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean Mac checkout plus one archive initializes and replays with zero access to gyj, yyh, `/home/ubuntu`, or other non-bundle runtime assets.
- **SC-002**: Moving the bundle and changing current working directory preserves effective config hash and replay outcome.
- **SC-003**: 100% of files pass manifest/checksum verification; a missing or one-byte-tampered required file is rejected before inference.
- **SC-004**: Portable and reviewed 029 effective configuration SHA-256 values exactly match.
- **SC-005**: All 140 frozen images match for validity, error/stage, pose values, and non-timing diagnostics under an explicit allowlist.
- **SC-006**: Existing absolute-path and focused runtime tests remain passing.
- **SC-007**: Two identical builds have identical archive SHA-256 values.
- **SC-008**: Generated assets/archive remain Git-external and repository status is clean after commit.

## Assumptions

- Mac has a compatible Python environment and the specified Git checkout; this packages runtime assets, not a Python interpreter or application binary.
- Reviewed 029 thresholds and algorithm behavior remain frozen.
- Existing annotation/reference bytes are authorized for controlled transfer to the operator's Mac.
- The operator extracts the archive rather than editing files inside it.
