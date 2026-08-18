# 137 壳体检测算法

本仓库承载 137 壳体 A 端面、孔2柱面/端面检测与槽姿态引导；三类算法保持独立入口、配置和规格。

## 检测核心来源

### 槽姿态

- `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py`
- SHA-256：`36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35`
- 复用函数：`outer_boundary_edge_point`、`fit_circle`、`robust_fit_circle`（内部几何拟合）、
  `bilinear_sample`、`parabolic_peak`、`object_bbox_center`、`polar_resample`、`find_outer_notch_angle`、
  `estimate_rotation_by_notch`、`estimate_rotation_by_polar`、`estimate_global_transform`、
  `build_reference_model`、`load_detection_gray`。

### 孔2交付状态

当前已完成数据无关工具链、配置模板和现有 `hole_2` 算法适配。尺寸7已按确认语义实现
双边界拟合，Φ12.2已提供半径和显式像素直径列。正式毫米标定、20张重复性验证和生产
OK/NG仍等待真实图片、图纸确认及验收数据。

### A端面尺寸

`algorithms/end_face/core.py` 原样来自桌面算法包
`/home/ubuntu/disk/zzx/算法/算法.zip` 内的 `A端面/repeatability_evaluation.py`，
SHA-256 为 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`。
权威核心没有被改写；新增代码提供独立调用、质量分层、严格 JSON 契约、批量评估，以及核心之外的
19/30 参考梯度候选。候选有独立状态和失败保护，不会写回核心量测。

## 槽姿态引导

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
- 020增加默认关闭的固定阴影nuisance template和真实槽双侧壁同源性门。约31度/328度只是允许漂移的
  夹具先验，绝不会形成禁止检测区；算法保留所有原始暗区候选，并输出每侧局部灰度/梯度剖面供审计。
  真槽靠近阴影时只能做有界多假设残差分解，缺人工模板、缺一处阴影或假设不唯一均安全失败。
  当前服务器JPEG实验过于保守，只用于说明失败门生效，不构成生产精度或准确率结论。
- 022增加默认关闭的同源性二级裁决：020原始对比度拒绝和0.12门限完整保留；仅当原判定只失败
  `edge_contrast_asymmetry`、其他原检查全过且端点结构差满足独立硬门时，显式
  `single_real_groove`实验配置才可输出`ACCEPTED_OVERRIDE`并继续计算图像角和有符号调整量。
  它始终是`developmentOnly`、非权威且PLC阻断；默认配置、其他诊断模式和未开启路径不变。

025将初版收敛为单拍：不需要也不等待180°双拍。`tools/prepare_single_shot_initial_config.py`
只在用户显式运行时，把现有单槽v3、原020同源性门和022二级裁决组合成Git外配置；
它拒绝改动原0.12门、外部代码路径、非85°目标或已确认PLC映射。完整且唯一的真槽可输出
图像当前角和调整角；固定物遮挡、单壁、混边、0/多候选或圆失败必须`valid=false`且角度为null。
该剖面仍是功能分支上的初版候选，PLC始终为null；完整命令与审核边界见
`specs/025-single-shot-initial-deliverable/quickstart.md`。

025剖面v2对最多3个粗真槽候选逐个运行既有亚像素双壁与同源性链，只有唯一完整通过
才输出单拍图像引导；0个或多个通过仍报错。该能力不读取人工标注、不依赖候选编号，
也没有放宽原始槽识别、同源性或外圆门限。

026在默认关闭的`physical_outer_circle.edge_family_selection`中修复逐射线边族切换：同一张图的
稀疏筛选与最终720射线都保留有界多峰，以跨角度完整圆几何要求唯一边族，再调用原鲁棒拟圆和原质量门。
无族、多族或容量溢出均在槽链前失败；单拍v3剖面显式开启该策略，v2保持不变，人工圆只用于Git外离线核对。

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

## 021双拍配对槽姿态实验

现场已确定同一物理零件拍摄两次并在中间旋转，用跨帧运动规律区分随件真槽和相机坐标近似固定的夹具阴影。
旋转角、方向和重复误差尚未确认，因此021只在独立功能分支提供默认关闭框架：每帧继续复用现有外圆、暗区、
真槽几何、亚像素侧壁和同源性诊断；第二帧候选按配置的有符号旋转量映回第一帧零件坐标，只有唯一匹配且
至少一帧无遮挡才输出第二拍后的图像引导。参数`UNCONFIRMED`、缺帧、错配、0/多解或两帧均遮挡全部
fail-closed，PLC字段始终为空。约31°/328°不形成ignore mask。

`tools/prepare_slot_pose_prefill_review.py`在Git外为part-019 374/369生成原分辨率raw/simplified、
RAW/SIMPLIFIED两栏联系表和精简`AUTO_` LabelMe预填。simplified只显示019最终左右槽壁/端点及020
观测暗区角度区间，不画外圆、定位框、其他raw射线或实心fixture区域。它优先使用
`pairEvidence.selectedCandidateIds`；配对不完整时绝不把最近的`NOT_MATCHED`候选冒充fixture。
橙色括号只表示一维`start/center/end`，图上明确“fixture身份未确认、像素边界未知”。
自动shape保持`human_verified=false`，无需从空白图重画外圆。完整契约和Mac命令见
`specs/021-paired-capture-slot-pose/quickstart.md`。

`detector.local_second_wall_diagnostic`是另一个默认不存在/关闭的实验开关：仅在020同源性拒绝后，
复用现有亚像素侧壁和灰度剖面，在粗暗区两端分别向内、向外建立有界且支持0°/360°环绕的搜索域，
逐seed独立拟合物理墙，再以无序canonical wall pair核验同一局部方形开口。粗暗区start/end只作为
搜索锚点，不再当成不可越过的槽壁边界；搜索范围和候选上限均由`local-second-wall-diagnostic/2`
显式配置并受物理槽宽上限约束。即使唯一实验候选形成，顶层仍保持
`GROOVE_SOURCE_INCONSISTENT`、`valid=false`，不得产生权威姿态或PLC命令。
`local-second-wall-diagnostic/4`进一步把“存在墙状像素证据、但没有完整同源唯一槽口”标为
`PARTIALLY_OBSERVED`。该状态不指定哪条是真槽壁，`authoritative=false`、
`posePromotionAllowed=false`、`experimentalCandidate=null`；完整槽中点、当前角、修正角和PLC均为空。
Git外人工确认可以说明某个cluster是真壁，但人工标签绝不进入生产运行时。
`tools/extract_local_second_wall_trace.py`可从Git外JSONL按文件basename导出不含原图和绝对路径的
搜索域、逐seed/拟合、物理墙cluster和canonical pair trace，用于判断另一真壁是未生成、生成后被拒绝
还是被错误归并；该工具不允许调门限。简化审阅图只额外显示最终墙对候选，使用`AUTO_experimental_`
且明确非权威，不渲染全部seed射线。

`tools/build_complete_groove_review_queue.py`从冻结manifest/JSONL按物理sample盘点双壁证据，显式排除
已知partial/mixed样本，并在候选sample内只按图像SHA稳定选择少量待审帧。输出JSON、CSV和review manifest
全部在Git外，`accuracyEvaluated=false`且不含预测角择样；人工必须确认两壁同属一个完整方形槽及槽口端点后，
这些帧才可成为完整槽姿态真值。

145/147已完成“同一真实槽、两侧完整、槽肩端点、AUTO槽壁语义干净”的人工确认，但AUTO坐标仍不是真值。
`tools/prepare_clean_groove_pixel_review.py`只核对review-index、原图与AUTO文件SHA，随后在Git外生成
`shapes=[]`的独立LabelMe任务；它不解析或复制AUTO几何。人工每墙独立点至少3个支撑点并各点1个左右槽口
端点。校验器把墙/端点完成与同图独立外圆弧/圆心参考分开；缺外圆参考时不得评价最终角度精度。旧
fixture污染标注工具继续DORMANT/INAPPLICABLE，所有复核产物禁止runtime、调参和PLC输入。

145/147现已完成独立3+3墙点与左右槽口端点复核。145另有13个独立外圆可见弧点，但只覆盖约30°；
它可拟圆诊断，但未过项目既有`>=120°`正式覆盖门和留一点稳定性门。不得把拟合后外推的圆上点当成
新的人工弧证据，也不得用它“补到120°”。可用
`tools/compare_clean_groove_pixel_truth.py`按图像SHA把HUMAN点与冻结runtime JSONL对照，分别报告墙线、
端点、中点、槽宽和“共用runtime圆心”的条件方向残差；后者只隔离槽口定位贡献，不能称为最终姿态角精度。

`tools/evaluate_clean_groove_pose_truth.py`是默认关闭的Git外离线评估器：复用项目已有Kasa初值与
robust/geometric拟圆，对点数、弧覆盖、径向残差和留一点圆心/半径漂移逐项硬门。只有全部过门才输出
人工当前角、AUTO候选角环形误差和85°最短调整量；否则`finalPose=null`。145实跑因覆盖和稳定性不足为
`NOT_EVALUATED`，它的拟圆/临时角只在`diagnosticOnly`中，不是最终真值或精度PASS。

`detector.sidewall_source_consistency_candidate`是默认不存在/关闭的development-only诊断。它不放宽现有
`0.12`对比不对称门；只在原结果恰好仅失败contrast、其他原检查通过且更严格端点结构证据通过时标记
`CANDIDATE_SUPPORTED`。无论结果如何，原`GROOVE_SOURCE_INCONSISTENT`、`valid=false`、空角度和空PLC
都不改变。当前证据仅有part-008一个人工正样品和part-019一个已知混合负样品，禁止默认启用或宣称泛化。

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

### 027真实槽与邻近固定装置阴影来源诊断

`detector.groove_shadow_source_discrimination`严格默认关闭且不拥有任何新数值门限。显式启用时，它只汇总
既有粗识别、v2物理双壁/外圆肩部端点、原始sidewall source-consistency及ambiguity resolver证据。
只有唯一物理存活候选且所有竞争候选都有明确失败证据时，才记录
`REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`；混合壁/端点、多个存活者、未评估证据、低polar或上游失败
均保持fail-closed。低`polar_score`不能被局部完整槽证据覆盖。

Mac回放700张已成为`observed-diagnostic-not-unseen-acceptance`，只允许逐图根因诊断，不能循环调全局门限或
宣称准确率。逐图SHA账本由`tools/trace_groove_shadow_sources.py`生成；候选来源叠加由
`tools/render_slot_pose_review.py`生成，原图缺失时明确记录`unavailable`。生产默认启用、准确率结论和任何
PLC授权必须等待物理零件与700组无交集的新manifest一次性冻结验收。

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

LabelMe 标注、参考图、待测原图和压缩包均为外置资产，不提交 Git。

## 安装与测试

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

## 槽姿态生产阻塞

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

## 009多组静态重复性与过渡盲测

009不改圆、真槽、槽壁或85°引导算法，只修复评估数据流：

- canonical inventory统一相对一个显式A2数据根；只处理清单列出的图，normal根不会递归重复扫入`坏/`。
- inventory draft允许sample/condition/repeat为空，但绝不能直接冒充confirmed grouping。正式分组CSV必须逐图同SHA覆盖，
  带物理sample、固定condition、连续repeat和非算法authority/provenance。
- 采集负责人可只确认精简的`confirmed-segments.csv`；`tools/materialize_a2_grouping.py`会在不读取算法结果的前提下
  校验无重叠、完整覆盖，再展开成逐图confirmed grouping。
- 每个静态condition必须同一零件、同一次摆放/装夹、同角度/工况且至少20帧。报告逐组环形角极差、样本标准差、
  P95绝对残差、检测有效率、圆心/半径/槽口中点波动和耗时P50/P95/max，再池化组内中心化残差做总体汇总。
- normal 481–498与499–500为同一sample的两个不同condition，分别18帧和2帧，数据保留但不进入正式静态汇总。
- bad组缺少badReason/poseUsable权威语义时只保留诊断，不能进入权威静态汇总。
- 过渡盲测按完整sample的源图SHA集合确定性选择，绝不读取算法结果。当前700张已被查看，因此锁固定标为
  `NON_STRICT_TRANSITIONAL`；工具同时导出排除该sample的development Manifest，并用一次性包装器阻止重复执行。

Mac完整命令、输出路径和判读见`specs/009-a2-static-repeatability-governance/quickstart.md`。常用入口：

```bash
uv run python tools/materialize_a2_grouping.py --help
uv run python tools/prepare_a2_evaluation.py --help
uv run python tools/freeze_transition_blind.py --help
uv run python tools/evaluate_static_repeatability.py --help
uv run python tools/run_transitional_blind_once.py --help
```

需要顺/逆时针调整仍是检测成功；只有几何不可用才是`DETECTION_FAILED`。本工具不产生PLC命令，也不把重复性
数值自动判为生产PASS/FAIL。

## 019跨零件圆与真槽鲁棒性

019针对历史七个失败物理零件建立了分层诊断和默认关闭的实验恢复，不把700张历史输出当真值：

- 外圆继续复用锁定gyj射线取点与`robust_fit_circle`；新增扇区残差证据，只允许局部、连续、数量受限的
  污染扇区执行一次原拟圆器重拟合，分布式污染/覆盖不足/拟合漂移继续失败。
- 暗区继续使用同一极坐标环带；MAD阈值不可用时可实验性增加有限分位数假设，跨阈值环形去重后仍先经过
  真槽几何过滤，且必须恰好一个槽才可计算姿态。
- part-006由009封存sample和SHA在读取结果/图片前双重隔离。七组按完整零件生成三折；所有700张均已暴露，
  所以只称开发/验证防过拟合证据，不称严格test或百分比准确率。

默认配置没有启用上述恢复。独立外圆可见弧、真槽开放边界/侧壁/槽口端点和遮挡区域人工复核完成前，
生产激活仍为BLOCKED。规格、Mac分折命令和判读见
`specs/019-a2-cross-part-circle-groove-robustness/quickstart.md`。

## A端面单图 CLI

标注中的 `imagePath` 必须能相对标注文件解析到外置参考图：

```bash
uv run python algorithms/end_face/main.py \
  --annotation /path/to/sample_1_label.json \
  --image /path/to/target.bmp \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --output /tmp/a-end-face-result.json \
  --task-id inspection-001 \
  --strict
