# Quickstart: 全局物理外圆边族选择验证

## 1. Prerequisites

- 当前分支：`026-global-circle-edge-family`。
- 161 JSON SHA必须为`5707b530594fc71ecd75616ebde3ab07c51a11938b986e69c492a0a9c8b01e9f`。
- 使用安全九图manifest生成开发、正对照与held-out清单；先执行物理组交集和禁用分组污染门。
- 所有BMP、LabelMe、manifest和JSONL结果写在`/home/ubuntu/disk/dzk/slot-pose-private-data/multi-edge-circle-026-validation/`，不得进入Git。

## 2. TDD and contract gates

```bash
uv run --with jsonschema python -m unittest \
  tests.test_physical_outer_circle \
  tests.test_full_frame_circle_locator \
  tests.test_legacy_adapter \
  tests.test_slot_pose_contract \
  tests.test_circle_edge_family_trace \
  tests.test_manual_circle_edge_family_analysis \
  tests.test_single_shot_initial_profile
```

```bash
uv run --with jsonschema python -m unittest discover -s tests -p 'test_*.py'
```

```bash
uv run --with jsonschema python - <<'PY'
import json
from pathlib import Path
import jsonschema
for path in sorted(Path('contracts').glob('*.schema.json')):
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))
print('root schemas valid')
PY
```

## 3. Offline 161 evidence

运行人工圆/多峰投影CLI，将报告写到Git外。预期人工圆约为中心`(2811.590,1839.705)`、半径`1649.858px`、弧覆盖`270.118°`、P95`3.538px`，leave-one-out最大中心漂移不高于`0.14px`。运行时不得接收该JSON参数。

## 4. Frozen groups

- 开发：141(part-008)、161(part-009)、441(part-023)。
- 正对照：145(part-008)，不计独立验证。
- held-out：281(part-015)、401(part-021)。

先只运行开发与145；冻结候选配置和代码后再运行held-out。281应继续在槽识别失败，401应继续在槽精修失败，二者所有姿态/PLC字段均为null。

## 5. Required comparisons

- 每张图的合格边族数必须为1才可进入最终拟圆。
- 比较物理圆中心/半径、点数、inlier ratio、角覆盖、P95、原门限与margin。
- 161相对人工圆中心差和半径差均不大于5px；人工弧到运行时圆P95不超过“该图原物理圆门+人工弧自身P95”的离线合成上界。该上界只处理两套独立残差的比较，不得写入运行时或放宽原门。
- 145人工圆误差不得相对025基线回退。
- 0/多族、裁切、反光、多同心圆、31°/328°与候选重排合成测试必须fail-closed或旋转等变。

## 6. Performance and contamination

使用同机、同清单、复用同一适配器的基线/候选成对基准；报告P50/P95/max。候选图像只解码一次，每射线只采样一次，单图总P95不得超过2.5秒。

```bash
git diff --check
git status --short
git diff --name-only --diff-filter=ACMR | rg '\.(bmp|jpg|jpeg|png|jsonl|tar|gz)$' && exit 1 || true
rg -n 'HUMAN_outer_circle_visible_arc|132228_141|132251_161|132510_441' algorithms config && exit 1 || true
```

只有聚焦、全量、全部根Schema、CLI、静态重复性、性能、跨零件和污染门全部通过后才可提交并推送本功能分支；不得合并main。
