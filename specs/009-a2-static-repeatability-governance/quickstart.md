# Quickstart: A2 多组静态重复性与过渡盲测治理

## 1. Mac准备

```bash
git switch main
git pull --ff-only origin main
uv sync

export A2_PARENT_ROOT='__SET_A2_PARENT_DIRECTORY__'
export A2_WORK='__SET_EXTERNAL_OUTPUT_DIRECTORY__'
mkdir -p "$A2_WORK"
```

canonical inventory中的路径以`A2_PARENT_ROOT`为根，例如`A2/...bmp`和`A2/坏/...bmp`。图片、inventory、grouping、semantics与报告均留在`A2_WORK`或其他Git外目录。

## 2. 由人工确认段生成逐图分组

先复制 `config/a2-confirmed-segments.template.csv` 到Git外工作目录，由采集负责人确认
`dataset_class/start_capture_sequence/end_capture_sequence/sample_id/condition_id`。这张表只写采集事实，
不填算法角度、成功率或阈值。normal 481–498与499–500应使用同一`sample_id`、不同`condition_id`。

```bash
uv run python tools/materialize_a2_grouping.py \
  --inventory "$A2_WORK/inventory.csv" \
  --segments "$A2_WORK/confirmed-segments.csv" \
  --output "$A2_WORK/confirmed-grouping.csv"
```

工具要求分段无重叠且精确覆盖inventory每一图；结果角度不参与展开或分组。

## 3. 物化统一Manifest与资格表

```bash
uv run python tools/prepare_a2_evaluation.py \
  --data-root "$A2_PARENT_ROOT" \
  --inventory "$A2_WORK/inventory.csv" \
  --grouping "$A2_WORK/confirmed-grouping.csv" \
  --output-dir "$A2_WORK/prepared" \
  --verify-images
```

`dataset-semantics.csv`只在质量负责人已确认bad reason、pose usable、authority和provenance后通过
`--semantics "$A2_WORK/dataset-semantics.csv"`显式加入。未确认时应省略，bad组会保留但被排除出权威静态统计。

关键输出：

- `prepared/manifest.json`：统一根Manifest。
- `prepared/static-group-eligibility.json`与`.csv`：`ELIGIBLE`或排除原因。
- `prepared/preparation-report.json`：路径、哈希、分组与泄漏检查。

若只有空sample/condition的inventory draft，不要传`--grouping`冒充正式分组；先由采集负责人完成confirmed grouping。

## 4. 冻结过渡盲测

在开发/调参前执行一次：

```bash
uv run python tools/freeze_transition_blind.py \
  --manifest "$A2_WORK/prepared/manifest.json" \
  --eligibility "$A2_WORK/prepared/static-group-eligibility.json" \
  --output-dir "$A2_WORK/transitional-blind"
```

查看`transitional-blind/transitional-blind-lock.json`。它必须显示：

- `blindStatus=NON_STRICT_TRANSITIONAL`
- `priorExposure=true`
- 一个完整`selectedSampleId`
- `maxExecutionCount=1`

冻结目录还包含`development-manifest.json`。从冻结完成到发布候选之前，开发、调参和普通回归必须只使用该Manifest；
其中已完整排除锁定sample。

开发期间不要运行该Manifest或打开其逐图结果。

## 5. 非盲数据批量检测与静态报告

```bash
uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_WORK/transitional-blind/development-manifest.json" \
  --data-root "$A2_PARENT_ROOT" \
  --config "$A2_WORK/slot-pose-config.json" \
  --output "$A2_WORK/results.jsonl"

uv run python tools/evaluate_static_repeatability.py \
  --manifest "$A2_WORK/transitional-blind/development-manifest.json" \
  --results "$A2_WORK/results.jsonl" \
  --eligibility "$A2_WORK/prepared/static-group-eligibility.json" \
  --output-dir "$A2_WORK/static-repeatability"
```

查看：

- `static-repeatability/static-repeatability.json`：逐组和总体权威报告。
- `static-repeatability/static-groups.csv`：每组角度、有效率、几何和耗时。
- `summary.guidanceCoverage.status`：三类工况是否齐全。
- `groupEligibility[*].exclusionReasons`：18/2帧短组、bad语义未知等排除原因。

需要调整不等于检测失败：`CLOCKWISE`/`COUNTERCLOCKWISE`是有效检测的闭环指令；只有`DETECTION_FAILED`才是检测失败。

## 6. 发布候选时只运行一次过渡盲测

```bash
uv run python tools/run_transitional_blind_once.py \
  --manifest "$A2_WORK/transitional-blind/transitional-blind-manifest.json" \
  --lock "$A2_WORK/transitional-blind/transitional-blind-lock.json" \
  --data-root "$A2_PARENT_ROOT" \
  --config "$A2_WORK/slot-pose-config.json" \
  --output-dir "$A2_WORK/transitional-blind/execution"
```

工具在运行检测前先原子写入`transitional-blind/execution/execution-claim.json`。即使检测中途中断，
也不允许对同一锁重跑；需保留claim并把该次记为失败尝试。成功结果位于
`transitional-blind/execution/results-once.jsonl`，执行身份位于`transitional-blind/execution/execution-record.json`。该结果只能称为非严格过渡盲测；
正式泛化结论必须来自新增、物理样品隔离且此前未查看的数据。

## 7. 质量门

```bash
uv run --with jsonschema python -m unittest discover -s tests -v
git diff --check
```
