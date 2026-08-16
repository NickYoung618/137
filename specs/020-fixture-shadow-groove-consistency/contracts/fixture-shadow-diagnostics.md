# Contract: Fixture Shadow Diagnostics

diagnostics新增向后兼容字段：

- fixtureShadowEvidence：启用状态、模板版本、原始候选数、逐候选逐模板匹配、成对状态和分解假设。
- grooveRefinement.startSide/endSide.profileEvidence：径向对比/梯度序列及原始/归一化局部灰度剖面。
- grooveSourceConsistency：每项实测值、门限、余量、passed和failedChecks。

失败语义：

- FIXTURE_SHADOW_TEMPLATE_INCOMPLETE：仅在必须依赖模板分解且模板证据不完整时使用。
- GROOVE_SOURCE_INCONSISTENT：唯一粗候选完成两侧精修但同源硬门失败。
- GROOVE_RECOGNITION_AMBIGUOUS：多个同源候选或多个分解假设通过。

fixtureShadowEvidence中的成对完整性和两影相似性是诊断字段：不完整、不相似或单影缺失不得单独否定
固定阴影假设，也不得直接清空姿态。只有实际依赖且已人工验证的重叠分解缺少必要模板证据时，才使用
FIXTURE_SHADOW_TEMPLATE_INCOMPLETE；固定角仍只是软先验。

上述失败均保持result.valid=false、currentAngleDeg=null、correctionDeg=null和imageFrameCorrectionDeg=null。默认关闭时不新增失败。
