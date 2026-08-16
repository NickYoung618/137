# Specification Quality Checklist: D7 v6回退首版有效性诊断

**Purpose**: 在计划阶段前验证规格完整性

**Created**: 2026-08-17

**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] 不含需要算法默认猜测的业务定义
- [x] 面向首版发布决策而非实现细节堆叠
- [x] 明确诊断范围和禁止修改项
- [x] 必填章节完整

## Requirement Completeness

- [x] 没有`NEEDS CLARIFICATION`
- [x] Mac事实、服务器证据和推断边界分开
- [x] `measurementValid`与`evidenceComplete`定义独立
- [x] 绝对准确度、重复性和生产判定不混用
- [x] 成功标准可验证

## Feature Readiness

- [x] 每项需求都有只读证据或定向契约测试
- [x] 失败保护和无真值限制明确
- [x] 不需要修改算法、门限、Phi、配置或Schema
- [x] 可以进入计划和诊断分析
