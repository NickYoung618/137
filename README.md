# 137壳体 A端面槽姿态引导算法

本仓库已完成Spec Kit功能`002-slot-pose-estimation`的服务器MVP：复用历史A端面视觉核心，新增只读
适配、角度契约、质量门控、fail-closed、合成回归、Manifest和评估工具。它不是另写的一套圆/极坐标/
槽检测算法，也未修改孔2或`/home/ubuntu/disk/gyj`下任何文件。

## 复用代码与新写代码

只读复用资产：

- `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py`
- SHA-256：`36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35`
- 复用函数：`outer_boundary_edge_point`、`fit_circle`、`robust_fit_circle`（内部几何拟合）、
  `bilinear_sample`、`parabolic_peak`、`object_bbox_center`、`polar_resample`、`find_outer_notch_angle`、
  `estimate_rotation_by_notch`、`estimate_rotation_by_polar`、`estimate_global_transform`、
  `build_reference_model`、`load_detection_gray`。

本仓库新写部分：

- `algorithms/slot_pose/legacy_adapter.py`：哈希校验、只读动态加载、既有函数编排、质量门控和角度换算。
- `algorithms/slot_pose/contract.py`、`main.py`：v2结果契约、fail-closed和单图CLI。
- `algorithms/slot_pose/groove_refinement.py`：唯一真槽通过后，局部亚像素侧壁点、稳健直线和
  侧壁—外圆交点精修；不复制圆拟合实现。
- `tools/generate_synthetic_slot_pose.py`、`evaluate_slot_pose.py`：小图回归和角度评估。
- `tools/make_manifest.py`、`validate_dataset.py`、`evaluate_repeatability.py`：外置数据清单与重复性。

## 服务器快速验证

```bash
cd '/home/ubuntu/disk/dzk/槽姿态引导算法'
uv sync
uv run python -m unittest discover -s tests -v

uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir /tmp/slot-pose-synthetic --angles=0,30,90 --repeats 1 --seed 137

uv run python algorithms/slot_pose/main.py \
  --image /tmp/slot-pose-synthetic/synthetic/sample_synthetic/angle_pos_030p00/repeat_001.png \
  --config /tmp/slot-pose-synthetic/synthetic-config.json \
  --task-id synthetic-30 --out /tmp/slot-pose-synthetic/result.json --strict
```

已确认合成`+30°`冒烟输出约`+29.984°`。默认`config/inspection.example.json`故意保持目标实体和机械语义未确认，
对权威参考图返回`TARGET_SEMANTICS_UNCONFIRMED`、`valid=false`、正式角度`null`。

Manifest和评估命令见`specs/002-slot-pose-estimation/quickstart.md`。正式规格、方案、任务和历史数值
证据位于`specs/002-slot-pose-estimation/`。

## A2多槽角色几何增量

`003-a2-paired-notch-stability`在不替换历史圆心、尺度、极坐标和polar链的前提下，增加了：

- `legacy_single_notch`历史对照、`paired_notches_centerline`兼容诊断和`multi_notch_roles`通用角色模式。
- 全外缘暗区候选的角中心、半宽、显著度、起止边界、环绕标志、排名和次候选差距。
- paired候选数、两侧宽度/显著度、角间距、唯一性、环带完整性、圆心/尺度和polar一致性门控。
- 任意数量候选到`datum_primary`/`datum_secondary`/`target_left`的显式分配、唯一性和环形夹角。
- v2向后兼容诊断、外置A2 Manifest/truth契约、正常/坏图分报告和Mac一键验收CLI。
- 可选归一化圆搜索ROI（默认关闭）用于屏蔽相邻工装；它只改变历史圆链的对齐输入，不修改候选原图。
- `tools/render_slot_pose_review.py`在仓库外生成候选编号叠加图、联系表、候选/`failures.csv`和非权威角色假设表。
- `tools/summarize_slot_pose_diagnostics.py`比较多个审阅包的环形候选簇、跨帧稳定性、门控成功率、错误码和P50/P95/max耗时；稳定候选仍不等于已确认业务角色。
- `multi_notch_roles`现在先将环形暗区输出为`rawCandidates`，再用径向深度、局部对比、成对边缘和轮廓一致性生成`grooveCandidates`；datum/target分配只消费后者。
- `single_real_groove`落实“每件恰好1个真实槽、另外2个暗区为遮挡阴影”的业务决定：1个接受槽
  继续拟合左右亚像素侧壁及其外圆交点，再以两个交点的环形中点计算Y下半轴有符号角；0个、多个或
  任一侧精修失败继续fail-closed。
