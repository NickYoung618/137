# Quickstart

使用冻结manifest、对应022 JSONL、原始数据根和外置输出目录运行现有`render_slot_pose_review.py`。本规格首轮不运行全量检测、不修改配置。

代表子集必须用明确 `imageId` 选择，而不能按算法分数排名：

```bash
python tools/build_slot_pose_representative_subset.py \
  --manifest /external/fold-01/validation-manifest.json \
  --results /external/fold-01.jsonl \
  --manifest /external/fold-02/validation-manifest.json \
  --results /external/fold-02.jsonl \
  --manifest /external/fold-03/validation-manifest.json \
  --results /external/fold-03.jsonl \
  --image-id normal:part-008:fixed-pose:0005 \
  --image-id normal:part-008:fixed-pose:0007 \
  --image-id normal:part-008:fixed-pose:0001 \
  --image-id normal:part-009:fixed-pose:0001 \
  --image-id normal:part-023:fixed-pose:0001 \
  --image-id normal:part-015:fixed-pose:0001 \
  --image-id normal:part-014:fixed-pose:0001 \
  --image-id normal:part-021:fixed-pose:0001 \
  --image-id normal:part-019:fixed-pose:0014 \
  --dataset-id a2-single-shot-representatives-024 \
  --output-dir /external/slot-pose-024/subset
```

`selection-report.json` 保留原 fold/task/SHA 血缘，并明确
`algorithmResultsUsedForSelection=false`。所有 `/external/...` 均为运行时示例，不是生产数据路径。
