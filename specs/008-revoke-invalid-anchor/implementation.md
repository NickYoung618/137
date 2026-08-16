# Implementation Log: Revoke Invalid A2 Short-Line Anchor

## Starting state

- Repository: `/home/ubuntu/disk/dzk/137-end-face-refactor-work`
- Starting HEAD: `461ef7caeef908cbe72bdfa77396634f61550bd8`
- Starting worktree: clean, detached at the same commit as `origin/main`
- Immutable core SHA-256:
  `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`
- The withdrawn A2 annotation was not loaded, parsed, tuned against, or used as
  acceptance evidence during this increment.

## Implementation result

- The shared LabelMe loader rejects the withdrawn fingerprint before JSON
  parsing or reference-image access.
- `MainHousingRegistrar` takes only a reference image and config. Reference
  selection uses supported-circle dominance and fails on insufficient margin.
- Existing short-line search and quality gates are byte-for-byte equal in
  value to the pre-increment v2 config; no threshold was lowered.
- Registration-only single and Manifest batch commands emit strict records,
  core/config/input fingerprints, hypotheses, transforms, checks and counts.
  They emit no measurement, candidate transition, or recovery fields.
- Real A2 19/30 candidate acceptance remains blocked pending corrected truth.

## Verification

- Targeted revocation/registration/diagnostic/schema suite: 18 passed.
- Full `unittest` discovery: 54 passed.
- `python -m compileall -q algorithms tools tests`: passed.
- `git diff --check`: passed.
- SpecKit analyze: initial core-provenance gap remediated; final review has no
  critical/high issues and 100% requirement-to-task coverage.
- Core source matches the pinned SHA and has no diff from starting HEAD.
- Candidate Git set contains no raw image, archive, generated JSONL, or file
  larger than 1 MiB.
