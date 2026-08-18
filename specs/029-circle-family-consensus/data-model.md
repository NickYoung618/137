# Data Model: Circle-Family Consensus

## Member Hypothesis

- Finite preliminary circle `(centerX, centerY, radiusPx)` in image pixels.
- One observed candidate assignment per supported ray.
- Support, angular coverage, median/P95 residual, failed checks and bounded seed membership.
- Belongs to exactly one grouped family or remains a distinct family.

## Family Consensus

- Strategy version and bounded maximum iteration count.
- Member-hypothesis count.
- Finite consensus seed derived invariantly from all member circles.
- Corrective activation determined only by the existing scaled authoritative residual gate.
- Current observed assignments keyed by ray index.
- Per-iteration assignment-change count.
- Converged flag and terminal status.
- Final preliminary circle, support, coverage, residual and failed checks.

State transitions:

`grouped → initialized → reassigned → converged → qualified/rejected`

or

`grouped → initialized/reassigned → non_convergent/invalid → rejected`

## Edge-Family Selection Diagnostic

- Existing extraction, seed, hypothesis, family and timing fields.
- Per-family consensus summary for version 2.
- Summary records whether correction was applied, the trigger residual, original residual, iteration evidence and final quality.
- Selection remains `selected`, `ambiguous`, `no_family`, `invalid` or `overflow`.
- A selected family supplies only observed points and their original ray indices to the authoritative robust fit.

## Compatibility Profile

- Version-1 configuration: legacy representative behavior and existing diagnostic surface.
- Version-2 configuration: corrective consensus plus exact preservation of already-passing representatives and additive diagnostics.
- Root invalid results preserve null pose/guidance/PLC command fields.
