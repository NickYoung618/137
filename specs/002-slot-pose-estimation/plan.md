# Implementation Plan: A端面槽姿态估计

**Branch**: `main` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/home/ubuntu/disk/dzk/槽姿态引导算法/specs/002-slot-pose-estimation/spec.md`

## Summary

在不上传Mac侧A2真实图片的前提下，以历史A端面3051行算法为唯一视觉核心，实现只读资产校验、
薄适配和fail-closed槽姿态MVP。适配器直接复用其圆/中心、极坐标、外缘notch和旋转估计函数，
把现有输出映射为质量诊断，并按受控配置计算相对机械零位的带符号角度。默认机械语义未确认，
因此只允许诊断结果；不另写独立圆、极坐标或槽检测逻辑。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: 与历史A端面源一致的NumPy 2.x、Pillow 12.2；不新增OpenCV视觉实现
**Storage**: 外置不可变图像目录；仓库内JSON配置/Schema/Manifest和小体积CSV/JSON报告
**Testing**: Python `unittest`，合成图单元/集成测试，已有A端面参考图只读冒烟
**Target Platform**: 新Linux服务器开发；Mac本地离线回放与正式数据验证
**Project Type**: 单体Python CLI与可导入算法库
**Performance Goals**: 5472×3648单图P95不超过8.0秒（当前只读参考基线约6.5秒包含建模和多路诊断调用）；批处理逐图加载
**Constraints**: A2真实数据不上传服务器；无GUI依赖；机械约定未确认时禁止有效引导；不修改孔2或历史端面代码
**Scale/Scope**: 单图单A端面单目标槽，只输出绕端面法向的一个角度自由度

## Constitution Check

*GATE: Phase 0前与Phase 1后均检查。*

| Principle | Pre-design gate | Post-design gate | Evidence |
|---|---|---|---|
| I. 规格先行与场景闭环 | PASS | PASS | `spec.md`含4个独立场景、FR/SC及B-001..B-005阻塞 |
| II. 坐标系与姿态契约明确 | PASS | PASS | `spec.md`定义角度语义；配置契约要求frame/zero/sign及confirmed门禁 |
| III. 质量评估与安全失败 | PASS | PASS | 结果契约规定无效时角度为空，错误码区分各检测阶段 |
| IV. 数据溯源与可复现验证 | PASS | PASS | 外置Manifest、图像/配置/算法指纹、合成种子和评测报告 |
| V. 模块化与集成可控 | PASS | PASS | face、polar、slot、pose、quality和contract分层；PLC仅适配层 |

没有需要豁免的Constitution违规。现场未确认项通过运行时阻塞而非默认假设处理。

## Reused Algorithm Asset

| Asset | Absolute path | SHA-256 |
|---|---|---|
| 3051行权威源 | `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py` | `36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35` |
| LabelMe标注 | `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/annotation.json` | `d949f779a309dc8d3741067e863aa8918aee103f60177dad7068f1e999302390` |
| A端面参考图 | `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/reference.bmp` | `cf8b4e0437f1e04fbd55782b1fb33e13c0693ecaf3a436786b2d38dd933053f0` |

复用函数及当前行号：`robust_fit_circle:372`、`object_bbox_center:740`、`polar_resample:841`、
`find_outer_notch_angle:866`、`estimate_rotation_by_notch:935`、`estimate_rotation_by_polar:960`、
`estimate_global_transform:1017`、`build_reference_model:1351`、`load_detection_gray:1883`。
参考图实算证据见`evidence/historical-a-end-face-reference-baseline.json`。

## Adapter Data Flow

1. **资产门禁**：在动态加载前校验源、标注和参考图SHA-256；禁止写字节码到权威目录。
2. **参考模型**：调用`build_reference_model`，保留既有圆角色、中心和内外半径语义。
3. **目标端面与旋转**：调用`load_detection_gray`和`estimate_global_transform`，复用既有外圆/内圆拟合、
   `polar_resample`及`estimate_rotation_by_polar`链，得到目标中心、尺度、相对参考图旋转和polar分数。
4. **外缘槽/notch**：调用`find_outer_notch_angle`获取目标notch方位、半宽和显著度；调用
   `estimate_rotation_by_notch`形成相对旋转第二意见。
5. **候选质量**：适配层只组合既有输出：notch显著度/半宽、polar分数、notch与polar旋转差、尺度范围
   和中心是否在图内。现有函数不提供第二候选分数，无法直接证明多槽唯一性；真实数据出现歧义时
   先记录证据，再评审对既有函数的最小增强。
6. **角度计算**：图像角度沿历史函数坐标约定增大；适配器按配置零位和正方向计算
   `wrap(direction_sign × (slot_azimuth - mechanical_zero), [-180, 180))`。
7. **质量与fail-closed**：配置未确认、哈希不匹配、notch缺失、分数不足、两种旋转估计分歧或角度
   越界时，正式角度为空；诊断可保留候选图像方位用于离线调试。
8. **输出与评估**：按版本化JSON契约写单图结果；批量评估从结果和真值计算误差、重复性、成功/失败
   和耗时。服务器只跑合成图与只读参考图冒烟，Mac侧再跑A2正式回归。

## MVP Parameter Strategy

- 参数全部进入配置：权威资产路径/哈希、notch显著度、polar分数、notch/polar最大分歧、尺度范围、
  置信度门限和角度有效范围；历史核心内部参数暂不在适配层复制。
- 默认生产模板的`conventions_confirmed=false`、零位为空、PLC映射未确认，必然fail-closed。
- 合成测试配置显式使用图像x轴为零位、数学逆时针为正，仅用于验证计算和契约，不可复制为现场值。
- `mm_per_px`对纯角度结果非必需；若以后输出平移量，必须引入独立标定链和测试。

## Data and Annotation Plan

- Mac真实数据建议根目录：`/Users/daizekai/Desktop/壳体项目/A2/`；若流式读取RAR，Manifest中的
  逻辑相对路径必须能稳定定位压缩包成员，且记录压缩包SHA-256。
- 推荐目录：`sample_id/angle_or_position/image_###.bmp`。同一物理样品及其所有派生图只能属于一个split。
- 标注使用版本化JSON，包含face circle、slot polygon、slot centerline、机械真值、sample/position/repeat、
  calibration_id和split。未知生产字段使用`null`并阻止验收，不从文件名猜测角度。
