# Angle Truth CSV Contract

Required columns:

```text
image_sha256,truth_valid,truth_angle_deg,truth_source,calibration_id,
sample,condition,repeat,split,dataset_class
```

Rules:

- `image_sha256` joins exactly one manifest image.
- `truth_valid=true` requires a finite `truth_angle_deg` in `[-180,180)`, a truth source, and a calibration ID.
- `truth_valid=false` requires an empty `truth_angle_deg` and represents a bad/negative image.
- `sample`, `condition`, `repeat`, `split`, and `dataset_class` must match the manifest.
- Duplicate hashes, unknown hashes, missing normal-image truth, and grouping mismatches block formal evaluation.
- Algorithm output is never a valid truth source.
