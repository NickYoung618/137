# SpecKit Analyze: 006 A2 LabelMe Short-Line Reference

**Analyzed**: 2026-08-14
**Result**: no critical, high or medium consistency findings

## Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| FR-001/002/003 | `load_labelme_short_line_reference` | valid/missing/duplicate/type/point/bounds/dimension tests |
| FR-004 | catalog contains only paths, hashes, geometry and `imageDataIgnored` | embedded sentinel is absent from serialized catalog |
| FR-005 | adapter-only optional reference; `core.py` untouched | input immutability test and core SHA/source test |
| FR-006 | result/comparison/summary provenance carries reference mode, schema and hashes | JSON Schema tests and comparison rebuild test |
| FR-007 | existing candidate configuration and required gates are unchanged | blank, low contrast, competing peak, boundary and consistency tests |
| FR-008 | `tools/inspect_short_line_labelme.py` and catalog schema | CLI output and Schema tests |
| FR-009 | default desktop reference remains available | all pre-006 candidate/CLI tests pass |
| FR-010 | forced Manifest split and `--development-group` 20-frame gate | Manifest split and exact-group rejection tests; quickstart commands |

## Constitution check

- Core source remains immutable and SHA-gated.
- Core measurements, core quality, localization and completeness are not mutated.
- External images and LabelMe JSON remain outside Git; outputs contain hashes, not image bytes.
- Candidate stays fail-closed through the unchanged multi-evidence gates.
- The public result stays `a-end-face-result/3`; new provenance properties are optional so earlier v3 records remain schema-compatible.

## External acceptance gate

Mac must still run the frozen LabelMe reference on the complete 20-frame development sample and then on all held-out physical samples. Server synthetic recovery proves control flow and protection behavior, not A2 production accuracy. This is an external evidence dependency, not a specification inconsistency.
