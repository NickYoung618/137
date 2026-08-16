# Contract: Diagnostic Evidence

slot-pose-result/3顶层不升版。新增字段位于diagnostics：

- physicalOuterCircle.sectorEvidence和robustRefit
- circleLocalization.circleCandidates每项的sectorEvidence和robustRefit
- angularProfile.rawDarkThreshold和thresholdUsable
- candidateSummary.thresholdMode、thresholdHypotheses和candidateOrigins

所有数值必须有限，不可表示残差为null。证据不得包含原始像素、绝对现场路径、人工真值或暗区角色推断。

失败语义不变：圆失败返回现有圆错误；raw=0或accepted=0返回GROOVE_RECOGNITION_FAILED；
accepted大于1且精修仍不唯一返回歧义/精修错误。任一失败均valid=false且所有姿态与引导角为null。
