# Implementation Log: Registration Stability Statistics

## Starting state

- Starting HEAD and `origin/main`:
  `6a0d5228f0b24025fae197dc6d408e93a9fbd120`
- Starting tracked worktree: clean; only the new feature 009 specification was
  untracked after the SpecKit design phases.
- Immutable core SHA-256:
  `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`
- `.gitignore` already covers Python caches, outputs, JSONL, raw/private data,
  archives, inspection images, and large LabelMe naming patterns; no change was
  needed.
- The withdrawn annotation is neither opened nor consumed by this feature.
  Its existing fingerprint rejection remains part of the shared loader.

## Implementation checkpoints

- Red phase 1: the test module failed because linear/circular/stability helpers
  did not exist.
- Red phase 2: all statistical tests passed while the v2 Schema test failed
  because its repository contract did not yet exist.
- Targeted registration diagnostics: 9/9 passed after implementation.
- Full unit test discovery: 59/59 passed.
- `compileall`, CLI help, JSON parsing, four Schema meta-validations, and
  `git diff --check`: passed.
- SpecKit analyze initially found the Constitution-required external reference
  smoke missing from tasks. T016 was added and the final analysis reports 100%
  FR/SC-to-task coverage with no remaining issue.
- Registration-only external smoke used the accessible representative image as
  both reference and target, passed technical execution and registration with
  scale `1.0`, rotation `0.0°`, and `image_circle_dominance` selection. It did
  not load LabelMe and is not 19/30 or 25-frame performance evidence.
- Immutable core SHA remains
  `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`.
  Core, registration/candidate algorithms, candidate config, search gates, and
  legacy output paths have no diff from starting HEAD.
- Candidate Git set contains no raw image, archive, generated JSONL, forbidden
  candidate/measurement status field, or file over 1 MiB.
- Mac registration-only command is documented in `quickstart.md`; generated
  external values are still pending and no real-series stability claim is made.
