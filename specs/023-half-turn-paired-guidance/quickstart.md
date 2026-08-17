# Quickstart

初版先从已有单帧结果JSONL生成引导，不重新实现图片检测。

```bash
uv run python tools/run_half_turn_guidance.py --help
uv run python -m unittest tests.test_half_turn_guidance tests.test_paired_capture_slot_pose
```

单图请求与双图请求均写入Git外JSON manifest，路径使用数据根相对路径并以SHA关联单帧JSONL。示例配置默认`enabled=false`；开发验证需在Git外复制后显式开启。当前没有真实同件180°照片，真实pair验收必须等待现场数据，不能用旋转单张图片替代。

```bash
uv run python tools/run_half_turn_guidance.py \
  --manifest "$SLOT_POSE_WORK/guidance-request.json" \
  --single-results "$SLOT_POSE_WORK/single-results.jsonl" \
  --config "$SLOT_POSE_WORK/half-turn-guidance.experimental.json" \
  --output "$SLOT_POSE_WORK/guidance-results.jsonl"
```

`SINGLE_CAPTURE`请求包含一个`captureIndex=1`且`halfTurn=null`；`HALF_TURN_PAIR`请求包含同一`sampleId`下的1/2两拍，并固定：

```json
{
  "nominalRotationDeg": 180.0,
  "directionRequired": false,
  "executionResponsibility": "EXTERNAL_HARDWARE",
  "conventionId": "image-x-right-y-down-clockwise/1"
}
```
