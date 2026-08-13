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

已确认合成`+30°`冒烟输出约`+29.984°`。默认`config/inspection.example.json`故意保持机械语义未确认，
对权威参考图返回`POSE_CONVENTION_UNCONFIRMED`、`valid=false`、正式角度`null`。

Manifest和评估命令见`specs/002-slot-pose-estimation/quickstart.md`。正式规格、方案、任务和历史数值
证据位于`specs/002-slot-pose-estimation/`。

## Mac A2后续验证

真实数据仍只在`/Users/daizekai/Desktop/壳体项目/A2.rar`，不上传服务器、不提交Git。同步本仓库到Mac后：

1. 将配置的`legacy_asset`路径改为Mac同源源码、标注和参考图，并核对内容SHA-256。
2. 在外置目录解压/流式读取A2，先生成Manifest，再补目标槽、机械真值、样品和split标注。
3. 按样品隔离开发/调参/验证/验收；固定角度至少20次采集做静态重复性，至少2个换位组做动态重复性。
4. 运行单图/批量结果与`tools/evaluate_slot_pose.py`，报告角度MAE/P95/max、成功/漏检/误检和节拍。

无需A2即可先在Mac验证历史源码适配链（标注和参考图由工具生成的小图提供）：

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir /tmp/slot-pose-synthetic --angles=0,30,90 --repeats 1 --seed 137 \
  --legacy-source '/Users/daizekai/Desktop/壳体项目/work/算法原始/A端面/repeatability_evaluation.py'
uv run python algorithms/slot_pose/main.py \
  --image /tmp/slot-pose-synthetic/synthetic/sample_synthetic/angle_pos_030p00/repeat_001.png \
  --config /tmp/slot-pose-synthetic/synthetic-config.json --task-id mac-smoke --strict
```

Mac没有服务器绝对路径时，权威服务器参考图用例会显示`skipped`；这与算法失败不同。完整A2验证需要
另建本机配置，不能直接修改并提交服务器默认模板。

## 生产阻塞（不能由算法默认值代替）

- B-001 现场/机械负责人：确认目标槽是否就是历史`find_outer_notch_angle`检测的外缘缺口。
- B-002 戴泽楷：确认A2与历史参考图是否同工位、同视角、同方向。
- B-003 机械/机器人负责人：确认机械零位、正方向及图像到机械坐标映射。
- B-004 质量负责人：确认角误差、重复性、成功率和节拍验收门限。
- B-005 PLC/机器人工程师：确认字段、地址、缩放、握手、超时和失败动作。

关闭顺序：B-001/B-002 → B-003 → 冻结Mac验证集 → B-004验收 → B-005上线。全部关闭前，本MVP
只能用于离线诊断和验证，不能宣称生产可交付。