```

`--output -` 可将 JSON 输出到标准输出。默认 `--pixel-size 1` 保留像素单位；只有传入经确认的
物理单位/像素比例时，核心才会增加物理量字段。JSON 中的非有限检测值统一写为 `null`，不会输出
非标准 `NaN` 或 `Infinity`。

当前契约为 `a-end-face-result/3`，三个旧状态不得混用：

- `technicalStatus`：检测程序是否执行完成；
- `result.localization.valid`（同 `result.valid`）：端面中心、尺度、旋转和定位方法是否通过策略；
- `result.measurementCompleteness.allValid`：所有带核心质量状态的特征是否均有效。

每个 `featureQuality.<特征>.coreValid` 都直接来自不变核心，不会被适配层强行改有效。默认策略不把
19、30、46、M78、80、86 等特征测量失败当成端面定位失败；如现场确认某特征属于定位必要项，必须
在新版本策略的 `requiredFeatureLabels` 中显式加入。

v3 追加 `result.shortLineCandidates`：只为 19/30 保存核心基线、独立 `candidateValid`、候选几何、
ROI/对比度/梯度/峰值/搜索边界诊断、失败检查和 `recovered/regressed` 对照状态。候选采用二维参考
梯度联合配准，重新估计局部位置和方向；它不覆盖 `featureQuality`、`measurements`、定位状态或旧
`measurementCompleteness`。

## LabelMe 标注语义

现有 A 端面 `sample_1_label.json` 的标注与核心解释已经核对：

| 稳定尺寸名 | 原始 LabelMe 标注 | 图形 | 核心解释 |
| --- | --- | --- | --- |
| 100 | 损坏直径字形 + `100` | `linestrip`，30 点 | 最大圆，外圆定位锚及半径/直径 |
| 71 | 损坏直径字形 + `71` | `linestrip`，26 点 | 最小圆，内孔定位及半径/直径 |
| 86 / 80 / M78 | 圆弧点集 | `linestrip`，85/88/85 点 | 中间环半径/直径 |
| 46 | 两端点 | `line` | 从中心到外缘的径向长度及角度 |
| 20 | 两端点 | `line` | 线段长度及角度 |
| 19 / 30 | 两端点 | `line` | 短线位置、方向和长度；旧标注长度约 44.80/26.20 px |
| 字符区域 | 四点区域 | `polygon` | 区域包围框和面积；不是定位必要项 |

LabelMe 中 19/30 必须各使用一个两点 `line`，点落在真实边缘并保持既有起止方向。原文件中的损坏
单位/直径字形不作为稳定身份，适配层统一映射为 `19`、`30`、`100` 等 canonical feature。

Mac A2 可从一个物理样品、一个位置的完整 20 张中选一张代表图，手工建立域内 19/30 参考。先检查
标注；输出 catalog 只有坐标、尺寸和 SHA，不包含嵌入的 `imageData`：

```bash
uv run python tools/inspect_short_line_labelme.py \
  --annotation "/external/A2/development/sample_001/CORRECTED-a2-short-lines.json" \
  --output "/external/A2/outputs/corrected-a2-short-lines-catalog.json"
