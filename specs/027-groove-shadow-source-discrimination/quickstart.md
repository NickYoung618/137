# Quickstart: 027开发与验收

## 1. 固定开发起点

```bash
git switch 027-groove-shadow-source-discrimination
git rev-parse HEAD
git status --short --branch
```

预期基线祖先为`d776c4d2f25b985fb4e50d4978cc3868cc59c6f7`。不得merge `main`，不得访问sealed part-006。

## 2. 核验A2整合包

```bash
sha256sum '/home/ubuntu/disk/dzk/slot-pose-private-data/mac-d776c4d-a2-human-review-20260818/A2真实回放-d776c4d-20260818-complete-evidence-20260818.tar.gz'
```

预期：`636fe9d786050e94e1f6d24515886c8434c2eca80268cff6d45c52c8085d1ae4`。

## 3. 生成已观察组逐图账本

实现后使用只读输入与Git外输出目录：

```bash
uv run python tools/trace_groove_shadow_sources.py \
  --evidence-dir /home/ubuntu/disk/dzk/slot-pose-private-data/mac-d776c4d-a2-human-review-20260818 \
  --results-dir /home/ubuntu/disk/dzk/slot-pose-private-data/mac-d776c4d-a2-full-technical-20260818 \
  --output-dir /home/ubuntu/disk/dzk/slot-pose-private-data/027-observed-diagnostic-trace-20260818-145000
```

报告必须有207条唯一SHA记录；人工语义未提供的行必须是`null/not_labeled`，ambiguous中未运行的精修必须是`not_evaluated`。

## 4. 运行测试

```bash
uv run python -m unittest \
  tests.test_groove_shadow_discrimination \
  tests.test_groove_resolution \
  tests.test_slot_pose_contract \
  tests.test_single_real_groove \
  tests.test_trace_groove_shadow_sources -v

uv run python -m unittest discover -s tests -v
git diff --check
git status --short --branch
```

## 5. 独立新物理零件验收

开始前必须收到并冻结：原图、物理part ID、逐图人工三态标签和manifest SHA。先验证与已观察700张物理part集合无交集，并验证不含sealed part-006；随后冻结代码与配置，只运行一次验收。

报告分开给出：完整近阴影安全放行/继续拒绝、混合或遮挡拒绝、其他阶段失败、失败空输出、重复性、性能和所有SHA。

冻结后使用以下元数据预检与聚合接口；`observed-physical-ids.txt`必须来自数据持有者确认的700组物理分组，
不能由文件序号猜测：

```bash
uv run python tools/trace_groove_shadow_sources.py \
  --acceptance-manifest "$NEW_PART_MANIFEST" \
  --acceptance-results "$NEW_PART_RESULTS" \
  --observed-physical-ids "$OBSERVED_PHYSICAL_IDS" \
  --expected-code-commit "$FROZEN_COMMIT" \
  --expected-config-sha256 "$FROZEN_CONFIG_SHA" \
  --output-dir "$NEW_PART_ACCEPTANCE_REPORT_DIR"
```

新原图到达后，代表性来源叠加使用既有review renderer；若仅预审结果而尚无原图，可加
`--allow-missing-images`，产物会记录`sourceOverlayStatus=unavailable`而不伪造图片。

若新物理组尚未到达，最终状态必须写`INDEPENDENT_ACCEPTANCE_BLOCKED`；不得给出准确率提升结论，不得启用生产默认，不得授权PLC。
