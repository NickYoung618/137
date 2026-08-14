# Implementation Plan: A2双缺口槽姿态稳定检测与真实数据验收

**Branch**: `003-a2-paired-notch-stability` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-a2-paired-notch-stability/spec.md`

## Summary

在现有只读历史A端面适配链上做最小增量：继续使用已有圆心、尺度、极坐标和polar配准，
新增环形外缘角度剖面的全暗区候选提取和严格双缺口配对。两种显式诊断模式共存；
旧单notch路径作不回退对照，paired路径必须通过候选、几何、唯一性、环形边界、圆心/尺度和
polar一致性门控。结果保留v2必填字段，只扩展可忽略的diagnostics。同时增强外置Manifest、
truth CSV校验、环形残差评估和正常/坏图分报告，为Mac真实A2批量验收提供一键命令。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；不新增视觉框架或学习依赖
**Storage**: 外置不可变原图目录；仓库只存JSON Schema、配置模板、Manifest/truth契约和小体积报告
**Testing**: Python `unittest`，历史合成扫角回归，paired合成真值、边界/失败分支、Schema/CLI/批处理测试
**Target Platform**: Linux服务器开发回归；macOS外置A2数据离线验收
**Project Type**: 单体Python算法库和CLI工具
**Performance Goals**: `5472×3648`单图P95不超过8.0秒；批处理逐图持久化且单图失败不中断整批
**Constraints**: fail-closed；目标语义/机械契约未确认时正式角为空；不改历史资产和两个外部工作区；不接PLC
**Scale/Scope**: 服务器小型合成集；Mac端当前盘点约500张正常图和201张坏图，实际分组由采集记录确认

## Constitution Check

*GATE: Phase 0前与Phase 1后均检查。*

| Principle | Pre-design | Post-design | Evidence |
|---|---|---|---|
| I. 规格先行与场景闭环 | PASS | PASS | `spec.md`含4个独立场景、25条FR、10条SC和B-001..B-005 |
| II. 坐标系与姿态契约明确 | PASS | PASS | 诊断角与正式机械角分离；环形角范围和方向在契约中显式化 |
| III. 质量评估与安全失败 | PASS | PASS | paired逐项门控；失败角/置信度为空；坏图误引导单独统计 |
| IV. 数据溯源与可复现验证 | PASS | PASS | 外置Manifest、truth、物理样品/split隔离、图像/配置/算法指纹 |
| V. 模块化与集成可控 | PASS | PASS | 新候选模块只消费已有圆心/尺度/极坐标能力；v2诊断向后兼容；无PLC修改 |

无Constitution违规或需豁免项。外部未知项通过BLOCKED和运行门控保留，不阻止服务器诊断实现。

## Design Decisions

1. **保留legacy原路径**：`legacy_single_notch`仍直接调用历史`find_outer_notch_angle`，用同一扫角回归证明不回退。
2. **最小多候选增强**：新模块调用历史`polar_resample`获得外缘环带，在本仓库内对角度剖面做环形平滑、
   稳健暗区阈值和全连通段枚举；不复制或替换圆/配准/极坐标链。
3. **先验证环带完整性**：用已有圆心、外半径和图像尺寸计算外缘环带是否完全入镜，再采样；裁切不用均值填充掩盖。
4. **确定性配对**：对所有候选两两组合，先用可配置门槛筛选，再依间距偏差、宽度不对称和显著度不对称得分。
   仅当最佳得分达标且与次优差距达标时返回唯一配对。
5. **中心线角定义**：两候选角在最短环形弧上的中点；候选按角度和稳定ID排序，避免输入枚举顺序影响结果。
6. **参考/目标配对一致性**：参考图和目标图均提取唯一配对，二者中心线环形差作paired rotation，与polar rotation比较。
7. **v2不升版**：新数据只放入已允许任意对象的`diagnostics`；结果顶层、`result`、`error`和旧诊断键不删改。
8. **评估使用残差**：角误差先环形化到`[-180,180)`；静态组围绕环形均值展开，跨真值组只统计残差组均值，
   失败始终作计数而非0度。

## Project Structure

### Documentation (this feature)

```text
specs/003-a2-paired-notch-stability/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── diagnostics-v2.md
│   ├── a2-manifest.md
│   ├── angle-truth-csv.md
│   └── evaluation-report.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── angular_profile.py          # 新的外缘候选与配对纯函数
├── legacy_adapter.py           # 模式编排、已有中心/尺度/polar复用
├── contract.py                 # v2 fail-closed和向后兼容诊断
└── main.py                     # 单图CLI

contracts/
├── slot-pose-config.schema.json
└── slot-pose-result.schema.json

config/
└── inspection.example.json

tools/
├── generate_synthetic_slot_pose.py
├── generate_synthetic_paired_notches.py
├── make_manifest.py
├── validate_dataset.py
├── run_slot_pose_batch.py
├── evaluate_slot_pose.py
└── run_a2_acceptance.py

tests/
├── test_angular_profile.py
├── test_paired_slot_pose.py
├── test_slot_pose_contract.py
├── test_slot_pose_cli.py
├── test_slot_pose_batch.py
├── test_slot_pose_evaluation.py
└── test_data_tools.py
```

**Structure Decision**: 保持现有单体Python布局。多候选/配对的数学部分与历史动态加载分离，便于纯合成边界测试；
适配器仍是历史视觉函数的唯一调用入口。数据和评估工具在现有CLI上增量，不引入服务、GUI或控制器连接。

## Complexity Tracking

无需记录的Constitution违规或复杂度豁免。
