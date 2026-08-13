# Contract: `a-end-face-result/2`

- `technicalStatus` only reports whether the detector executed.
- On success, `result.valid` equals `result.localization.valid`.
- `result.measurementCompleteness.allValid` independently reports whether all core-qualified features are valid.
- `result.featureQuality.<feature>.coreValid` preserves the core status and cannot be promoted by policy.
- `result.measurements` preserves all core measurement and quality fields.
- The root machine-readable schema is `contracts/a-end-face-result.schema.json`.
