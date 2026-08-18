# Implementation Plan: Self-Contained Slot-Pose Assets

**Branch**: `030-self-contained-assets` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/030-self-contained-assets/spec.md`

## Summary

Add an explicit `config_relative_v1` asset path mode while keeping omitted/`legacy` mode byte-compatible, resolve and confine portable paths at configuration load time, and provide a deterministic Git-external bundle builder. The bundle contains the reviewed configuration derivative, annotation, reference BMP, manifest, checksums, and Mac instructions. Algorithm thresholds, coordinate/pose contracts, PLC behavior, and effective configuration identity remain unchanged.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Python standard library, NumPy 2.4.4, Pillow 12.2.0; jsonschema only in validation environment

**Storage**: Git-tracked JSON schemas/docs/code plus Git-external immutable deployment archive

**Testing**: `unittest`, Draft 2020-12 JSON Schema validation, real-image replay comparison

**Target Platform**: Linux packaging/validation host and macOS replay host

**Project Type**: Python library and CLI tools

**Performance Goals**: No measurable inference overhead after adapter construction; package build is offline and bounded by two asset copies

**Constraints**: No algorithm/threshold changes, no main merge, no PLC/HMI, no sealed part-006, no large/private assets in Git; fail closed on asset/path integrity failure

**Scale/Scope**: Two locked runtime assets, one portable config, deterministic archive, focused tests, full frozen 140-image equivalence replay

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1.*

- **I — specification first**: spec has three independently testable stories, numbered requirements, and measurable outcomes; plan/tasks/tests retain traceability.
- **II — pose contract**: no coordinate frame, angle semantics, validity, or output contract changes; equivalence regression guards this invariant.
- **III — fail closed**: invalid paths and missing/tampered assets fail before inference; no stale or fabricated pose is emitted.
- **IV — provenance/reproducibility**: manifest, per-file hashes, source/effective configuration hashes, revision, deterministic archive, and external evidence location are mandatory.
- **V — modular/integrable**: path normalization stays in configuration loading, package construction stays in a standalone CLI, legacy absolute configs remain compatible.
- **Engineering constraints**: assets remain Git-external with manifest/checksums; no secrets or private host paths are written into the portable artifact.

Post-design re-check: PASS. The design introduces no pose convention, model, hardware, concurrency, or production output change.

## Design and Data Flow

```text
reviewed config + locked annotation/reference + reviewed Git revision
        │ verify declared SHA-256 and bundled-core identity
        ▼
deterministic bundle builder (Git-external output only)
        │
        ├── config.json (config_relative_v1)
        ├── assets/annotation.json
        ├── assets/reference.bmp
        ├── manifest.json
        ├── SHA256SUMS
        └── README.md
        ▼
single deterministic .tar.gz ──transfer/extract anywhere──► load_config
                                                           │ confine paths to config root
                                                           ▼
                                                   existing adapter hash gates
                                                           ▼
                                                   unchanged pose pipeline
```

The packaged annotation is rewritten only when its `imagePath` must point to the packaged reference basename. Its resulting SHA becomes the portable configuration's annotation lock; reference and algorithm source hashes remain reviewed. Effective identity would normally include the annotation hash, so to satisfy strict equality the reviewed annotation is first checked: if its existing `imagePath` is already the same basename, it is copied byte-for-byte. Packaging rejects any annotation that would require semantic/path rewriting for this v1 workflow.

## Project Structure

### Documentation (this feature)

```text
specs/030-self-contained-assets/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── portable-bundle-manifest.example.json
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/contract.py
contracts/slot-pose-config.schema.json
contracts/slot-pose-portable-bundle.schema.json
tools/build_slot_pose_portable_bundle.py
tools/verify_slot_pose_portable_bundle.py
tests/test_slot_pose_contract.py
tests/test_slot_pose_portable_bundle.py
config/README.md
```

**Structure Decision**: Extend the existing config contract and loader; isolate all filesystem mutation and archive handling in purpose-built tools. Runtime algorithm modules remain untouched.

## Test Strategy

- Unit/contract: legacy default semantics; config-relative relocation and CWD independence; POSIX/Windows absolute, traversal, symlink escape rejection; Unicode/spaces.
- Packaging: hash locks, manifest schema, no absolute/source path leakage, no overwrite/worktree output, missing/tampered asset rejection, deterministic rebuild.
- Adapter integration: initialize from a relocated temporary bundle using bundled core and locked test assets; re-verification fails after tamper.
- Real replay: compare frozen 140 inputs between reviewed 029 and portable configurations; ignore only `createdAtUtc`, `algorithm.configSha256`, and recursively named `elapsedMs`/`timingMs` fields. Require every other field—including config ID, validity/error/stage and all pose/circle/groove diagnostics—to match exactly.
- Repository gates: focused tests, full relevant test suite, all root schemas, `git diff --check`, clean status after commit.

## Complexity Tracking

No Constitution violations.
