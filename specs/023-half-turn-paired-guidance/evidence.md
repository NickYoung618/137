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

## 2026-08-17 Mac independent focused gate

- Mac候选：`023-mac-validation@b38ffd25a0297839efa5f582b7c6651d1d842204`，由远程`023-half-turn-paired-guidance`显式抓取并fast-forward验证；工作树干净。
- 聚焦命令：`uv run --with jsonschema python -m unittest tests.test_half_turn_guidance tests.test_paired_capture_slot_pose -q`。
- 结果：38/38通过，0 failure/error。
- 安全边界：没有修改阈值、PLC/HMI或main；没有合并或push main；没有用旋转单张图片伪造真实双拍。
- 单拍代表复核与服务器一致：145 current约`29.578°`、correction约`+55.422°`；147 current约`29.579°`、correction约`+55.421°`；141为`HOUSING_CIRCLE_NOT_FOUND`且不输出角度。
- 已有失败代表覆盖：161外圆未找到、441物理外圆验证失败、281凹槽识别失败、261凹槽歧义、401槽壁精修失败、374真实槽壁与固定阴影混合。
- 裁决：该Mac门只证明023单图/半圈双图编排的聚焦契约跨平台通过，不证明底层图片检测改善；真实同件180°pair仍是`REAL_PAIR_VALIDATION_MISSING`。
