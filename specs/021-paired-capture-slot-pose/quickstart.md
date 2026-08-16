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

输出目录包含`raw/`、`overlay-019/`、`overlay-020/`、`labelme-auto/`、`contact-sheet.jpg`和`review-index.json`。LabelMe打开`labelme-auto/*.json`；AUTO_ shape不是人工真值。人工只需确认/修正真实凹槽、fixture shadow A/B和左右壁是否同源。Pic_2026_08_13_132354_292.bmp不加入manifest。

## 判读

- `status=DETECTED`：双拍几何有效且图像引导可用；PLC仍阻断。
- `status=DIAGNOSTIC_ONLY`：参数未确认，任何角度假设都不权威。
- `valid=false`：不得输出0度或沿用旧角，查看`error.code`和`hypotheses[].failedChecks`。
