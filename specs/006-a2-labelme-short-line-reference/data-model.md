# Data Model

## LabelMeShortLineReference

- `schemaVersion`: `a-end-face-labelme-short-line-reference/1`
- `annotationPath`, `annotationSha256`
- `imagePath`, `imageSha256`, `width`, `height`
- `imageDataIgnored`: boolean
- `features`: exactly canonical keys `19` and `30`
  - `rawLabel`, `shapeType`, `points`, `annotatedLengthPx`, `angleDeg`

## Candidate provenance extension

- `referenceMode`: `desktop_core` or `external_labelme`
- `referenceAnnotationPath`, `referenceAnnotationSha256`: nullable
- `referenceImagePath`, `referenceImageSha256`: nullable

## Invariants

- External annotation and reference image must be accessible and hashable.
- Every point is finite, inside the declared/actual image, and each line has non-zero length.
- Candidate state never mutates core measurements or feature quality.
