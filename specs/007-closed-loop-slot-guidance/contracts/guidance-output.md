# Contract: 单真槽闭环图像引导输出

## Version boundary

- `single-real-groove-pose-config/3` selects this contract.
- The pose diagnostic is `slot-single-real-groove-pose/3`.
- The top-level result is `slot-pose-result/3`.
- Legacy, paired, multi-role, and single-groove v1/v2 configurations continue to emit `slot-pose-result/2` without semantic changes.

## Successful detection

When the physical circle, exactly one real groove, and the subpixel groove opening geometry are reliable:

```json
{
  "schemaVersion": "slot-pose-result/3",
  "technicalStatus": "succeeded",
  "result": {
    "valid": true,
    "detectionStatus": "DETECTED",
    "guidanceStatus": "DETECTED_NEEDS_ADJUSTMENT",
    "currentAngleDeg": 22.834,
    "targetAngleDeg": 85.0,
    "toleranceDeg": 5.0,
    "correctionRawDeg": 62.166,
    "correctionDeg": 62.166,
    "imageFrameCorrectionDeg": 62.166,
    "rotationDirection": "CLOCKWISE",
    "withinTolerance": false,
    "mechanicalCorrectionDeg": null,
    "plcCommand": null,
    "plcExecutionStatus": "BLOCKED_MAPPING_UNCONFIRMED"
  },
  "error": null
}
```

`result.valid=true` means that the current frame contains reliable detection geometry and a usable image-frame guidance value. It does not authorize a PLC movement.

## Deadband

For a reliable current angle inside the inclusive left/lower target interval `[80, 90]`:

- `guidanceStatus=DETECTED_IN_POSITION`
- `correctionRawDeg` retains the diagnostic shortest difference to 85°.
- `correctionDeg=0`
- `imageFrameCorrectionDeg=0`
- `rotationDirection=NONE`
- `withinTolerance=true`

## Detection failure

When the circle, unique groove, or subpixel opening geometry is unavailable or ambiguous:

- `technicalStatus=failed`
- `result.valid=false`
- `detectionStatus=DETECTION_FAILED`
- `guidanceStatus=NOT_AVAILABLE`
- all current/correction/direction fields are null
- `mechanicalCorrectionDeg` and `plcCommand` are null
- `error.code` contains the stable detection or input error code

A detection failure must never be represented by a zero correction.

## Coordinate and sign convention

- Origin: detected physical outer-circle center.
- Image axes: `+X` right, `+Y` down.
- Zero ray: the downward image `+Y` ray. The workpiece/device phrase “negative Y lower half-axis” is an alias for this same physical ray.
- Positive angle and correction: clockwise in the image frame.
- Negative angle and correction: counterclockwise in the image frame.
- Angle interval: `[-180, 180)`.
- Exact 180° differences normalize to `-180°`.

The image-frame direction is not automatically the actuator direction. Until camera/actuator direction, zero, scale, address, byte order, and handshake are confirmed, `plcExecutionStatus=BLOCKED_MAPPING_UNCONFIRMED` and no executable command is emitted.

## Review exports

The review package must contain:

- one review JSON index;
- `candidates.csv` with raw and accepted/rejected groove evidence;
- `guidance.csv` with detection, current angle, target, raw correction, deadbanded correction, direction, in-position state, and PLC gate;
- `failures.csv` containing detection failures only;
- one overlay and one AUTO LabelMe diagnostic per input image;
- one contact sheet.

AUTO LabelMe output is algorithm-generated review evidence, not manual truth and not a runtime input.
