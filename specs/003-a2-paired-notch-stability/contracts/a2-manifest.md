# A2 External Manifest Contract

The manifest remains JSON and uses only paths relative to the user-supplied data root. Each image record adds:

- `datasetClass`: `normal` or `bad`.
- `sampleId`: physical sample identifier; required for formal split validation.
- `conditionId`: acquisition/truth-angle group from a capture log, timestamp mapping, or explicit mapping.
- `captureTimestamp` and/or `captureSequence`: optional grouping evidence.
- `repeatIndex`: sequence within one confirmed condition.
- `split`: `development`, `tuning`, `validation`, `acceptance`, or `unassigned`.

The tool must not infer 25 groups of 20 merely from 500 files. When grouping metadata is absent, it emits
`unassigned`/null metadata and validation reports `INCOMPLETE` instead of manufacturing groups.

The validator checks safe relative paths, bytes/hash/image metadata, unique IDs and paths, group repeat indices,
physical-sample split isolation, and consistency with the truth CSV.