- `tools/review_labelme_groove_pose.py`只在仓库外审阅人工外圆弧和开放槽边界：复用锁定gyj拟圆、验证槽口几何并输出图像方位/象限；人工标签不进入运行时，左下85°目标和机械纠偏保持独立。
- `tools/compare_pose_reference.py`只在仓库外将人工robust/geometric参考圆与同一原图的自动圆/自动
  槽口中点比较，分开报告圆心、半径和槽角误差；单张结果只标为开发参考。

服务器paired合成冒烟：

```bash
uv run python tools/generate_synthetic_paired_notches.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-paired" --seed 137
uv run python tools/run_slot_pose_batch.py \
  --manifest "${TMPDIR:-/tmp}/slot-pose-paired/manifest.json" \
  --data-root "${TMPDIR:-/tmp}/slot-pose-paired/images" \
  --config "${TMPDIR:-/tmp}/slot-pose-paired/config.json" \
  --output "${TMPDIR:-/tmp}/slot-pose-paired/results.jsonl"
```

当前单槽v2已确认：物理外圆圆心为原点，图像下方`+Y`半轴为datum，顺时针为正；唯一真槽必须在
画面左下且实测角落在`+85°±5°`。默认模板仍保留legacy安全模式；PLC地址/缩放/字节序/握手未确认，
因此单槽v2可输出测量、PASS/FAIL和图像纠偏诊断，但顶层正式机械角仍为空。完整规格和Mac命令见
`specs/003-a2-paired-notch-stability/`。

## 007单真槽闭环图像引导

`single-real-groove-pose-config/3`修正了旧v2把“当前不在85°附近”和“PLC映射未确认”混入失败状态的问题。
它不改外圆、暗区、真槽过滤或槽壁精修算法，只在可靠槽口径向之后增加版本化闭环状态：

- `detectionStatus`只回答外圆、唯一真槽和亚像素槽口几何是否可靠；当前槽在任何象限都可以是`DETECTED`。
- `currentAngleDeg`以检测圆心向下的图像`+Y`射线为0°，图像顺时针为正，范围为`[-180,180)`。
- 目标固定为左下85°±5°；`correctionRawDeg=wrapTo180(85-current)`。
- 当前方向在左下闭区`[80,90]`时进入死区，`correctionDeg=0`且方向`NONE`；否则输出最短
  `imageFrameCorrectionDeg`，正值`CLOCKWISE`、负值`COUNTERCLOCKWISE`。
- 可靠检测即使需要调整也保持`valid=true`。PLC映射未确认时，图像引导量仍有值，但
  `mechanicalCorrectionDeg`和`plcCommand`为空，`plcExecutionStatus=BLOCKED_MAPPING_UNCONFIRMED`。
- 每次重拍独立计算：需要调整后由调用方旋转并重拍；进入死区停止；新帧检测失败必须清空修正量，不能复用旧值。

Git安全配置片段见`config/closed-loop-guidance-v3.fragment.json`，完整契约、命令和实跑证据见
`specs/007-closed-loop-slot-guidance/`。25张JPEG全画面回放得到25/25检测成功，其中2张已到位、
23张需调整（顺时针3、逆时针20）；这只是检测/引导回放，不是生产精度结论。

## Mac A2后续验证