```

当前先前提供的 A2 端点标注已因未吸附到真实阶梯强边而撤销，并由共享加载器按文件 SHA-256
拒绝。它不得用于模板、调参、真值或验收；真实 19/30 比较等待新的人工复核 LabelMe。重命名或
移动撤销文件不会绕过门禁。

传入 `--short-line-labelme-reference` 后，候选局部模板来自该外置 A2 标注图；桌面核心仍使用原参考，
其 SHA、旧量测和 `coreValid` 均不改变。`main-housing-registration-v2` 还会先枚举圆形实例、独立选择
主壳体、稳健拟合圆心/尺度并用环形外观估计角度，再投影真实 19/30 标注做局部搜索。旧 core 端点
只保留在对照诊断中，不参与 v2 搜索中心。候选输出 provenance 会记录 `external_labelme` 以及标注/
图片 SHA-256。v2 缺少外置 19/30 标注时严格拒绝；v1 仍可显式选择以保持兼容。

接口契约见 `contracts/a-end-face-result.schema.json`，质量分层与批量评估的 Spec Kit 规格见
`specs/004-quality-policy-batch/`；主壳体配准增量规格见 `specs/007-main-housing-registration/`。

## 批量质量评估

批量工具先完整校验外置 Manifest，再复用同一参考模型逐图检测：

```bash
uv run python tools/evaluate_end_face_batch.py detect \
  --manifest /external/a2-manifest.json \
  --data-root /external/A2 \
  --annotation /external/sample_1_label.json \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --short-line-labelme-reference /external/A2/development/sample_001/CORRECTED-a2-short-lines.json \
  --output-dir outputs/a2-evaluation
