# Evaluation Report Contract

Two reports are emitted from one validated manifest/truth/result set:

- `normal-report.json`: matched/valid counts and rate, circular-error MAE/P95/max, per-condition circular static
  range and standard deviation, cross-condition truth-residual mean/range/stddev, error-code counts, and elapsed
  mean/P50/P95/max.
- `bad-report.json`: matched count, false-positive/misguidance count and rate, invalid count, error-code counts,
  and elapsed mean/P50/P95/max.

Failures never contribute an angle value. Cross-condition statistics compare circular residuals
`wrap(estimate - truth)`, never raw angle means. Reports without confirmed grouping, sufficient repeats, truth,
or acceptance thresholds use `INCOMPLETE` or `NOT_EVALUATED`, never a formal `PASS`.
