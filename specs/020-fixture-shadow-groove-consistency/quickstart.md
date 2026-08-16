# Quickstart: 020固定阴影与同源性验证

## 服务器聚焦测试

    uv run --with jsonschema python -m unittest \
      tests.test_fixture_shadow \
      tests.test_sidewall_consistency \
      tests.test_slot_pose_contract \
      tests.test_single_real_groove

## 全量测试

    uv run --with jsonschema python -m unittest discover -s tests

## 生成外置实验配置

020是在默认关闭的019实验配置上叠加诊断门。先从现场默认配置生成019配置，再生成020配置：

    uv run python tools/prepare_slot_pose_robustness_config.py \
      --base "$A2_WORK/config-local.json" \
      --output "$A2_WORK/fixture-shadow-020/experimental-config-019.json"

    uv run python tools/prepare_slot_pose_fixture_shadow_config.py \
      --base "$A2_WORK/fixture-shadow-020/experimental-config-019.json" \
      --output "$A2_WORK/fixture-shadow-020/experimental-config.json"

输出不得覆盖base；生成配置仍标记experimental，不用于生产。

## 历史证据与标注队列

    uv run python tools/audit_a2_fixture_shadow_evidence.py \
      --grouping "$A2_WORK/confirmed-grouping.csv" \
      --seal-lock "$A2_WORK/transitional-blind/transitional-blind-lock.json" \
      --results "$A2_WORK/history/results.jsonl" \
      --output-dir "$A2_WORK/fixture-shadow-020/audit"

该步骤只读历史结果，不读取图片，不评估准确率。

## Mac三折配对回放

每折先运行默认配置，再用完全相同manifest运行实验配置：

    uv run python tools/run_slot_pose_batch.py \
      --manifest "$A2_WORK/robustness/manifests/fold-01/validation-manifest.json" \
      --data-root "/path/to/A2-parent" \
      --config "$A2_WORK/config-local.json" \
      --output "$A2_WORK/fixture-shadow-020/fold-01-default.jsonl"

    uv run python tools/run_slot_pose_batch.py \
      --manifest "$A2_WORK/robustness/manifests/fold-01/validation-manifest.json" \
      --data-root "/path/to/A2-parent" \
      --config "$A2_WORK/fixture-shadow-020/experimental-config.json" \
      --output "$A2_WORK/fixture-shadow-020/fold-01-experimental.jsonl"

必须人工检查part-019至少2帧的两侧物理来源；part-015/021在标签完成前保持不可判定。不得读取或运行part-006。

## Mac获取功能分支

020只推送功能分支，不合入main：

    git fetch origin
    git switch --track origin/020-fixture-shadow-groove-consistency

原始BMP、人工LabelMe和回放结果继续写入Git外目录。对比时先核对默认配置与实验配置SHA；实验自动valid不等于
人工确认可信，必须逐图检查槽两侧壁是否来自同一真实开口。若出现真槽一侧与固定件阴影另一侧的混合配对，
该结果按false-positive处理并保持生产功能关闭。