```

输出 `results.jsonl` 和 `quality-summary.json`。也可用 `summarize` 子命令只传逐图结果流，在无图片的
服务器上重算技术成功率、定位率、测量完整率、耗时和逐特征来源/原因分布。

## Mac 外置 A2 注册诊断与候选比较

在更正的 19/30 真值到位前，只运行无标注主壳体注册诊断：

```bash
uv run python tools/diagnose_main_housing_registration.py batch \
  --reference-image "$HOME/Desktop/壳体项目/137/a2-labelme-development-20/representative.bmp" \
  --manifest "$HOME/Desktop/壳体项目/137/a2-development-20-manifest.json" \
  --data-root "$HOME/Desktop/壳体项目/137/A2" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-registration-v2-development-20"
```

逐帧输出只含主壳体假设、圆心/尺度/角度和门限诊断，不含候选恢复语义。批量
`registration-summary.json` 使用 `a-end-face-main-housing-registration-summary/2`：对所有注册有效帧
汇总圆心/半径（像素及按每帧尺寸归一化）、尺度、旋转置信度/裕量、实例选择裕量、边缘覆盖与圆拟合
残差；线性量提供 count/min/max/mean/median/p05/p95/MAD，角度使用跨 ±180° 连续的环形统计。统计
只用于观察漂移，不参与有效判定。以下候选比较命令仅在 `CORRECTED-a2-short-lines.json` 经人工强边
核对及严格 inspect 后才可运行。

既有 v2 `results.jsonl` 可直接作为不可改写基线；工具会先完整验证 Manifest 图片属性/SHA-256 和
`imageId/taskId` 一一对应，再读取图片运行候选：

```bash
uv run python tools/compare_short_line_candidates.py compare \
  --manifest "$HOME/Desktop/壳体项目/137/a2-development-20-manifest.json" \
  --data-root "$HOME/Desktop/壳体项目/137/A2" \
  --annotation "/path/to/sample_1_label.json" \
  --results-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-v2-development-20/results.jsonl" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --short-line-labelme-reference "$HOME/Desktop/壳体项目/137/A2/development/sample_001/CORRECTED-a2-short-lines.json" \
  --development-group \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-main-housing-v2-development-20"
