# Implementation Plan: 现拍样品姿态注册与孔2尺寸检测

**Branch**: `main` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-current-capture-registration/spec.md`

## Summary

在既有 `algorithms/hole_2/main.py` v6 上增加独立现拍适配层：以旧参考标注中的圆/圆弧自动形成空间支持组，先用主同心圆组全局定位中心与尺度，再对四个正交方向分别做局部边缘一致性搜索和稳健相似变换精配准。候选必须获得至少三个空间分散支持并通过候选间隔、残差、角度和尺度质量门限。有效姿态作为可选种子传给 v6 检测器，默认 v6 CLI 行为不变。新 CLI 输出版本化 JSON、旧参考坐标兼容列及目标图坐标；独立验收 CLI 才能读取外置现拍 LabelMe 真值。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；不新增 OpenCV/SciPy 运行时依赖

**Storage**: 外置 BMP/LabelMe JSON 输入；仓库外 JSON 输出；仓库内 JSON Schema 与版本化配置

**Testing**: Python `unittest`，合成相似变换、假背景、契约测试、旧参考冒烟和外置单图离线验收

**Target Platform**: Linux 服务器与 macOS，离线 CPU CLI

**Project Type**: 单体 Python 算法库与命令行工具

**Performance Goals**: 3072×2048 单图在服务器 CPU 上 30 秒内完成四方向注册、检测和 JSON 写出；验收另行执行

**Constraints**: 复用 v6；现拍 JSON 不得进入运行时；保留旧业务列；不新增大文件；低质量安全失败；输入与资产均做 SHA-256 追溯

**Scale/Scope**: 本轮一张负责人确认的现拍图、两个确认对象（`7` 与 `Φ12.2`）；合成测试覆盖四方向及失败分支，不声明 20 张重复性

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **规格先行与需求追踪 — PASS**：FR/SC、用户故事、任务和测试使用稳定编号映射；生产毫米公差明确排除。
- **量值、单位与基准明确 — PASS**：参考/目标坐标系和 `ref_px`/`target_px` 分离；正逆变换、资产与配置版本显式输出。
- **数据溯源与结果复现 — PASS**：旧参考、目标图、配置、算法和契约都有 SHA/版本；现拍图与 JSON 外置。
- **测试先行与边界验证 — PASS**：先增加四方向、假匹配、失效映射、契约和验收结构测试，再写实现。
- **安全失败与全程可观测 — PASS**：注册和两个测量状态独立；无效注册不输出有限最终尺寸；候选诊断全量保存。
- **外部契约与数据保护 — PASS**：检测与验收为两个 CLI；运行时参数无目标标注入口；输出目录与大文件均被忽略。

Phase 1 复核：数据模型、两个 JSON Schema 和 quickstart 已明确上述边界，无 Constitution 例外。

## Phase 0: Research Decisions

详见 [research.md](research.md)。所有技术未知项均已由旧参考资产、无真值现拍图诊断、合成可测性与 v6 接口审计解决；没有待澄清项。

## Phase 1: Design

- 数据实体、状态和坐标关系见 [data-model.md](data-model.md)。
- 检测与验收输出契约见 [contracts/current-capture-result-v1.schema.json](contracts/current-capture-result-v1.schema.json) 与 [contracts/current-capture-acceptance-v1.schema.json](contracts/current-capture-acceptance-v1.schema.json)。
- 服务器/Mac 的真值隔离运行步骤见 [quickstart.md](quickstart.md)。

## Project Structure

### Documentation (this feature)

```text
specs/002-current-capture-registration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── current-capture-result-v1.schema.json
│   ├── current-capture-acceptance-v1.schema.json
│   └── current-capture-batch-summary-v1.schema.json
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/hole_2/
├── main.py                         # v6，新增可选外部姿态种子；默认行为不变
└── current_capture.py              # 注册、质量门限、目标坐标适配
config/
└── current_capture_registration.v1.json
tools/
├── run_current_capture.py          # 运行时检测，不接受目标标注
├── evaluate_current_capture.py     # 检测后离线真值对照
└── batch_current_capture.py        # Mac 外置分组批量质量回归
tests/
├── test_current_capture_registration.py
├── test_current_capture_contract.py
├── test_current_capture_acceptance.py
├── test_current_capture_batch.py
└── test_current_capture_real_e2e.py
```

**Structure Decision**: 保持现有单项目布局。新注册逻辑与 v6 文件分离，只在 v6 `extract_image` 增加默认关闭的可选姿态种子，从而复用其特征检测器且不改变旧 CLI。

## 2026-08-14 Controlled measurement hardening increment

- 保留已验证的四方向注册、v6 姿态种子与现拍适配层，不重复开发核心。
- 将 `Φ12.2` 半径搜索分为受边界约束的主搜索和条件恢复搜索；恢复的唯一触发是主下界饱和。
- 保留尺寸7新切线双边界为首选；失败时仅选择 v6 已通过原双边界质量状态的结果，不调整注册门限。
- 单元测试分别覆盖触发、禁止触发、扩展仍饱和、v6 合格回退和 v6 不合格拒绝；外置单图 E2E 固定尺寸7长度 `≤2 px` 与 `Φ12.2` 直径 `≤1 px` 验收门。

## Complexity Tracking

无 Constitution 例外；不引入新框架、数据库或生产服务。
