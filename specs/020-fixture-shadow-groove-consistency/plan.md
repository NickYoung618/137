# Implementation Plan: A2固定阴影与真槽同源性

**Branch**: 020-fixture-shadow-groove-consistency | **Date**: 2026-08-16 | **Spec**: spec.md

## Summary

在019默认关闭的多阈值候选与亚像素双侧壁能力之上，增加两个同样默认关闭、互相解耦的传统视觉阶段：

1. 固定阴影nuisance matcher：只生成相机坐标模板匹配与成对证据，不删除原始候选。
2. 双侧壁source-consistency gate：在亚像素侧壁精修后比较两侧灰度跃迁、局部标准化剖面、梯度、径向支持和终点结构；任一硬门失败即拒绝。

有参考剖面时，重叠诊断比较纯阴影预测与阴影加额外槽残差；无参考剖面时保持diagnostic_incomplete，不猜测。服务器只完成合成、历史JSON治理和25张JPEG无真值诊断；140张原始BMP及人工物理标签在Mac完成。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: NumPy、Pillow、项目锁定的gyj圆边缘与鲁棒拟圆适配能力；不新增生产依赖
**Storage**: Git内JSON Schema、配置模板和脱敏统计；图像、LabelMe及回放结果留在Git外
**Testing**: unittest、jsonschema、受控NumPy合成图、历史JSONL只读审计、Mac原始BMP分折回放
**Target Platform**: Linux服务器开发验证与macOS离线回放，单进程CPU
**Project Type**: Python算法库与CLI
**Performance Goals**: 实验模式新增P95不超过0.8秒，峰值RSS不超过1.5 GiB；默认关闭路径不执行新增计算
**Constraints**: 单帧、传统视觉、fail-closed；固定角不得作为ignore mask；part-006封存；无标签不宣称准确率
**Scale/Scope**: 480张历史normal统计、7个分折零件140张Mac BMP、25张服务器JPEG、至少6帧新人工队列

## Constitution Check

- 规格先行：PASS。33项FR和13项SC覆盖场景、契约、验证和阻塞。
- 坐标与姿态：PASS。nuisance使用图像+x为0°且y-down顺时针角；85°引导不变。
- 质量与安全失败：PASS。0解、多解、缺模板、同源失败均不输出姿态。
- 数据溯源：PASS。按sample隔离、SHA防泄漏、原图Git外、part-006前置拒绝。
- 模块化与集成：PASS。模板匹配、同源门、重叠诊断和运行时适配解耦，全部默认关闭。
- 性能与资源：DESIGN_PASS / EMPIRICAL_BLOCKED。固定采样数、假设硬上限、无全图复制和无跨窗口完整重跑；
  峰值RSS过门，但共享服务器负载污染了端到端成对P95，须在负载受控环境复核0.8秒增量门。

## Architecture and Data Flow

1. 复用现有物理外圆输出圆心、半径和极坐标环带。
2. 现有angular_profile产生原始暗区，完整保留。
3. fixture_shadow模块对每个原始暗区计算两个模板的标量与剖面证据，并评估两阴影是否成对完整。
4. 若启用重叠诊断且模板含人工参考剖面，产生有上限残差假设；否则只输出不可判定诊断。
5. 现有groove_recognition继续进行局部凹入粗筛。
6. 现有groove_refinement采集两侧亚像素点，同时保留统一方向的局部灰度/梯度剖面。
7. sidewall_consistency对两侧做硬门；失败候选不得进入single_groove_pose。
8. 只有唯一候选完成全部阶段才输出当前姿态和图像引导。

## Project Structure

Documentation:

    specs/020-fixture-shadow-groove-consistency/
      spec.md
      plan.md
      research.md
      data-model.md
      contracts/
      quickstart.md
      tasks.md
      evidence.md

Source and tests:

    algorithms/slot_pose/fixture_shadow.py
    algorithms/slot_pose/sidewall_consistency.py
    algorithms/slot_pose/groove_refinement.py
    algorithms/slot_pose/legacy_adapter.py
    algorithms/slot_pose/contract.py
    contracts/slot-pose-config.schema.json
    config/closed-loop-guidance-v3.fragment.json
    tools/prepare_slot_pose_fixture_shadow_config.py
    tools/audit_a2_fixture_shadow_evidence.py
    tests/test_fixture_shadow.py
    tests/test_sidewall_consistency.py
    tests/test_single_real_groove.py
    tests/test_slot_pose_contract.py

**Structure Decision**: 在现有slot_pose包内新增两个纯计算模块；legacy_adapter只负责编排，避免把模板、精修和姿态状态耦合在一个函数中。

## Phase 0 Research Decisions

- 不使用固定角删除；角度只是模板位置子证据。
- 模板匹配输出独立子证据；两处阴影之间的完整性/相似性只作诊断，不因透视或照明造成的不对称直接拒绝姿态。
- 局部剖面统一成金属到暗区方向后再标准化比较，避免左右壁极性相反造成伪差异。
- 侧壁对比使用归一化差，剖面同时输出相关性和平均绝对差，径向支持与端点结构单独成门。
- 无人工参考剖面时不执行可能改变候选的去模板残差分解，只输出diagnostic_incomplete。
- part-019结构化回归先以人工确认的边缘对比不对称证据构造测试夹具；不能把真实图数值写入生产运行时。
- 圆弧阴影与近方形槽口的形态差异保持为LabelMe后验证项；当前不据此新增门限。

## Phase 1 Design Outputs

- data-model.md：模板、匹配、重叠假设、侧壁剖面和决策状态。
- contracts/fixture-shadow-config.md：默认关闭的配置与严格校验。
- contracts/fixture-shadow-diagnostics.md：向后兼容诊断字段和fail-closed状态。
- quickstart.md：服务器测试、历史审计与Mac三折配对命令。

## Post-Design Constitution Re-check

CONDITIONAL_PASS。设计未改变外圆、目标角、PLC或默认行为；没有以历史输出代替真值；所有实验路径显式启用且可安全失败。
性能P95、Mac原始BMP配对和结构化人工标签仍是发布阻塞，不影响功能分支默认关闭交付。

## Complexity Tracking

无Constitution豁免。新增两个小型模块是为了保持阶段可测试和诊断可追踪，不增加外部服务、模型或并发。
