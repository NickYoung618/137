# Quickstart: 单拍初版候选

## 1. 物化Git外初版配置

```bash
uv run python tools/prepare_single_shot_initial_config.py \
  --base-config /path/to/nonsealed-single-real-groove-config.json \
  --output /path/outside/repository/single-shot-initial.json \
  --report /path/outside/repository/single-shot-initial-profile.json
```

## 2. 运行一张图

```bash
uv run python -m algorithms.slot_pose.main \
  --image /path/to/image.bmp \
  --config /path/outside/repository/single-shot-initial.json \
  --out /path/outside/repository/result.json \
  --strict
```

`--strict`在检测失败时返回非0；失败结果仍会写入JSON以便诊断。

## 3. 聚焦验证

```bash
uv run python -m unittest \
  tests.test_single_shot_initial_profile \
  tests.test_source_consistency_adjudication \
  tests.test_single_groove_pose -q
```

## 4. 判读

- 完整真槽：`valid=true`，读`currentAngleDeg`、`correctionDeg`和`rotationDirection`。
- 被挡/混边/歧义/圆失败：`valid=false`，角度必须为null，读`error.code`和`error.stage`。
- 无论成功失败，PLC命令都必须为null。
