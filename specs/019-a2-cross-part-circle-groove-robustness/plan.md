# Implementation Plan: A2 跨零件圆与真槽鲁棒性

**Branch**: 019-a2-cross-part-circle-groove-robustness | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

## Summary

在不改变85°闭环引导契约、不以无真值结果调生产门限的前提下，增加两个默认关闭的版本化实验能力：
物理圆分扇区残差证据与有上限的一次重拟合，以及环形暗区的有界多阈值假设与跨假设去重。补充按
完整物理sample的分折、封存泄漏检查和选定根因组只读审计。没有人工圆/真槽真值前，实验能力不得
成为默认生产路径。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: 既有NumPy 2.4.4、Pillow 12.2.0和锁定gyj边缘点/robust_fit_circle；不新增生产依赖

**Storage**: 外置图片、LabelMe、CSV、JSONL和JSON；Git内只保存Schema、模板、脱敏统计与小型夹具

**Testing**: unittest、jsonschema、合成圆/槽/阴影边界、选定历史JSONL只读dry-run、Mac分组原图回放

**Target Platform**: Linux服务器和macOS离线CLI，单进程CPU路径

**Project Type**: Python算法库与离线CLI

**Performance Goals**: 实验模式新增P95延迟不超过0.8秒；单进程峰值内存不超过1.5 GiB；七组无图审计五秒内完成

**Constraints**: 不读取或重跑part-006；不按帧随机拆分；不改PLC、上位机或85°契约；0槽或多槽继续安全失败

**Scale/Scope**: 历史700条结果中的七个normal物理零件、140帧诊断；阈值假设和圆重拟合次数均有硬上限

## Constitution Check

*GATE: Phase 0前与Phase 1后均通过。*

| 原则 | 设计响应 | 状态 |
|---|---|---|
| I. 规格先行 | 019的场景、FR、SC、任务和分组验收可追踪 | PASS |
| II. 坐标契约 | 沿用007的y-down、正顺时针、85±5°和最短旋转 | PASS |
| III. 安全失败 | 圆排除、阈值假设和候选数有硬上限；0/多槽不输出引导 | PASS |
| IV. 数据溯源 | 复用009 sample/condition/SHA；报告方法、配置、环境和分折哈希 | PASS |
| V. 模块化 | 圆证据、暗区假设、真槽门、姿态与评估分层；默认路径兼容 | PASS |
| 工程门 | 单元、契约、Schema、离线回归、性能和污染检查进入tasks | PASS |

Constitution已从跨仓库合并误覆盖的A端面版本恢复为槽姿态专用v3.0.0。Phase 1复核：新配置默认
关闭，新诊断为向后兼容扩展，人工真值不进入运行时，无宪法豁免。

## Architecture and Data Flow

    image
      -> existing component proposals
      -> sparse gyj edge points + initial robust circle
           -> always: angular sector residual evidence
           -> experimental: bounded suspect-sector exclusion + one refit
      -> authoritative final gyj edge points + same evidence/refit policy
      -> physical circle accepted or fail-closed
      -> ring profile
           -> default: existing MAD threshold
           -> experimental: bounded MAD/quantile hypotheses
                -> per-hypothesis runs/rejections
                -> circular dedup with origin trace
      -> existing groove geometry and bounded ambiguity refinement
      -> exactly one physical groove -> existing subpixel pose/guidance

    009 grouping + explicit root-cause map + sealed lock
      -> whole-sample fold planner
      -> selected historical replay audit and annotation queue

## Design Decisions

1. 分扇区证据始终输出；只有显式实验开关允许一次有上限重拟合。
2. 重拟合复用同一次射线采样的点集，禁止为每个窗口重跑整条定位链。
3. 异常扇区只由圆残差和角覆盖决定，不使用槽角、85°或算法成功状态。
4. 保留原始MAD阈值；实验模式补充有限个分位数阈值，所有阈值有界且来源可追踪。
5. 多阈值的重复暗区先按环形中心与区间重叠去重，再送入现有真槽门。
6. 多个物理槽候选不得按分数或85°择一，只能通过现有有上限侧壁精修得到唯一幸存者。
7. 保持slot-pose-result/3；新字段只扩展diagnostics。配置子块各自版本化。
8. 分折只消费009 grouping和封存lock，不读取results；不足两个sample的家族明确样本不足。
9. 历史审计先匹配目标SHA，只解析指定七组且在解析前拒绝封存SHA。
10. 合成与已暴露数据的改善不能解除生产激活BLOCKED。

## Project Structure

### Documentation

    specs/019-a2-cross-part-circle-groove-robustness/
      spec.md plan.md research.md data-model.md quickstart.md evidence.md tasks.md
      contracts/robustness-config.md
      contracts/diagnostic-evidence.md
      contracts/grouped-validation.md

### Source Code

    algorithms/slot_pose/
      angular_profile.py physical_outer_circle.py full_frame_circle_locator.py
      legacy_adapter.py contract.py
    contracts/
      slot-pose-config.schema.json
      a2-robustness-fold-plan.schema.json
      a2-robustness-audit.schema.json
    config/
      a2-robustness-parts.template.csv
      closed-loop-guidance-v3.fragment.json
    tools/
      plan_a2_robustness_folds.py
      audit_a2_robustness_groups.py
    tests/
      test_angular_profile.py test_physical_outer_circle.py
      test_full_frame_circle_locator.py test_single_real_groove.py
      test_slot_pose_contract.py test_a2_robustness_governance.py

**Structure Decision**: 延续单一算法库与CLI结构；不复制拟圆实现，鲁棒层只组织既有边缘点和
robust_fit_circle。

## Complexity Tracking

| 复杂度 | 必要性 | 简单方案为何被拒绝 |
|---|---|---|
| 有上限分扇区重拟合 | part-023的180/720射线表现反转 | 直接放宽P95会接纳错圆 |
| 有上限多暗阈值 | part-019原始阈值为负数 | clamp到0仍可能raw=0，放宽真槽门会接纳阴影 |
