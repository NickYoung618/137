# Implementation Plan: A 端面质量分层与批量评估

**Branch**: `main` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-quality-policy-batch/spec.md`

## Summary

在保持桌面 `core.py` 字节不变的前提下，增加可配置的端面定位质量适配层，把技术执行、端面定位、
特征测量完整性拆成独立状态。升级单图 JSON 契约，并增加基于外置 Manifest 的批量执行及基于结果流
的离线统计。参考图由服务器可访问的 `算法.zip` 临时提取；A2 只保存用户提供的无图汇总证据。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；不新增运行依赖

**Storage**: 外置图片/标注、Git 内小体积 JSON 策略/Schema/证据、Git 外运行结果 JSONL/JSON

**Testing**: Python unittest，服务器参考资产集成测试，临时 Manifest/合成结果测试

**Target Platform**: Linux 服务器与本机兼容 Python 环境

**Project Type**: 离线算法库与 CLI

**Performance Goals**: 批量报告每图耗时并复现用户反馈的平均耗时口径；不改变核心检测耗时目标

**Constraints**: 核心 SHA-256 不变；不访问其他视觉引导仓库；不提交/上传 A2 原图；严格 JSON；无质量 OK/NG

**Scale/Scope**: 当前验收为 1 张参考图和 25 条 A2 无图结果证据，可扩展任意 Manifest 图片数

## Constitution Check

| Gate | Pre-design | Post-design |
| --- | --- | --- |
| 规格先行与追踪 | PASS：14 条 FR、6 条 SC、3 个故事 | PASS：任务逐项覆盖 |
| 核心原样复用 | PASS：只读调用，哈希固定 | PASS：适配、契约和工具均在核心外 |
| 输入输出可复现 | PASS：策略、Manifest、输入和核心指纹 | PASS：v2 单图与 v1 批量契约定义完整 |
| 安全失败 | PASS：技术/定位/测量三层状态 | PASS：无效特征不改写，定位失败可解释 |
| 数据最小化 | PASS：A2 只收无图证据 | PASS：测试临时提取后删除，输出被忽略 |

## Phase 0: Research Findings

研究结论见 [research.md](research.md)。核心失败条件已定位到以下只读路径：短线横向边缘、46 径向
NCC、中间环模板/径向候选。定位规则只使用核心输出的变换指标和目标图尺寸；特征质量继续采用核心
原始门限，不在适配层强行翻转。

## Phase 1: Design & Contracts

- 数据实体与状态不变量见 [data-model.md](data-model.md)。
- 单图结果升级为 `a-end-face-result/2`。
- 质量策略为 `a-end-face-quality-policy/1`。
- 批量汇总为 `a-end-face-batch-quality-summary/1`。
- 运行与复现步骤见 [quickstart.md](quickstart.md)。

## Project Structure

### Documentation (this feature)

```text
specs/004-quality-policy-batch/
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
├── core.py                 # byte-identical desktop core; never edit
├── adapter.py              # reusable reference + quality adapter
├── quality.py              # policy loading, classification, diagnostics
├── contract.py             # result/strict JSON contract
└── main.py                 # single-image CLI
config/
└── end_face_quality.example.json
contracts/
├── a-end-face-result.schema.json
├── a-end-face-quality-policy.schema.json
└── a-end-face-batch-quality-summary.schema.json
tools/
└── evaluate_end_face_batch.py
tests/
├── test_end_face_quality.py
├── test_end_face_batch.py
├── test_end_face_contract.py
└── test_end_face_cli.py
```

**Structure Decision**: 保持现有单项目结构；适配层复用一次构建的参考模型，单图与批量入口共享相同
质量策略和契约，不引入第二套检测算法。

## Implementation Order

1. 先以测试固定核心质量来源、A2 聚合计数和新契约不变量。
2. 实现质量策略、定位检查、特征状态提取与诊断目录。
3. 由可复用适配器连接核心、契约和单图 CLI。
4. 实现 Manifest 批量执行、JSONL 重统计和汇总输出。
5. 运行参考图、A2 无图证据、合成 Manifest、核心哈希和 Git 大文件门禁。

## Quality Gates

1. `core.py` SHA-256 保持 `f408631e…f8fbc`。
2. 全部 unittest 通过；无图环境只允许参考资产用例明确 skip。
3. 服务器参考图 `technicalStatus=succeeded`、`localization.valid=true`，19/30 保持 `coreValid=false`。
4. A2 无图证据复现全部用户反馈计数和平均耗时 2630.5 ms。
5. 临时 Manifest 哈希变化在任何检测调用前失败。
6. 同一 JSONL 两次统计得到一致的确定性质量计数。
7. Git 中无图片、RAR/ZIP、逐图结果流或超过 5 MiB 的业务资产。

## Complexity Tracking

无 Constitution 违规；不需要复杂度豁免。
