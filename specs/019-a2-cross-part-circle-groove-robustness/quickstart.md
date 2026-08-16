# Quickstart: A2 跨零件圆与真槽鲁棒性

## 1. 聚焦测试

    uv sync --frozen
    uv run python -m unittest tests.test_angular_profile tests.test_physical_outer_circle
    uv run python -m unittest tests.test_full_frame_circle_locator tests.test_single_real_groove
    uv run python -m unittest tests.test_slot_pose_contract tests.test_a2_robustness_governance

预期：默认模式历史用例不变；实验模式的污染圆、负暗阈值、0/多槽和泄漏用例通过。

## 2. 分组验证计划（不读图、不读results）

    uv run python tools/plan_a2_robustness_folds.py \
      --grouping "$A2_WORK/confirmed-grouping.csv" \
      --root-causes "$A2_WORK/robustness-root-causes.csv" \
      --seal-lock "$A2_WORK/transitional-blind/transitional-blind-lock.json" \
      --fold-count 3 \
      --output "$A2_WORK/robustness/fold-plan.json" \
      --source-manifest "$A2_WORK/manifest.json" \
      --manifest-dir "$A2_WORK/robustness/manifests"

确认part-006不在任何fold，同sample不跨两侧，单sample家族显示INSUFFICIENT_PARTS。

## 3. 历史七组只读审计

    uv run python tools/audit_a2_robustness_groups.py \
      --grouping "$A2_WORK/confirmed-grouping.csv" \
      --root-causes "$A2_WORK/robustness-root-causes.csv" \
      --seal-lock "$A2_WORK/transitional-blind/transitional-blind-lock.json" \
      --fold-plan "$A2_WORK/robustness/fold-plan.json" \
      --results "$A2_WORK/history/results.jsonl" \
      --output-dir "$A2_WORK/robustness/audit"

查看audit.json、groups.csv和annotation-queue.csv。sealedRecordsParsed必须为0，
accuracyEvaluated必须为false。

## 4. Mac小组原图开发回放

只在外置配置副本启用实验开关，不覆盖生产配置。开发期仅运行fold中的development samples；
配置固定前不查看validation逐图overlay。part-006不得出现在任何命令中。

    uv run python tools/prepare_slot_pose_robustness_config.py \
      --base "$A2_WORK/config-local.json" \
      --output "$A2_WORK/robustness/experimental-config.json"

    uv run python tools/run_slot_pose_batch.py \
      --manifest "$A2_WORK/robustness/manifests/fold-01/development-manifest.json" \
      --data-root "/path/to/A2" \
      --config "$A2_WORK/robustness/experimental-config.json" \
      --output "$A2_WORK/robustness/development-results.jsonl"

## 5. 全量工程门

    uv run python -m unittest discover -s tests
    git diff --check
    git status --short

另执行Schema、大文件、媒体、绝对A2路径和Git外证据污染检查。新人工真值完成前，不得以实验配置替换
默认生产配置。
