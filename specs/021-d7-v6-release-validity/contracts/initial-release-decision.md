# Contract: D7 v6 fallback initial-release decision

## Decision

首版允许通过原v6质量门的fallback继续报告`measurementValid=true`，但它只代表技术测量有效，
不代表边界证据完整、绝对精度已证明或生产合格。

## Required invariant

```text
fallback eligible :=
  d7.quality.upstream == "ok:dual_boundary_fit"
  AND d7_x1, d7_y1, d7_x2, d7_y2, d7_length are finite
```

任何一项不满足时，fallback MUST NOT恢复D7有效性。

## Required reporting for eligible fallback

```json
{
  "measurementValid": true,
  "evidenceComplete": false,
  "evidenceAuditStatus": "unavailable",
  "evidenceAuditReason": "boundary_evidence_unavailable",
  "sourceDetector": "hole2-v6-original-quality-fallback",
  "recoveryPass": "v6_original_quality"
}
```

报告MUST另行统计`measurementValid`与`evidenceComplete`。renderer/LabelMe MUST不伪造A/B线；只存在
尺寸连接线时，MUST明确其为measurement annotation而不是detected contour。

## Initial-release matrix

| 用途 | eligible v6 fallback |
|---|---|
| 技术检测覆盖率 | 允许计入，但单列fallback和不可审核数 |
| 静态趋势/异常选帧 | 允许，不能称绝对准确度 |
| A/B边界人工审核 | 不允许；无保存证据 |
| 精度验收 | 不允许仅凭010无真值结果 |
| 生产OK/NG | 不允许；`productionDisposition=not_evaluated` |

若首版消费方只接受可审核测量，应使用`measurementValid && evidenceComplete`作为其自身准入条件，
不得篡改底层检测状态。
