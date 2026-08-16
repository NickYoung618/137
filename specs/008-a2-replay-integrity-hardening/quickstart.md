# Quickstart: A2 回放验收与根因加固

以下命令只使用占位路径，媒体和现场路径不得写入Git。

## 1. 运行聚焦测试

```bash
uv run --with jsonschema python -m unittest \
  tests.test_slot_pose_review \
  tests.test_data_tools \
  tests.test_slot_pose_contract \
  tests.test_slot_pose_evaluation \
  tests.test_groove_resolution \
  tests.test_a2_replay_audit -v
```

## 2. 生成带显式语义的Manifest

```bash
uv run python tools/make_manifest.py \
  --input /external/data \
  --output /external/results/manifest.json \
  --dataset-id a2-review-v1 \
  --task slot_pose \
  --semantics /external/contracts/dataset-semantics.csv

uv run python tools/validate_dataset.py \
  --manifest /external/results/manifest.json \
  --data-root /external/data
```

## 3. 展开并核对有效配置

```bash
uv run python tools/materialize_slot_pose_config.py \
  --config /external/config/source.json \
  --output /external/config/effective.json
```

省略默认与显式默认的等价配置必须得到相同effective SHA。

## 4. 对已有结果做无图像审计

```bash
uv run python tools/audit_slot_pose_replay.py \
  --manifest /external/results/manifest.json \
  --results /external/results/results.jsonl \
  --output /external/results/replay-audit.json
```

锁定700条期望：491 valid；489 needs adjustment；2 in position；209 unavailable。若无poseUsable标签，authoritative false-positive状态必须为BLOCKED。

## 5. 生成权威review

```bash
uv run python tools/render_slot_pose_review.py \
  --manifest /external/results/manifest.json \
  --results /external/results/results.jsonl \
  --data-root /external/data \
  --output /external/results/review
```

质量拒绝必须显示最终DETECTION_FAILED/NOT_AVAILABLE；联系表自动增加列数，700图不能超过JPEG高度限制。

## 6. 数据用途隔离

- `development`：合成样本与当前唯一人工标注参考，可反复开发测试。
- `validation`：新物理样品、人工复核、与development样品隔离；当前为`NOT_AVAILABLE`。
- `test`：另一个未参与开发/阈值选择的新样品集；当前为`NOT_AVAILABLE`。
- `acceptance`：已检查的700张锁定回归。实现期不反复跑原图，release candidate完成后才审计一次现成JSONL。

同一`sampleId`或`sourceImageSha256`不得跨用途。不能把25张同源JPEG、唯一人工样本或700张拆分后重新命名成独立验证/测试精度。

## 7. 全量质量门

```bash
uv run --with jsonschema python -m unittest discover -s tests -v
git diff --check
```

另行检查JSON可解析、无媒体/大文件、无现场绝对路径。PLC/上位机不在本功能范围。
