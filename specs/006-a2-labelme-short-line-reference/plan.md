# Implementation Plan: A2 LabelMe Short-Line Reference

## Technical context

- Python 3.12, NumPy, Pillow, unittest, JSON Schema.
- Immutable core: `algorithms/end_face/core.py` at the pinned SHA-256.
- Existing adapter: `EndFaceInspector`; existing candidate: `ShortLineCandidateEvaluator`.
- External assets: A2 images, LabelMe JSON and its referenced image.

## Design

1. Add a strict LabelMe loader in the candidate module. It returns only validated 19/30 line metadata, a smoothed grayscale/gradient image and SHA provenance; it never emits `imageData`.
2. Keep desktop core models for result keys and baseline geometry. When supplied, use external LabelMe shapes and image gradient only for the candidate template patch.
3. Add `--short-line-labelme-reference` to the single-image, batch and compare CLIs.
4. Add an annotation inspection CLI producing `a-end-face-labelme-short-line-reference/1` JSON.
5. Extend result/comparison provenance schemas with nullable external-reference fields while preserving v3 result semantics.
6. Test valid/invalid annotations, external-template recovery, input immutability, CLI plumbing and schemas.

## Gates

- Unit/integration suite.
- JSON Schema suite.
- `core.py` SHA equals pinned desktop source.
- no tracked image/archive/JSONL or file larger than 5 MiB.
- Spec analysis finds no requirement/implementation contradictions.
