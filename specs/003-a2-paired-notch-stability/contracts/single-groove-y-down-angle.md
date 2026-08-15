# Single Real-Groove Y-Down Angle Contract

该契约定义`single_real_groove` v2诊断，不改变顶层`slot-pose-result/2`。

## Coordinate frame

- Origin: detected physical outer-circle center.
- `+X`: image right.
- `+Y`: image down.
- Datum ray: origin toward image-down `+Y`.
- Positive rotation: clockwise.
- Signed range: `[-180°,180°)`.

The accepted dark candidate is only a coarse search interval. v2 fits both groove sidewalls from locally dense
bilinear samples, intersects both robust sidewall lines with the fitted physical outer circle, and uses the circular
midpoint of those two subpixel intersections. It is not the intensity-weighted candidate center or a coarse angular bin.

For `dx = openingX-centerX` and `dy = openingY-centerY`:

```text
measuredAngleDeg = wrapToSigned180(degrees(atan2(-dx, dy)))
```

## Target and location gate

```text
nominalDeg = +85
toleranceDeg = 5
positionGatePassed = dx < 0 and dy >= 0
angleTolerancePassed = 80 <= measuredAngleDeg <= 90
toleranceStatus = PASS only when both gates pass, otherwise FAIL
```

The interval is closed. `+90°` is the exact image-left horizontal boundary and is accepted by the stated
`85°±5°` tolerance. A right-lower mirror near `-85°` always fails.

## Deviation and correction

```text
signedMeasurementMinusTargetDeg = wrapToSigned180(measuredAngleDeg - 85)
imageFrameCorrectionDeg = wrapToSigned180(85 - measuredAngleDeg)
```

Positive `imageFrameCorrectionDeg` means clockwise; negative means counter-clockwise. It is a geometric image-frame
recommendation, not a PLC command. Until B-005 is closed:

- `mechanicalCorrectionDeg = null`
- `plcCommandAuthoritative = false`
- top-level `result.valid = false`
- top-level `result.signedRelativeRotationDeg = null`
- error code `PLC_MAPPING_UNCONFIRMED`

## Version compatibility

- `single-real-groove-pose-config/1` continues to produce `slot-single-real-groove-pose/1` and
  `targetAssessment.status=NOT_EVALUATED`.
- `single-real-groove-pose-config/2` produces `slot-single-real-groove-pose/2` with the fields above.
- A v1 config must never be silently interpreted as v2.
