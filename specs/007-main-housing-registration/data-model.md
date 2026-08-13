# Data Model: Main Housing Registration

## HousingHypothesis

- `componentIndex`: stable index within the current image
- `componentBoundsPx`: min/max x/y at original scale
- `coarseCenterPx`, `coarseRadiusPx`
- `centerPx`, `radiusPx`: robust refined outer circle
- `componentPixels`, `componentFillRatio`, `aspectRatio`
- `edgePointCount`, `edgeCoverageRatio`, `circularResidualPx`
- `scaleToReference`, `appearanceScore`, `instanceScore`
- `gates`: per-hypothesis pass/fail records

## HousingRegistration

- `registrationVersion`, `valid`, `failureReason`
- `reference`: selected reference housing geometry and anchor annulus ratios
- `hypotheses`: bounded target hypothesis diagnostics
- `selectedIndex`, `runnerUpIndex`, `selectionMargin`
- `transform`: reference/target centers, scale, rotation degrees
- `rotationScore`, `rotationSecondScore`, `rotationMargin`
- `checks`: required registration gates

## ProjectedShortLine

- `reference`: external LabelMe line geometry
- `projected`: transform-projected target geometry
- `candidate`: optional locally refined geometry
- `candidateValid`: true only when registration and every local gate pass
- `transition`: `both_valid`, `recovered`, `regressed`, or `both_invalid`

## Invariants

- Registration inputs never include legacy target 19/30 geometry.
- Candidate evaluation may read legacy values for comparison but never mutate them.
- Invalid registration implies invalid candidates with null candidate geometry.
- Every finite numeric output remains JSON-compatible; images are never embedded.
