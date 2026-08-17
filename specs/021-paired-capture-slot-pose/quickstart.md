# Quickstart: 021双帧配对槽姿态

## 服务器验证

    uv run --with jsonschema python -m unittest \
      tests.test_paired_capture_slot_pose \
      tests.test_slot_pose_prefill_review

    uv run --with jsonschema python -m unittest \
      tests.test_local_second_wall \
      tests.test_single_real_groove \
      tests.test_complete_groove_review_queue

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

### 374人工线的安全语义更名

当前人工文件中`HUMAN_true_groove_wall_missing`是误命名；它实际确认已有285.953°墙cluster是一条可见真实槽壁，不能作为相对侧壁真值。先在Mac计算原件SHA，再生成不覆盖原件的派生副本：

    HUMAN_SOURCE="$A2_WORK/manual-review-part-019-374-369/raw/review-01-Pic_2026_08_13_132433_374.json"
    HUMAN_DERIVED="${HUMAN_SOURCE%.json}.semantic-reviewed-v2.json"
    test -f "$HUMAN_SOURCE"
    test ! -e "$HUMAN_DERIVED"
    HUMAN_SOURCE_SHA="$(shasum -a 256 "$HUMAN_SOURCE" | awk '{print $1}')"
    jq --arg source_sha "$HUMAN_SOURCE_SHA" '
      .flags = ((.flags // {}) + {
        source_annotation_sha256: $source_sha,
        source_preserved: true,
        runtime_input_allowed: false
      })
      | .shapes |= map(
          if .label == "HUMAN_true_groove_wall_missing" then
            .label = "HUMAN_confirmed_visible_real_groove_wall"
            | .description = "Confirms one visible real-groove wall; not opposite-wall or complete-opening truth"
            | .flags = ((.flags // {}) + {
                human_verified: true,
                semantic_role: "visible_real_groove_wall",
                opposite_wall_truth: false,
                complete_opening_truth: false,
                opposite_wall_observability: "UNKNOWN_OR_POSSIBLY_OCCLUDED"
              })
          else . end
        )
    ' "$HUMAN_SOURCE" > "$HUMAN_DERIVED"
    shasum -a 256 "$HUMAN_SOURCE" "$HUMAN_DERIVED"

必须保留`HUMAN_SOURCE`不变。派生副本仍只用于人工审核，不能作为生产运行时输入；不要添加或猜测另一侧壁线。

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
不表示检测已修复；`CANDIDATE_MISSING`、`LOCAL_SECOND_WALL_NOT_FOUND`、`MULTIPLE_LOCAL_OPENINGS`、
`PARTIALLY_OBSERVED`和历史`SOURCE_INCONSISTENT`由`status/errorCode/failureStage`区分。所有情况下顶层均应保持
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

## 374/369逐seed根因trace（不需要原图）

拉取最新021后，可先直接读取8ff3889已经生成的三折JSONL，不重跑任何BMP。工具只按basename抽取算法字段，
输出不含绝对路径、图片像素或人工真值：

    uv run python tools/extract_local_second_wall_trace.py \
      --results "$A2_WORK/local-second-wall-021/three-fold/fold-01.jsonl" \
      --results "$A2_WORK/local-second-wall-021/three-fold/fold-02.jsonl" \
      --results "$A2_WORK/local-second-wall-021/three-fold/fold-03.jsonl" \
      --image-name Pic_2026_08_13_132433_374.bmp \
      --image-name Pic_2026_08_13_132433_369.bmp \
      --output "$A2_WORK/local-second-wall-021/part-019-374-369-trace-8ff3889.json"

旧结果可回答各seed的拟合角、线参数和失败检查；要获得diagnostic/2新增的anchor、拒绝阶段和merge cluster，
只需用同一SHA为`79960702...`的实验配置重跑374/369两张，不需要再跑140张。生成二图manifest的方法见上文
“默认关闭的局部第二壁诊断”，输出到：

    "$A2_WORK/local-second-wall-021/part-019-374-369-results-v2.jsonl"

然后再次导出：

    uv run python tools/extract_local_second_wall_trace.py \
      --results "$A2_WORK/local-second-wall-021/part-019-374-369-results-v2.jsonl" \
      --image-name Pic_2026_08_13_132433_374.bmp \
      --image-name Pic_2026_08_13_132433_369.bmp \
      --output "$A2_WORK/local-second-wall-021/part-019-374-369-trace-v2.json"

判读顺序：先看`localInterval`是否覆盖混合大暗区，再比较两个`anchorEvidence`；随后按极性查看
`searchOutcomeSummary`和`sideSearchCandidates[].rejectionStage`，最后核对
`sideSearchMergeClusters`及`hypothesisMergeClusters`成员守恒。不得因为输出接近0.12就放宽门限。

