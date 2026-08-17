# Evidence

## 2026-08-17 Server MVP

- Base: `022-source-consistency-adjudication@06f28af`；feature branch仅023，不合main。
- 聚焦TDD首次暴露唯一性测试恰好等于margin边界，修正为严格小于门限的歧义样例。
- 少量真实回归只使用非sealed `normal:part-008`三个既有结果：141、145、147；没有重跑140/700张，也没有调视觉阈值。
- 初跑3/3被新编排判`NO_COMPLETE_GROOVE`。根因：021候选提取保留原始source-consistency reject，不识别022版本化`ACCEPTED_OVERRIDE`，导致顶层有效145/147被错误降级。
- 修复只在023编排层尊重严格版本化有效裁决，同时保留`source_consistency_rejected`原始原因；没有修改圆、槽、0.12门或022裁决逻辑。
- 修复后：141继续fail-closed并直接保留`HOUSING_CIRCLE_NOT_FOUND`；145有效，current `29.578393924928037°`、correction `+55.42160607507196°` CLOCKWISE；147有效，current `29.579343127253935°`、correction `+55.420656872746065°` CLOCKWISE。
- Git外路径：`$SLOT_POSE_PRIVATE_DATA/half-turn-guidance-023-server-20260817`。
- 真实双拍仍缺失：`REAL_PAIR_VALIDATION_MISSING`。不得宣称双拍现场准确率或有效率。
- 聚焦新旧paired：38/38通过；48/48根Schema通过。
- 16×16候选纯编排微基准（1000次，不含图像检测）：P50 `2.433292ms`、P95 `2.975306ms`、max `6.483652ms`，满足P95<20ms设计门。
- 最终权威全量（显式安装jsonschema）：480/480通过。未安装jsonschema的首次全量仅有2个导入错误，属于测试依赖缺失，不是算法失败。

## Visual change discipline

本提交不改变视觉算法。后续若圆/槽失败需要算法修改，固定执行：少量物理零件复现→分层根因→只读审计yyh/gyj可复用实现→SpecKit修改→小样本验证→独立回归。人工语义不足时停止调参，并提供代表图与最少审核动作。