```

输出 `short-line-comparison.jsonl` 和 `short-line-summary.json`。无图重统计：

```bash
uv run python tools/compare_short_line_candidates.py summarize \
  --comparison-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-labelme-development-20/short-line-comparison.jsonl" \
  --output "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-labelme-development-20/short-line-summary-recomputed.json"
```

开发时同一样品/位置的 20 张必须全部留在 development Manifest；冻结标注 SHA 和配置 SHA 后，使用
不含该物理样品的全样品 Manifest 做 validation/acceptance。不得把同一组 20 帧随机拆到两个集合。
单张外置代表图只可用于注册诊断，不能据此宣称短线恢复或 25 张改善。25 张候选验收必须等更正
标注到位，再用冻结后的 v2 配置、同一标注/图片 SHA 在 Mac 外置数据上完整运行。撤销与注册诊断
撤销门禁见 `specs/008-revoke-invalid-anchor/`，注册稳定性统计见
`specs/009-registration-stability/`。

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项特征无效时保持该项 `coreValid=false`，但不默认否决定位。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。

## 槽姿态180°双拍初版（实验）

Spec 023新增两种输入：单图用于当前外圆/完整槽诊断并计算85°±5°调整量；双图一次输入
同一零件旋转180°前后的两拍，用第一拍互证遮挡、以第二拍当前位置输出唯一调整量。
半圈在几何上方向无关，硬件是否完成180°属于外部设备责任；软件只报告图像证据是否一致，
不会擅自归因硬件。

配置默认`enabled=false`，所有结果`developmentOnly=true`、`authoritative=false`、
`posePromotionAllowed=false`且PLC为空。当前没有真实同件180°图片，只完成合成契约初版；
不得把旋转单张图片当现场pair。命令见
[023 quickstart](specs/023-half-turn-paired-guidance/quickstart.md)。

## 孔2数据无关工具链与现拍检测

项目研发原则见 [Constitution](.specify/memory/constitution.md)。本轮数据无关基础的规格、方案和
任务记录位于 [001-data-independent-foundation](specs/001-data-independent-foundation/spec.md)。

## 数据无关工具链

安装固定依赖并运行测试：

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

为外置图片生成Manifest：

```bash
uv run python tools/make_manifest.py \
  --input /path/to/hole2-data \
  --output data/manifests/hole2-batch-001.json \
  --dataset-id hole2-batch-001 \
  --task hole_2 \
  --expected-repeats 20 \
  --reference-image /path/to/hole2-data/sample_1/pos_1/image_001.bmp
