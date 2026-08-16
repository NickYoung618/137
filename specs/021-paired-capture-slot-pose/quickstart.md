# Quickstart: 021双帧配对槽姿态

## 服务器验证

    uv run --with jsonschema python -m unittest \
      tests.test_paired_capture_slot_pose \
      tests.test_slot_pose_prefill_review

    uv run --with jsonschema python -m unittest discover -s tests

## Mac获取功能分支

    git fetch origin
    git switch --track origin/021-paired-capture-slot-pose

## 双拍运行（现场参数确认前）

先用现有单帧批跑得到JSONL，再生成paired manifest。不改任何配置时，
仓库示例`enabled=false`只输出`EXPERIMENT_DISABLED`。如需联调候选匹配，在Git外建立实验副本：

    mkdir -p "$A2_WORK/paired"
    jq '.enabled = true' config/paired-capture-slot-pose.example.json \
      > "$A2_WORK/paired/paired-config.experimental.json"

保持manifest中`rotation.parameterStatus=UNCONFIRMED`时，即使实验开关开启也只输出非权威诊断，
`valid=false`且所有guidance/PLC字段为空：

    uv run python tools/run_paired_slot_pose.py \
      --manifest "$A2_WORK/paired/paired-manifest.json" \
      --single-results "$A2_WORK/paired/single-results.jsonl" \
      --config "$A2_WORK/paired/paired-config.experimental.json" \
      --output "$A2_WORK/paired/paired-results.jsonl"

现场确认旋转角、方向和容差后，再把manifest对应`rotation.parameterStatus`改为
`CONFIRMED`并填入实测参数。不要修改仓库示例默认值。

## part-019 374/369预标注审阅

已有019/020 JSONL后可按唯一文件名直接生成两图审阅包，不需要先手写manifest：

    uv run python tools/prepare_slot_pose_prefill_review.py \
      --data-root "$A2_ROOT" \
      --image-name Pic_2026_08_13_132433_374.bmp \
      --image-name Pic_2026_08_13_132433_369.bmp \
      --results-019 "$A2_WORK/robustness-019/results.jsonl" \
      --results-020 "$A2_WORK/fixture-shadow-020/results.jsonl" \
      --output-dir "$A2_WORK/manual-review-part-019-374-369"

输出目录包含`raw/`、`simplified/`、`labelme-auto/`、`contact-sheet.jpg`和
`review-index.json`。联系表按374/369各一行，只有RAW与SIMPLIFIED两列；`simplified/*.png`保持
原图分辨率，可单独放大。简化图只画019最终左右槽壁/端点与020观测暗区角度区间，不画外圆、圆定位框、
其他raw候选射线或实心fixture区域；标题列出019 valid和020 error code，并明确
“Observed dark angular interval / Fixture identity unconfirmed / Pixel boundary unknown”。
有完整区间时橙色开放括号及三刻线分别表示start/center/end；无区间才降级为方向箭头。

LabelMe打开`labelme-auto/*.json`；JSON只含最终侧壁、端点和`AUTO_observed_dark_angular_interval_*`，
全部使用`AUTO_`且`human_verified=false`。区间shape为linestrip并携带candidate_id、match_status、
failed_checks、fixture_identity_confirmed=false和boundary_semantics=angular_profile_interval。
人工只需确认/修正真实凹槽、fixture shadow A/B和左右壁是否同源。
Pic_2026_08_13_132354_292.bmp不加入manifest。

## 默认关闭的局部第二壁诊断

不要修改已有020配置。先在Git外复制并插入实验块；`$CONFIG_020`应是Mac此前实际使用的020完整配置：

    jq --slurpfile local config/local-second-wall-diagnostic.example.json \
      '.detector.local_second_wall_diagnostic = ($local[0] | .enabled = true)' \
      "$CONFIG_020" > "$A2_WORK/local-second-wall-021.experimental.json"

