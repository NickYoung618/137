# Data Model: Position-Independent Radial U-Contour Ownership

## Coarse Fixture Evidence

- `sectorId`: bounded diagnostic identifier
- `role`: `upper_fixture` or `lower_fixture`
- `centerDeg`, `spanDeg`: finite image-frame geometry
- Validation: retained for diagnostics and safety context; never sufficient for ownership

## Refined Radial Wall

- `side`: start or end wall
- `endpointAngleDeg`: finite detected-circle angle
- `wallToRadiusAlignmentDeg`: acute deviation between the observed wall and its endpoint radius
- `openingHalfWidthDeg`: measured half-width of the same coarse opening
- `radialEnvelopeDeg`: opening half-width plus the unchanged existing intersection tolerance
- Validation: two distinct sides and deterministic ordering

## Radial U-Contour Ownership Proof

- Schema: `fixture-groove-source-exclusion/4`
- Inputs: coarse overlap, fixture pair, two refined walls/endpoints, observed floor, locked normalized source checks
- States: `verified`, `rejected`, `not_evaluated`
- Required verified facts: complete walls/floor, both wall alignments within the derived envelope, normalized profile/coverage/endpoint checks pass, no fixed angle/manual truth
- Output: ordered checks, both wall alignments, derived envelope, failed checks, `radialUContourOwnershipVerified`

## Effective Source Decision

- Schema: `source-consistency-adjudication/5`
- Preserves: original source status, failures, measurements and checks
- May remove effectively: `edge_contrast_asymmetry`, `edge_gradient_asymmetry`
- New route requires: verified schema `/4` ownership and all locked non-photometric checks
- Compatibility route: preserves unchanged version-4 complete-U or visible-boundary authorization
- States: `NOT_NEEDED`, `ACCEPTED_OVERRIDE`, `REJECTED`, `NOT_EVALUATED`

## State Transitions

```text
coarse overlap -> physical refinement -> radial U-contour proof -> source adjudication
       |                 |                       |                    |
   diagnostic       incomplete => reject    unresolved => reject   effective source
```

No state can create pose. It can only allow the already accepted refined groove pose to continue.
