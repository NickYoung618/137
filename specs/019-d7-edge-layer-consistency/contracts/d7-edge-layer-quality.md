# Contract: D7 edge-layer quality evidence

本增量不增加Schema必填字段，不破坏既有JSON消费者。下列字段作为D7 `quality`内的可审计诊断：

- `candidate_<side>_strip.layerStabilizationAttempted: bool`
- `candidate_<side>_strip.layerStabilizationUsed: bool`
- `candidate_<side>_strip.layerStabilizationInitialFailureStage: string|null`
- `candidate_<side>_strip.layerStabilizationRawPointCount: integer`
- `candidate_<side>_strip.layerStabilizationInlierPointCount: integer`
- `candidate_<side>_strip.layerStabilizationResidualGatePx: number`

Contract rules:

1. `Used=true` implies `Attempted=true`.
2. `ResidualGatePx` must equal the existing configured maximum fit residual; it is not a new gate.
3. `Used=true` does not bypass support, axis, residual, parallelism or search-boundary gates.
4. Primary success has `Attempted=false/Used=false` and unchanged measurement geometry.
5. No field may contain manual truth, nominal dimension or fixed compensation.