## 判读

- `status=DETECTED`：双拍几何有效且图像引导可用；PLC仍阻断。
- `status=DIAGNOSTIC_ONLY`：参数未确认，任何角度假设都不权威。
- `valid=false`：不得输出0度或沿用旧角，查看`error.code`和`hypotheses[].failedChecks`。

## diagnostic/3 双向/outward墙搜索

拉取含diagnostic/3的021分支后，仍使用Git外配置和三折manifest。新配置必须显式使用
`local-second-wall-diagnostic/2`且`enabled=true`；不得修改`sidewall_source_consistency`的0.12。
从实际使用的020完整配置重新生成，不复用旧config/1文件：

    jq --slurpfile local config/local-second-wall-diagnostic.example.json \
      '.detector.local_second_wall_diagnostic = ($local[0] | .enabled = true)' \
      "$CONFIG_020" > "$A2_WORK/local-second-wall-021.bidirectional.experimental.json"

只回放374/369时沿用上文二图manifest，将输出改为Git外新文件：

    uv run python tools/run_slot_pose_batch.py \
      --manifest "$A2_WORK/local-second-wall-021.manifest.json" \
      --data-root "$A2_WORK/local-second-wall-021-input" \
      --config "$A2_WORK/local-second-wall-021.bidirectional.experimental.json" \
      --output "$A2_WORK/local-second-wall-021.bidirectional.results.jsonl"

判读`diagnostics.localSecondWallDiagnostic`:

- `searchDomains[]`必须同时有start/end的`INWARD`与`OUTWARD`，跨0°时`wrapsBoundary=true`。
- `sideSearchCandidates[]`的每一项必须有domainId、seed、polarity及拟合或拒绝阶段。
- `sideSearchMergeClusters[]`是物理墙；`canonicalWallPairs[]`是无序墙对，不应再出现A锚B/B锚A两条顺序重复。
- 与原已拒绝start/end相同的混合对必须失败`reuses_rejected_initial_pair`。
- 新外侧cluster在人工确认像素壁前仍只是待审候选，不得把形成率称为准确率。

140张回放继续使用原三折validation manifest，不含sealed part-006。汇总必须分开：
part-019新outward cluster、旧混合对拒绝、part-008未裁决fail-closed、以及其他上游失败。

## PARTIALLY_OBSERVED与最小完整槽复核队列

`local-second-wall-diagnostic/4`的`PARTIALLY_OBSERVED`只表示存在墙状像素证据但没有完整、同源、唯一槽口。
它必须同时满足`authoritative=false`、`posePromotionAllowed=false`、`experimentalCandidate=null`；顶层仍为
`GROOVE_SOURCE_INCONSISTENT`、`valid=false`，当前角、修正角和PLC均为空。人工确认的374可见真壁不会进入运行时。

服务器或Mac可从冻结三折manifest/JSONL生成两帧最小正向复核队列。part-006是sealed，part-019是已知
partial/mixed负例，二者都通过显式审计排除项记录，不是固定角或运行时ignore：

    uv run --with jsonschema python tools/build_complete_groove_review_queue.py \
      --manifest "$A2_PRIVATE/manifests/fold-01/validation-manifest.json" \
      --manifest "$A2_PRIVATE/manifests/fold-02/validation-manifest.json" \
      --manifest "$A2_PRIVATE/manifests/fold-03/validation-manifest.json" \
      --results "$A2_PRIVATE/results/021-bidirectional-v3-working/fold-01.jsonl" \
      --results "$A2_PRIVATE/results/021-bidirectional-v3-working/fold-02.jsonl" \
      --results "$A2_PRIVATE/results/021-bidirectional-v3-working/fold-03.jsonl" \
      --exclude-sample normal:part-006=sealed_transition_sample \
      --exclude-sample normal:part-019=human_confirmed_partial_mixed_opening \
      --max-samples 1 --frames-per-sample 2 \
      --output-dir "$A2_WORK/complete-groove-review-021"

输出`review-queue.json`、`review-queue.csv`和`review-manifest.json`，全部位于Git外。它们只说明哪些帧值得人工检查，
不表示完整槽已检测正确。对当前140张，若队列选择part-008候选，可用fold-03结果生成精简AUTO审阅包：

    uv run python tools/prepare_slot_pose_prefill_review.py \
      --manifest "$A2_WORK/complete-groove-review-021/review-manifest.json" \
      --data-root "$A2_PRIVATE" \
      --results-019 "$A2_PRIVATE/results/021-bidirectional-v3-working/fold-03.jsonl" \
      --results-020 "$A2_PRIVATE/results/021-bidirectional-v3-working/fold-03.jsonl" \
      --output-dir "$A2_WORK/complete-groove-review-021/review-bundle"

