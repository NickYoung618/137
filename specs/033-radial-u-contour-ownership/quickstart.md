# Quickstart: Validate Position-Independent Radial U-Contour Ownership

## Prerequisites

- Use branch `codex/033-radial-u-contour-ownership`.
- Keep A2 and all review evidence outside Git and verify their recorded hashes.
- Do not inspect sealed part-006 or enable PLC/HMI output.

## Frozen Observed Baseline

- Baseline commit: `feede595787b0fa741c8bafd42ba530cda5fe42b`
- Baseline portable config SHA-256: `74baa2062db6724d333e6d529717036a6c61add28019fc5f0a9329c51b386e85`
- Baseline 700-result SHA-256: `b83865001cd04a6ea36d938de6b1d3ad9cf8e0e8873b6791556a62c3c4dbfe3b`
- Complete-visible controls: `bad:0101`, `0103-0109`, `0111`, `0113-0115`, `0119-0120`; `normal:0254`.
- Mixed/occluded controls: `bad:0001-0020`; `normal:0179`, `0226`, `0227`, `0237`, `0239`, `0241`, `0242`, `0283-0302`, `0403-0422`.
- All IDs above use the `a2-full` manifest group. They are observed regression controls, not unseen truth.

## Locked Threshold Statement

No ambiguity, recognition, refinement, polar-quality, fixture or source-consistency threshold is changed. The radial envelope is derived per candidate from its measured half-width plus the already configured, unchanged intersection tolerance.

## Validation Order

1. Run synthetic full-rotation U-contour and tangential fixture-edge tests, then focused ownership, source-adjudication, adapter, contract and profile tests.
2. Run the full available test suite and all root JSON schemas.
3. Materialize the new portable profile without changing any prior threshold.
4. Replay the immutable 15 complete-visible and 67 mixed/occluded review index.
5. Replay all 700 observed images and compare transitions against commit `feede595787b0fa741c8bafd42ba530cda5fe42b`.
6. Repeat one released and one occluded case five times with one reused adapter.
7. Measure uncontented warm P95 on 5472×3648 images.

## Expected Outcomes

- 15/15 reviewed complete-visible cases become valid through `radial_u_contour_ownership`.
- 67/67 reviewed mixed/occluded cases remain invalid with full safety nulls.
- No previous valid case becomes invalid.
- Original source measurements and thresholds remain unchanged.
- Warm P95 stays at or below 2.5 seconds.
- No production accuracy or PLC authorization is claimed before a physically separate new-part validation.

## Executed Pre-Replay Gates

- Focused ownership/config/profile/summary tests: 90/90 PASS.
- Focused adapter safety tests: 3/3 PASS.
- Full available suite: 617/617 PASS in 123.878 seconds.
- Root JSON Schema Draft 2020-12 checks: 64/64 PASS.
- `git diff --check` and `git diff --cached --check`: PASS.
- Final portable v8 config SHA-256: `85dbf8c71e5fc8c9340ad3aff8b5c90272bffe782ee9c441d0b6fd1ccd2ac3a1`.
- Profile v8 explicitly disables the superseded non-authoritative local-second-wall scan; profiles v7 and earlier remain unchanged.
- A first replay attempt was explicitly discarded after code changed during execution; no result from that mixed-code attempt is accepted as evidence.

## Frozen Observed Replay

- Evidence commit: `24c8015a82235dc933a973327b4876b0c971bd74`.
- Final result: 700 total, 633 valid and 67 invalid.
- Transition from the frozen v7 baseline: 618 valid stayed valid, 15 reviewed complete-visible cases changed from invalid to valid, and 67 reviewed mixed/occluded cases stayed invalid.
- All 15 recovered cases use `radial_u_contour_ownership`; all 67 mixed/occluded controls remain fail-closed with every guidance/PLC value null and PLC execution non-authoritative.
- No previously valid result regressed. The superseded local-second-wall diagnostic executed zero times in profile v8.
- Final result SHA-256: `4c24b08e62019eb1b79988aa08a3effdd2e23838628a264d39caf412d4b605ef`.
- Validation report SHA-256: `d4b1702bc2f83212ef8cfc83b5078ceb67cd98e6d5e4d03f60895a4a46254726`.
- Validation evidence: `/home/ubuntu/slot-pose-private-data/A2-700-observed-034-diagnostic-20260820/run-003-frozen-24c8015/validation-report.json`.

## Warm Performance and Repeatability

- One adapter was reused on one accepted case and one complex occluded case, with one discarded warmup and five measured repeats per path on CPU 1 while the competing compiler process remained on CPU 0.
- Combined wall-clock P50/P95/max: `1246.054 / 1290.734 / 1295.273 ms`, passing the `2500 ms` gate.
- Accepted-path P95: `1293.256 ms`; occluded-path P95: `1211.848 ms`.
- Both paths had exactly one non-timing result signature across five repeats; all accepted-path results stayed valid and all occluded-path results stayed invalid.
- Each measured result used one adapter estimate and one runtime image load; the superseded local scan executed zero times.
- Performance report SHA-256: `d3663fabd23cb2069bc72b5d8306f8f993f69f966e612f7c8a51e999f5744db6`.
- Performance evidence: `/home/ubuntu/slot-pose-private-data/A2-700-observed-034-diagnostic-20260820/run-003-frozen-24c8015/performance-report.json`.

These results are observed regression evidence only. Physically separate new-part validation remains mandatory before any production accuracy or PLC claim.

## Final Convergence Gate

- Added an explicit five-repeat true-ambiguity integration regression; all five non-timing diagnostics and outputs are identical and remain fail-closed.
- Final full available suite after convergence: 617/617 PASS in 124.841 seconds.
- Final root JSON Schema Draft 2020-12 checks: 64/64 PASS.
- Final `git diff --check` and `git diff --cached --check`: PASS.
- SpecKit convergence checked 19 functional requirements, 10 success criteria, 9 acceptance scenarios, 9 plan decisions and 5 constitution principles; no remaining implementation gap was found.