只复核374/369时，把两张原BMP的符号链接放入独立Git外目录，生成二图manifest后批跑；不要重跑sealed
part-006，也不要用本实验结果调020门限：

    mkdir -p "$A2_WORK/local-second-wall-021-input"
    ln -s "$A2_NORMAL_ROOT/Pic_2026_08_13_132433_374.bmp" \
      "$A2_WORK/local-second-wall-021-input/Pic_2026_08_13_132433_374.bmp"
    ln -s "$A2_NORMAL_ROOT/Pic_2026_08_13_132433_369.bmp" \
      "$A2_WORK/local-second-wall-021-input/Pic_2026_08_13_132433_369.bmp"
    uv run python tools/make_manifest.py \
      --input "$A2_WORK/local-second-wall-021-input" \
      --output "$A2_WORK/local-second-wall-021.manifest.json" \
      --dataset-id a2-part-019-374-369-local-wall --task slot_pose \
      --expected-repeats 2 --split development
    uv run python tools/run_slot_pose_batch.py \
      --manifest "$A2_WORK/local-second-wall-021.manifest.json" \
      --data-root "$A2_WORK/local-second-wall-021-input" \
      --config "$A2_WORK/local-second-wall-021.experimental.json" \
      --output "$A2_WORK/local-second-wall-021.results.jsonl"

判读`diagnostics.localSecondWallDiagnostic`：`UNIQUE_DIAGNOSTIC`只说明合成门下出现唯一实验候选，
不表示检测已修复；`CANDIDATE_MISSING`、`LOCAL_SECOND_WALL_NOT_FOUND`、`MULTIPLE_LOCAL_OPENINGS`和
`SOURCE_INCONSISTENT`由`errorCode/failureStage`区分。所有情况下顶层均应保持
`GROOVE_SOURCE_INCONSISTENT`、`valid=false`、无PLC命令。再用上面的审阅命令，把
`--results-020`替换成`$A2_WORK/local-second-wall-021.results.jsonl`重新生成简化材料。

140张非sealed三折回放使用019已冻结的三个validation manifest，不读取part-006；每折只运行一次同一实验配置：

    mkdir -p "$A2_WORK/local-second-wall-021/three-fold"
    for fold in 01 02 03; do
      uv run python tools/run_slot_pose_batch.py \
        --manifest "$A2_WORK/robustness/manifests/fold-${fold}/validation-manifest.json" \
        --data-root "$A2_ROOT_PARENT" \
        --config "$A2_WORK/local-second-wall-021.experimental.json" \
        --output "$A2_WORK/local-second-wall-021/three-fold/fold-${fold}.jsonl" || exit 1
    done

只汇总顶层valid、实验唯一候选和失败阶段，不把算法输出当真值或准确率：

    jq -s '
      def diag: (.diagnostics.localSecondWallDiagnostic // {});
      {
        images: length,
        topLevelValid: map(select(.result.valid == true)) | length,
        localDiagnosticStatus: (group_by(diag.status // "NOT_RUN") |
          map({key: (.[0] | diag.status // "NOT_RUN"), value: length}) | from_entries),
        localDiagnosticError: (group_by(diag.errorCode // "NONE") |
          map({key: (.[0] | diag.errorCode // "NONE"), value: length}) | from_entries)
      }' "$A2_WORK/local-second-wall-021/three-fold/"*.jsonl \
      > "$A2_WORK/local-second-wall-021/three-fold/summary.json"

`summary.json`报告的是实验候选形成率与fail-closed分布；在多图人工真值完成前不得称precision、accuracy或
“识别率提升”。part-019已知混合边负例必须保持顶层无效；如实验候选形成，只能用简化审阅材料人工裁决。

## 判读

- `status=DETECTED`：双拍几何有效且图像引导可用；PLC仍阻断。
- `status=DIAGNOSTIC_ONLY`：参数未确认，任何角度假设都不权威。
- `valid=false`：不得输出0度或沿用旧角，查看`error.code`和`hypotheses[].failedChecks`。
