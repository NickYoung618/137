# Implementation Plan: D7 v6回退首版有效性诊断

**Branch**: `main` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

以只读方式审计010的20条D7 v6 fallback记录、v6检测代码和现有证据契约，决定该路径在首版中的
有效性语义。采用“保留技术`measurementValid`、保持证据不可审核、禁止生产精度解释”的条件保留方案。
本增量只提交SpecKit文档，不改运行时代码、门限、Phi、配置、Schema或测试。

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: 只读使用Python标准库解析外置JSONL；项目运行时仍为NumPy/Pillow

**Storage**: SpecKit Markdown；证据和运行输出全部仓库外

**Testing**: 现有`unittest`定向契约测试、JSONL只读统计、Git差异审计

**Target Platform**: Linux服务器与Mac独立复验环境

**Project Type**: Python CLI/算法适配层

**Performance Goals**: 不改变运行时，性能影响为零

**Constraints**: 不调门、不用真值调参、不改Phi、不读取holdout、不提交外置资产

**Scale/Scope**: Mac独立40帧状态事实；服务器010/030各20帧只读记录；一张权威真值锚点

## Constitution Check

- 规格、证据、决策和验证可追踪：PASS。
- 权威参考与目标真值的运行时边界不变：PASS。
- 失败保护不改写，无效结果不恢复：PASS。
- 像素结果不产生毫米或OK/NG：PASS。
- 图片、JSONL和运行输出留在Git外：PASS。
- 本增量不修改检测核心或适配算法：PASS。

## Diagnostic Design

### 1. 追溯原质量门

从`algorithms/hole_2/main.py`确认两侧边界检测的极性、点数、边缘峰、稳健拟合、残差、轴向和搜索窗条件；
从`algorithms/hole_2/current_capture.py`确认fallback只接受`ok:dual_boundary_fit`和有限业务值。

### 2. 追溯证据缺口

区分v6计算过程中使用的边缘点与结果契约实际保留的`rawEdgeEvidence`。缺少后者只能判为不可审核，
不能倒推出前者不存在，也不能伪造边界。

### 3. 发布矩阵

把首版权限拆为技术数值、可视审核、绝对精度和生产处置四列。对v6 fallback采用条件保留，而非二选一改写。

### 4. 验证

运行定向契约测试证明失败不恢复、有效性与证据完整性独立；执行SpecKit analyze和Git范围审计。

## Project Structure

```text
specs/021-d7-v6-release-validity/
├── spec.md
├── research.md
├── data-model.md
├── plan.md
├── quickstart.md
├── contracts/
│   └── initial-release-decision.md
├── checklists/
│   └── requirements.md
├── analysis.md
└── tasks.md
```

**Structure Decision**: 纯文档诊断增量；不新增源码或测试文件。

## Constitution Re-check

设计后复核无例外：不修改检测逻辑，不扩大数据范围，不引入生产判定，外置证据不入Git。

## Complexity Tracking

无Constitution例外。