服务器现有25张5472×3648 A2 JPEG诊断副本和3张同源原始BMP；第4帧有一份同源BMP人工圆弧/开放槽开发参考，
但25张JPEG尚无逐图同哈希人工truth。图片、LabelMe模板和审阅产物全部留在Git外；完整正常/坏图集仍在Mac外置存储。

## 006单人工参考与逐图自动标注

当前只有1张图有人工外圆和真槽标注。它被锁定为`DEVELOPMENT_REFERENCE_ONLY`：只能报告该图本身的
人工/自动圆心、半径和环形槽角差，不能把它的角度当成另外25张图的真值。25张无真值图可以逐图导出
LabelMe可视诊断，包含自动外圆、槽口、圆心到槽口中点的径向线、两侧槽壁内点与拒绝点。所有标签均以
`AUTO_`开头，并写明`human_verified=false`、`formal_truth=false`和`runtime_input_allowed=false`。

```bash
uv run python tools/export_reference_anchored_diagnostics.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULTS" --data-root "$A2_DATA_ROOT" \
  --manual-review "$MANUAL_REVIEW_JSON" \
  --reference-comparison "$REFERENCE_COMPARISON_JSON" \
  --output-dir "$A2_REFERENCE_DIAGNOSTIC_DIR"
```

`observedCircularDeltaToReferenceDeg`仅是“当前检测值与开发参考角的环形观测差”，不是准确度误差。
没有逐图独立人工真值时，准确度是`NOT_EVALUATED`；没有明确的同样品/同位置/同工况重复组时，
静态重复性也是`NOT_EVALUATED`。详细契约和命令见`specs/006-single-reference-diagnostics/`。

## 004全画面找圆与逐图标注验收

新增的全画面策略默认关闭，仅在`single_real_groove`显式启用：低分辨率连通域只提名候选，180条锁定gyj
射线做筛选，唯一候选再由既有720射线物理圆门精修。无圆、候选溢出或候选不唯一均在槽识别前安全失败。
`tools/prepare_real_case_annotations.py`为每张真实图生成Git外、无伪truth的LabelMe模板；
`tools/evaluate_annotated_real_cases.py`只接收同图哈希一致、人工标注并由不同人员复核的外圆和开放槽边界，
逐图输出人工值、自动值及圆心/半径/环形槽角差。静态重复性按明确的同样品同条件组统计环形残差；当前25张分组
和同图truth不完整，因此该项明确为`NOT_EVALUATED`，不冒充准确率。完整命令见
`specs/004-full-frame-circle-localization/quickstart.md`。

## 005槽壁亚像素精修稳定性

`groove-sidewall-subpixel-v2`不改上游圆、暗区候选或真槽选择，也不放宽2 px侧壁P95残差门。
它在每侧全部亚像素边缘点中确定性生成有限直线假设，只保留内点数/比例、纵向覆盖、
残差和外圆交点均合格且没有同等次优模型的唯一直槽壁。审阅包每图含叠加图和
`sidewall-models.csv`：蓝色是全部检测点，绿/黄是两侧有效内点，红叉是拒绝的圆角/纹理点，白线为最终槽壁。

真实精度案例必须一图一份同哈希LabelMe人工外圆+真槽开放边界，并由不同人复核；
`tools/prepare_real_case_annotations.py`生成空白模板（不用算法值预填真值），
`tools/evaluate_annotated_real_cases.py`逐图生成人工/自动圆心、半径、槽角、象限与环形差值。
静态重复性是同样品/同位置/同条件重复帧的“检测-同图人工”环形残差极差、标准差和P95；
无明确分组或未完成标注时严格输出`NOT_EVALUATED`。完整流程见
`specs/005-groove-refinement-robustness/quickstart.md`。
同步本仓库到Mac后：

1. 将配置的`legacy_asset`路径改为Mac同源源码、标注和参考图，并核对内容SHA-256。
2. 在外置目录解压/流式读取A2，先生成Manifest，再补目标槽、机械真值、样品和split标注。
3. 按样品隔离开发/调参/验证/验收；固定角度至少20次采集做静态重复性，至少2个换位组做动态重复性。
4. 运行单图/批量结果与`tools/evaluate_slot_pose.py`，报告角度MAE/P95/max、成功/漏检/误检和节拍。