人工最少回答：两条AUTO墙是否都属于同一真实方形槽、两槽口端点是否准确、整个真实槽是否无遮挡完整可见、
是否有任一边来自fixture shadow。若任一回答不确定，保持partial/fail-closed；不要根据算法建议直接改成HUMAN真值。

Mac在`fc9210d`上已完成140张独立回放与队列重建，结果同样选中part-008的147/145，并保持
`0/140 valid`。因此当前不需要重跑140张或重建队列；下一步只查看已生成的RAW/SIMPLIFIED联系表，
逐张回答上述四问。审阅结论未形成前，禁止从AUTO预测反推HUMAN标注或修改门限。

145/147最终人工澄清为A：同一真实方形槽=YES、两侧完整无遮挡=YES、端点位于真实外圆
槽肩=YES，两条`AUTO_detected_groove_wall_left/right`本身正确且干净。只有其他非槽候选标记落在
fixture shadow区域，而且这些阴影区域没有被完整标出。

**停用警告**：不要再运行`prepare_fixture_contamination_annotation.py`，不要在既有派生LabelMe中添加
`HUMAN_fixture_shadow_overlap_on_detected_wall_left/right`。已生成的两份文件只作为误解流程的历史证据，
保留原SHA，不覆盖、不补画、不导入。更正后的CLI会在写出前明确拒绝。

下一个最小人工像素复核改为：

1. 在left墙上独立点选至少3个沿可见墙分散的支持点。
2. 在right墙上以同样方式点选至少3个支持点。
3. 独立点选left/right两个槽口端点。
4. 不从AUTO线复制坐标，不要求补画fixture shadow边界。

这一步只能核对墙与端点像素位置。若要验收最终姿态角精度，还需同图的独立外圆可见弧或圆心真值。
在这些像素真值和独立验证设计完成前，禁止调门限或宣称像素/角度准确率。

## 145/147独立干净槽壁像素复核

以下任务与先前AUTO审阅包分开，生成的LabelMe初始`shapes=[]`。工具只验证AUTO文件SHA，不读取其
shape坐标，也不复制原图。所有输出必须位于Git外：

    REVIEW_BUNDLE="$A2_WORK/complete-groove-review-021/review-bundle"
    CLEAN_REVIEW="$A2_WORK/clean-groove-pixel-review-021"

    uv run --with jsonschema python tools/prepare_clean_groove_pixel_review.py prepare \
      --review-index "$REVIEW_BUNDLE/review-index.json" \
      --image-id 'normal:part-008:fixed-pose:0005' \
      --image-id 'normal:part-008:fixed-pose:0007' \
      --semantic-authority FINAL_HUMAN_CLARIFICATION_A \
      --output-dir "$CLEAN_REVIEW"

生成后只打开`$CLEAN_REVIEW/labelme-independent/*.json`。每张图按以下标签独立落点，不打开AUTO
LabelMe抄坐标。本轮left/right按槽口两个端点在图像中的x坐标由小到大定义；交换两侧不影响中点，
但统一命名便于逐壁误差审计：

1. `HUMAN_clean_groove_wall_left_support`：沿left真实槽壁上、中、下分散点至少3个point。
2. `HUMAN_clean_groove_wall_right_support`：沿right真实槽壁同样点至少3个point。
3. `HUMAN_clean_groove_mouth_endpoint_left`：left槽壁与真实外圆槽肩交点，恰好1个point。
4. `HUMAN_clean_groove_mouth_endpoint_right`：right槽壁与真实外圆槽肩交点，恰好1个point。
5. 可选`HUMAN_outer_circle_visible_arc`：同图独立可见外圆弧，linestrip至少8点；或
   `HUMAN_outer_circle_center`：独立圆心point。两者都不画时只完成墙/端点复核，不能验收姿态角精度。

保存前在LabelMe全局flags中勾选`human_verified`，取消`annotation_pending`；保持
`independent_annotation=true`、`copied_from_auto=false`以及runtime/tuning/PLC三个权限为false。
不要添加任何`AUTO_` shape或已停用的`HUMAN_fixture_shadow_overlap_on_detected_wall_*`。

完成两张后校验：

    uv run --with jsonschema python tools/prepare_clean_groove_pixel_review.py validate \
      --task-manifest "$CLEAN_REVIEW/clean-groove-pixel-review.json" \
      --output "$CLEAN_REVIEW/validation-report.json"

`wallEndpointPixelReviewComplete=true`只证明墙/端点人工几何齐全；只有
`outerCircleReferenceAvailable=true`时`poseAngleAccuracyReady`才会为true。即使如此，报告中的
accuracy/tuning/runtime/PLC权限仍保持false，后续还需独立评估设计才能使用这些真值。
