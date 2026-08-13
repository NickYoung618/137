# Implementation Plan: A 端面短线候选诊断与测量改进

**Branch**: `main` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-short-line-candidate/spec.md`

## Summary

保持桌面 `core.py` 字节不变，在其外增加版本化的 19/30 短线诊断和候选测量。候选使用参考标注附近
的参考梯度模板，在目标图预测区域内联合搜索横向位置、纵向位置和方向；它有独立证据门禁、状态和
量测，绝不回写 `coreValid` 或旧量测。新增工具把外置 Manifest、A2 图片和既有 v2 JSONL 按任务关联，
生成逐图核心/候选对照 JSONL 与可离线重建的汇总。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；不新增运行依赖

**Storage**: Git 内小型配置、JSON Schema、规格和无图摘要证据；Git 外图片、标注、Manifest、结果 JSONL/JSON

**Testing**: Python unittest、服务器可访问参考资产、临时生成的合成梯度/图片与 Manifest、jsonschema 合同验证

**Target Platform**: Linux 服务器和 Mac 本机兼容环境，均为离线 CLI

**Project Type**: Python 算法适配库与 CLI

**Performance Goals**: 候选只评估 19/30；单图结果分别记录核心耗时和候选耗时，批量汇总不把二者混为旧基线

**Constraints**: 核心 SHA-256 不变；候选不能降低旧门限或改写旧状态；A2 原图/运行 JSONL 不进 Git；严格有限 JSON

**Scale/Scope**: 1 张服务器参考图、合成边界集和 Mac 外置 A2 前 25 张；本轮候选仅覆盖 19/30

## Constitution Check

| Gate | Pre-design | Post-design |
| --- | --- | --- |
| 规格先行与追踪 | PASS：16 条 FR、7 条 SC、3 个独立故事 | PASS：研究、实体、四份合同及可运行验证路径覆盖全部要求 |
| 核心原样复用 | PASS：选择核心外候选，拒绝核心补丁 | PASS：新文件位于 adapter/contract/tool 边界，核心哈希门禁保留 |
| 输入输出可复现 | PASS：输入、参考、核心、配置均要求指纹 | PASS：v3 结果、候选配置、逐图比较和汇总均版本化 |
| 安全失败 | PASS：候选多门禁 AND，独立于核心 | PASS：失败原因、检查和回归计数进入合同，不允许强行恢复 |
| 数据最小化 | PASS：Mac 只重跑外置资产 | PASS：仓库只保存用户摘要，JSONL、图片和归档继续忽略 |

## Phase 0: Research Findings

研究结论见 [research.md](research.md)。参考图实算表明 19/30 的核心峰都位于搜索内部，但峰值/中位值
分别约为 `1.103` 和 `1.083`，未达到固定 `1.4` 倍规则；ROI 本身却有 133–162 灰度级对比度和明确
梯度，因此不是“无图像信号”。这支持使用结构不同的参考模板联合配准候选，而不是降低核心门限。

## Phase 1: Design & Contracts

- 状态、诊断、候选量测和批量聚合实体见 [data-model.md](data-model.md)。
- 单图结果升级为 `a-end-face-result/3`，旧核心字段及语义保持不变。
- 候选配置为 `a-end-face-short-line-candidate-config/1`。
- 外置逐图比较为 `a-end-face-short-line-comparison/1`。
- 比较汇总为 `a-end-face-short-line-batch-summary/1`。
- Mac 外置 A2 和服务器参考/合成验证步骤见 [quickstart.md](quickstart.md)。

## Project Structure

### Documentation (this feature)

```text
specs/005-short-line-candidate/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
├── evidence/
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/end_face/
├── core.py                         # 权威核心；不得修改
├── short_line_candidate.py         # 版本化参考模板候选与诊断
├── adapter.py                      # 核心后运行候选，旧结果不回写
├── contract.py                     # v3 单图严格合同
└── main.py                         # 单图候选配置入口
config/
└── end_face_short_line_candidate.v1.json
contracts/
├── a-end-face-result.schema.json
├── a-end-face-short-line-candidate-config.schema.json
├── a-end-face-short-line-comparison.schema.json
└── a-end-face-short-line-batch-summary.schema.json
tools/
├── evaluate_end_face_batch.py
└── compare_short_line_candidates.py
tests/
├── test_short_line_candidate.py
├── test_short_line_comparison.py
├── test_end_face_contract.py
├── test_end_face_cli.py
└── test_end_face_reference.py
```

**Structure Decision**: 候选是现有适配库内的独立模块，不复制或分叉核心。单图 CLI 与批量检测可输出
候选；比较 CLI 专门读取现有 v2/v3 JSONL，便于 Mac 不重跑旧核心就对相同基线逐图比较。

## Implementation Order

1. 先写合同、合成信号、参考图和外置 Manifest 的失败测试，确认当前缺少候选模块而失败。
2. 实现配置验证、核心短线路径复算诊断、参考模板联合搜索和多证据安全门禁。
3. 将候选作为只追加结果接入适配器/v3 合同和单图/批量 CLI，不修改核心结果对象。
4. 实现 v2/v3 JSONL 与 Manifest 的全量预检、逐图比较和无图汇总。
5. 运行全量测试、Schema、参考资产、核心来源和 Git 大文件门禁，再执行 SpecKit 只读 analyze。

## Quality Gates

1. `algorithms/end_face/core.py` 与桌面 `repeatability_evaluation.py` SHA-256 均为 `f408631e…f8fbc`。
2. 合成偏移/旋转线达到规格误差，空白、边界、低对比、竞争峰由对应必要门禁拒绝。
3. 参考图 19/30 输出完整核心诊断，候选只能在其自身所有必要检查通过时有效。
4. 启用/禁用候选时旧 `measurements`、`featureQuality`、`localization` 和 `measurementCompleteness` 深度相等。
5. 外置 Manifest 在任何图片诊断前完成路径、属性、哈希及任务唯一性验证。
6. 比较 JSONL 两次汇总完全一致，Schema 使用标准有限 JSON。
7. Mac A2 重跑如实报告恢复/退化；服务器不宣称达到真实 A2 恢复指标。
8. Git 中无图片、归档、运行 JSONL 或新增大于 5 MiB 文件。

## Complexity Tracking

无 Constitution 违规。选择核心外候选正是 Constitution II 允许的调用/契约/测试边界扩展。