- 建议数据比例按物理样品分组：开发40%、调参20%、验证20%、最终验收20%；样品很少时采用按样品
  留一验证，但最终验收集在算法冻结前不可查看或调参。
- 每个机械角度/装夹条件至少20次独立采集；动态验证至少两个重新装夹位置。建议扫角覆盖零位、
  正负工作边界和`±180°`环绕附近，实际范围由现场确认。

## Evaluation Plan

- **角度误差**：使用环形差值，报告MAE、P95和最大绝对误差，并按样品/角度/工位分层。
- **静态重复性**：同一样品、角度、装夹的20次结果，报告n、标准差、6σ和极差。
- **动态重复性**：重新装夹/角度组均值的标准差、6σ和极差，不把算法失败当作零角度。
- **检测指标**：正样本成功率；有槽但未输出的漏检率；无目标槽/歧义图却输出有效结果的误检率；
  各错误码占比和覆盖率。
- **节拍**：记录逐图墙钟时间，报告均值、P50、P95、最大值及测试机器信息。
- 服务器合成门禁采用SC-001..SC-004；真实A2生产限值未确认时报告`NOT_EVALUATED`。

## Model Escalation Gate

只有现有A端面传统方案在冻结的真实验证集上经适配层门限调优后，仍因可归类的外观变化无法达到现场成功率或
误差门限，才考虑学习模型。进入模型评审前必须有：稳定标注规范、按物理样品隔离的数据集、覆盖
主要材质/光照/油污/划痕的足量样本、传统方案错误分析和可部署算力预算。模型不得替代坐标约定、
机械零位或fail-closed契约。

## Interface and Failure Protection

- 算法库返回版本化结果对象，CLI仅负责文件输入输出；批处理不直接连接PLC。
- 错误码至少包括：`INPUT_INVALID`、`FACE_NOT_FOUND`、`SLOT_NOT_FOUND`、`SLOT_ROTATION_INCONSISTENT`、
  `SLOT_FIT_FAILED`、`QUALITY_REJECTED`、`POSE_CONVENTION_UNCONFIRMED`、`ANGLE_OUT_OF_RANGE`。
- 正式有效结果要求本次图像、任务、配置和算法版本一致，禁止缓存上次角度。
- PLC/机器人适配在后续独立模块完成；B-005关闭前只维护逻辑契约，不实现地址写入或DInt编码。

## Project Structure

### Documentation (this feature)

```text
specs/002-slot-pose-estimation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── slot-pose-result.md
│   ├── slot-pose-annotation.schema.json
│   └── slot-pose-config.schema.json
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── __init__.py
├── legacy_adapter.py
├── contract.py
└── main.py

config/
└── inspection.example.json

contracts/
├── slot-pose-output.md
└── slot-pose-result.schema.json

tools/
├── generate_synthetic_slot_pose.py
├── evaluate_slot_pose.py
├── make_manifest.py
└── validate_dataset.py

tests/
├── test_legacy_adapter.py
├── test_slot_pose_contract.py
├── test_slot_pose_cli.py
├── test_slot_pose_evaluation.py
└── test_data_tools.py
```

**Structure Decision**: 保留现有单体Python仓库；`legacy_adapter.py`只读加载并校验历史视觉核心，
不复制3051行实现；契约与CLI解耦，复用已有Manifest和重复性工具，不引入服务端、数据库、GUI或控制器连接。

## Complexity Tracking

无Constitution违规，无需复杂度豁免。
