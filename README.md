# 137壳体 A端面槽姿态引导算法

本仓库已完成Spec Kit功能`002-slot-pose-estimation`的服务器MVP：复用历史A端面视觉核心，新增只读
适配、角度契约、质量门控、fail-closed、合成回归、Manifest和评估工具。它不是另写的一套圆/极坐标/
槽检测算法，也未修改孔2或`/home/ubuntu/disk/gyj`下任何文件。

## 复用代码与新写代码

只读复用资产：

- `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py`
- SHA-256：`36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35`
- 复用函数：`robust_fit_circle`、`object_bbox_center`、`polar_resample`、`find_outer_notch_angle`、
  `estimate_rotation_by_notch`、`estimate_rotation_by_polar`、`estimate_global_transform`、
  `build_reference_model`、`load_detection_gray`。

本仓库新写部分：

- `algorithms/slot_pose/legacy_adapter.py`：哈希校验、只读动态加载、既有函数编排、质量门控和角度换算。
- `algorithms/slot_pose/contract.py`、`main.py`：v2结果契约、fail-closed和单图CLI。
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

现场图纸视频只证明竖向datum、左槽射线和`85°±5° (Z106)`的几何意图，不证明A2顶部两缺口的角色。
目标、datum、A2映射和输出用途未确认前，所有模式都只能作诊断；默认配置的
`target_semantics_confirmed=false`，因此绝不输出正式机械角。完整规格和Mac命令见
`specs/003-a2-paired-notch-stability/`。

## Mac A2后续验证

服务器现只有1张A2代表图及一份非datum/target的短线标注；完整正常/坏图集仍在Mac外置存储，不提交Git。
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

- B-001 现场/机械负责人：确认目标是单缺口、双缺口中的哪一个，还是两缺口夹持的凸台/槽中心线。
- B-002 数据负责人：根据采集记录确认A2条件组、物理样品、split及与历史参考图的工位/视角/方向映射。
- B-003 机械/机器人负责人：确认机械零位、正方向及图像到机械坐标映射。
- B-004 质量负责人：确认MAE/P95/max、静态极差、跨组残差、有效率、坏图误引导率和节拍门限。
- B-005 PLC/机器人工程师：确认字段、地址、缩放、握手、超时和失败动作。
- B-006 设计/机械方：确认竖向datum是上槽射线、上下槽轴还是其他基准。
- B-007 业务/质量方：确认85°±5°是尺寸OK/NG还是引导换算输入。
- B-008 现场负责人：确认A2暗区与图纸datum/target特征的逐项对应。

关闭顺序：B-006/B-007/B-008 → B-001/B-002 → B-003 → 冻结Mac验证集 → B-004验收 → B-005上线。全部关闭前，本MVP
只能用于离线诊断和验证，不能宣称生产可交付。