```

在服务器或Mac验证同一批原图：

```bash
uv run python tools/validate_dataset.py \
  --manifest data/manifests/hole2-batch-001.json \
  --data-root /path/to/hole2-data \
  --config config/hole2_inspection.example.json \
  --report outputs/hole2-batch-001/validation.json
```

从算法测量CSV计算静态/动态重复性：

```bash
uv run python tools/evaluate_repeatability.py \
  --measurements outputs/hole2-batch-001/measurements.csv \
  --config config/hole2_inspection.example.json \
  --output-dir outputs/hole2-batch-001/repeatability
```

使用现有权威参考资产进行一图冒烟：

```bash
bash scripts/smoke_reference.sh
```

数据目录详见 [data/README.md](data/README.md)，算法适配及资产指纹见
[algorithms/hole_2/README.md](algorithms/hole_2/README.md)。

## 现拍样品姿态注册与孔2尺寸检测

当前运行时只使用负责人确认的人工参考 JSON 及其配对 BMP。注册直接从该 BMP 的分布式图像
证据估计到目标图的固定工位小角度、尺度和平移；人工 JSON 定义 `Φ12.2` 可见弧和尺寸 `7`
两条物理边界的测量语义。退役模板不再作为底图、特征库、坐标系或任何运行时输入。

检测入口不接受现拍 LabelMe；负责人确认 JSON 只能在结果冻结后由独立验收入口读取。完整
服务器/Mac 命令、最新唯一真值哈希和证据限制见
[011 quickstart](specs/011-latest-truth-refactor/quickstart.md)。

负责人确认单图的当前结果（只代表像素几何，不代表重复性、毫米精度或生产 OK/NG）：

- 注册方向 `270°`，6 个空间支持，覆盖率 `1.0`，注册有效。
- `7`：预测 `309.2847 px`，最新真值 `310.0020 px`；长度误差 `0.7173 px`，端点最大误差 `1.5919 px`。
- `Φ12.2`：预测直径 `541.0248 px`，最新真值拟合直径 `541.1301 px`；直径误差 `0.1053 px`，圆心误差 `2.0650 px`。
- 检测未读取目标标注；叠加图、剖面、算法结果和验收报告全部留在仓库外。

检测结果现在显式输出目标↔参考正/逆变换与技术质量状态；注册或任一
特征失败时 CLI 返回非零且不保留伪造几何。验收报告会汇总方向、候选分数/拒绝
原因、变换、特征质量与真实误差。Mac `2000` 正常品 + `200` 坏品的外置分组
批量命令见 [011 quickstart](specs/011-latest-truth-refactor/quickstart.md)。

`Φ12.2` 使用受控两阶段半径搜索：主下限保持 `0.88`，只有主候选在
下界饱和时才以 `0.84` 下限恢复一次，并在质量字段中显式记录。尺寸7
的新切线双边界失败时，只允许回退到已通过原 v6 双边界质量状态的有限结果。

尺寸7的黑色轮廓带被建模为相反极性边缘对，并输出可审核的A/B边界与独立垂距线；Phi从
权威人工参考的可见弧确定灰度相位，在目标图强制同一径向极性后稳健拟圆。审核预览用绿色
局部弧表示真实边缘证据，并用蓝色实线整圆表示数学拟合模型；实线只是审核样式，不表示整圈均被检测。
检测器没有写入固定像素补偿、标称尺寸或目标真值坐标。

### 可变点数圆验收与 LabelMe 补圆

`Φ12.2` 验收不再要求固定77点。合法输入是 `shape_type=linestrip`、至少8个有限点，
并通过现有 `CIRCLE_RESIDUAL_PX`/`circular_residual` 圆拟合质量门；历史资产恰好77点
仅是数据事实。

仓库已有圆拟合能力，但此前没有“读取部分圆弧并写回完整 LabelMe 圆”的工具。现在可在
Git 外置目录运行：

```bash
uv run python tools/complete_labelme_circle.py \
  --annotation "$EXTERNAL_CIRCLE_DIR/partial-circle.json" \
  --image "$EXTERNAL_CIRCLE_DIR/source.bmp" \
  --config config/labelme_circle_completion.example.json \
  --completed "$EXTERNAL_CIRCLE_DIR/completed-circle.json" \
  --report "$EXTERNAL_CIRCLE_DIR/completion-report.json" \
  --preview "$EXTERNAL_CIRCLE_DIR/completion-preview.jpg"
```

工具复用 Kasa 初值、稳健筛点和几何圆拟合；要求可见弧覆盖至少 `120°`，按圆周长与源点
中位间距自动推导完整圆点数，并重复首点闭合。输出固定标记
`auto_completed=true`、`human_verified=false`，只能作为 LabelMe 人工复核底稿，不是人工真值。