采集记录和truth补齐后，一键命令为：

```bash
uv run python tools/run_a2_acceptance.py \
  --normal-root "$A2_NORMAL_ROOT" --bad-root "$A2_BAD_ROOT" \
  --grouping "$A2_GROUPING_CSV" --truth "$A2_TRUTH_CSV" \
  --config "$A2_CONFIG" --output-dir "$A2_REPORT_DIR"
```

正常集组合必须来自采集记录、时序或显式映射，不因“约500张”就猜成25×20。

无需A2即可先在Mac验证历史源码适配链（标注和参考图由工具生成的小图提供）：

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir /tmp/slot-pose-synthetic --angles=0,30,90 --repeats 1 --seed 137 \
  --legacy-source "$A2_LEGACY_SOURCE"
uv run python algorithms/slot_pose/main.py \
  --image /tmp/slot-pose-synthetic/synthetic/sample_synthetic/angle_pos_030p00/repeat_001.png \
  --config /tmp/slot-pose-synthetic/synthetic-config.json --task-id mac-smoke --strict
```

Mac没有服务器绝对路径时，权威服务器参考图用例会显示`skipped`；这与算法失败不同。完整A2验证需要
另建本机配置，不能直接修改并提交服务器默认模板。

## 生产阻塞（不能由算法默认值代替）

- B-001 已关闭：每件只有1个真实凹槽，另外2个外观暗区为遮挡阴影。
- B-002 数据负责人：根据采集记录确认A2条件组、物理样品、split及与历史参考图的工位/视角/方向映射。
- B-003 已关闭：图像向右`+X`、向下`+Y`，以`+Y`下半轴为datum，顺时针为正。
- B-004 质量负责人：确认MAE/P95/max、静态极差、跨组残差、有效率、坏图误引导率和节拍门限。
- B-005 PLC/机器人工程师：确认字段、地址、缩放、握手、超时和失败动作。
- B-006 已关闭：datum就是图像/检测圆心向下的`+Y`半轴，不由其他暗区建立。
- B-007 已关闭：独立输出`+85°±5°`判定和图像纠偏，正值顺时针、负值逆时针。
- B-008 已关闭：唯一通过几何门的真实槽就是目标槽，另外两个暗区不得补角色。

剩余关闭顺序：B-002 → 冻结Mac原始BMP验证集/人工参考规程 → B-004验收 → B-005上线。关闭前可以
输出版本化图像帧测量和最短引导量，但不能宣称生产精度、把图像方向等同于执行机方向或向PLC写入。

## 008回放完整性与数据集隔离

008修复的是验收可信度和有证据的歧义恢复，不使用700张回放反向调圆/槽阈值：

- review、CSV、叠加图和统计以顶层v3最终结果为准；质量拒绝即使保留中间槽角，也只能计入
  `DETECTION_FAILED/NOT_AVAILABLE`，中间几何另列为非权威诊断。
- `datasetClass`、产品判定、图像质量和`poseUsable`分开；只有带authority/provenance的显式
  `poseUsable=false`标签才能形成权威误引导率，“坏图目录”本身只有条件统计意义。
- `configSha256`标识源文件字节，`effectiveConfigSha256`标识运行时展开默认后的路径无关行为；
  `tools/materialize_slot_pose_config.py`可在不读图时展开并核对。
- 多粗槽候选可选地逐一经过现有亚像素物理精修，仅唯一幸存者可恢复。该开关默认关闭，等待独立标注验证。
- 当前数据分层：合成测试+唯一人工标注为development；700张为已检查、锁定的acceptance回归；
  独立validation/test尚不存在，需新增物理样品和逐图复核标注。25张同源JPEG不能充当独立validation。

命令和剩余BLOCKED见`specs/008-a2-replay-integrity-hardening/quickstart.md`。
