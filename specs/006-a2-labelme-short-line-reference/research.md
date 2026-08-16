# Research: A2 LabelMe Short-Line Reference

## R1 — Existing annotation semantics

The desktop A-end-face LabelMe JSON contains ten shapes. Relevant short lines are `19��` (`line`, 2 points, annotated length about 44.80 px) and `30��` (`line`, 2 points, about 26.20 px). Damaged diameter/unit glyphs are already normalized by `canonical_feature_label`, yielding stable features `19` and `30`.

Other shapes are: 46 and 20 as two-point lines; damaged-glyph 100, 71, 86, 80 and M78 as circular `linestrip` point sets; and one polygon region. The core interprets the largest circle as the outer localization anchor, the smallest as the inner alignment circle, intermediate circles as measured rings, lines as length/angle measurements, and the polygon as region geometry.

## R2 — Why the v1 reference is insufficient for A2 development

V1 registers a gradient patch cut from the old desktop reference at the old 19/30 annotation. The Mac A2 core baseline shows a stable domain mismatch (both short lines fail on all 25 images). A manually marked representative A2 image can supply a domain-matched template without altering global localization or legacy measurements.

## R3 — Alignment decision

The external template uses its own annotated midpoint and direction only to sample an orientation-normalized local gradient patch. The target search remains centered on the immutable core transform prediction. This avoids requiring the external LabelMe file to duplicate localization circles, while preserving the existing bounded correction and failure gates.

## R4 — Leakage and evidence

Twenty repeated frames from the same sample/position form one development unit. They MUST stay together. Candidate configuration and LabelMe reference are frozen before evaluating other samples. Server synthetic/reference tests establish behavior and safety only; Mac A2 images establish real recovery/generalization.

## R5 — Alternatives rejected

- Lowering core thresholds: rejected because it does not address the reference-domain mismatch and can promote noise.
- Writing candidate geometry into core measurements: rejected because it destroys the baseline comparison.
- Embedding the A2 reference image in Git/JSON outputs: rejected by the external-asset boundary.
- Treating 20 repeated frames as 20 independent samples: rejected as leakage.
