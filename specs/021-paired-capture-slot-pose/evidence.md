# Evidence: 021双帧配对槽姿态

## Baseline

- Parent branch: `020-fixture-shadow-groove-consistency@a964d56a7ffb2f47de6427679f602e28037e21e8`
- Feature branch: `021-paired-capture-slot-pose`
- Plain `uv run python -m unittest discover -s tests -v`: 359 tests ran; two import errors were solely the missing optional `jsonschema` package in the plain environment (`test_current_capture_contract`, `test_current_capture_real_e2e`), with 19 skips. This is an external dependency gate, not an algorithm regression.
- Authoritative full gate uses `uv run --with jsonschema ...`.

## SpecKit Analyze

- Buildable requirements: 34 (25 FR + 9 SC)
- Tasks: 22
- Requirement coverage: 100% at story/task level
- Critical Constitution conflicts: 0
- Unresolved behavior ambiguity: 0; unknown现场 rotation values are represented by `UNCONFIRMED` state.

## Data and Truth Boundary

- No real paired BMP is available on the server; no real paired accuracy claim is possible.
- Sealed `normal:part-006` was not read or rerun.
- `Pic_2026_08_13_132354_292.bmp` remains skipped.
- part-019 374/369 are the active review targets, but their media and generated review artifacts remain outside Git.
- Existing 132112_4 manual outer arc/groove boundary may be used only as a development reference and never as runtime input.

## Final Verification

- Focused paired/review tests: `26 tests`, all passed.
- Authoritative full gate: `uv run --with jsonschema python -m unittest discover -s tests -q` ran `391 tests` in `107.311s`; all passed.
- JSON and Schema syntax, Python compile, both CLI help entry points, and `git diff --check`: passed.
- New-file large-media scan found no file over 1 MiB; changed-content scan found no Mac/server evidence absolute path.
- Worst-case bounded 16x16 pure matcher microbenchmark (`n=1000`, excludes both single-frame detectors): P50 `1.826188ms`, P95 `2.172057ms`, max `4.876364ms` on this server. Real paired BMP end-to-end timing remains a Mac gate.
- Default example remains `enabled=false`; `UNCONFIRMED` rotation cannot produce image guidance, and PLC execution remains not authorized even after a confirmed diagnostic match.
- `main` and `origin/main` were both `04d179628a6f3f7f2a30d2a4884ce5ef98abfffa` before feature-branch commit/push. No main merge is authorized for 021.

## Simplified Manual Review Convergence

- Scope: part-019 374/369 review presentation only. No detector, threshold, paired matching, default configuration or PLC code changed.
- The prior v1 review bundle exposed the full 019/020 debug overlays, fitted circle and every raw ray. Revised `slot-pose-prefill-review/2` emits only full-resolution raw/simplified, a two-column contact sheet and minimal AUTO_ LabelMe.
- Simplified layers are limited to 019 final left/right walls and mouth endpoints plus 020 observed dark angular intervals. Pair identity selection uses only `pairEvidence.selectedCandidateIds`; incomplete/not-matched evidence is never filled by the nearest candidate.
- A raw start/center/end is rendered as an open orange circumference bracket with three ticks. It is explicitly labelled `Observed dark angular interval / Fixture identity unconfirmed / Pixel boundary unknown`; only missing intervals degrade to a direction arrow. No polygon or filled region is emitted.
- TDD red gate: the new focused test initially failed because the simplified text/render contract did not exist. Green gate: paired/review focused suite ran `26 tests` in `0.111s`, all passed.
- Authoritative full gate after the review change: `391 tests` in `105.935s`, all passed.
- Schema JSON, CLI help, Python compile and diff checks passed. The review test verifies two rows, original-resolution simplified PNG, stable colors, interval/direction downgrade, no nearest-unmatched identity, no filled region, no overlay directories, and no fitted-circle/raw-ray/rectangle/truth labels.
- Real 374/369 BMPs are not available on the server, so no generated image is committed and no visual correctness claim is made here. Mac must generate the Git-external bundle and the user must confirm the true groove and same-source walls.

## 2026-08-16 Single-frame Local Second-wall Convergence

- Human semantic feedback is recorded without pixel-truth inflation: the top square opening is the real groove region; 019 hit at least one real wall/region but paired its second wall with the upper-right fixture shadow. The feedback does not define exact wall pixels, mouth endpoints or fixture boundaries.
- Added optional `detector.local_second_wall_diagnostic`; omission and `enabled=false` preserve the prior effective/default runtime path. Enabling requires single_real_groove, refinement v2 and the unchanged enabled 020 source-consistency gate.
- The search reuses the existing subpixel tangential sampler, deterministic consensus TLS wall fit and sidewall profile consistency. It scans at most 48 configured seeds inside the coarse local interval and retains every side-search candidate and every pair hypothesis with failed checks.
- Hard layers are `candidate_anchor`, `local_geometry` (interval, width, parallelism, radial coverage), `mouth_endpoint` (same physical-circle residual), `opening_structure` (dark connected support), `sidewall_source` (contrast/gradient/profile/endpoint structure), and uniqueness. Diagnostic score cannot override any failed hard gate.
- Failure inventory is explicit: `CANDIDATE_MISSING`, `LOCAL_SECOND_WALL_NOT_FOUND`, `MULTIPLE_LOCAL_OPENINGS`, and `SOURCE_INCONSISTENT` with `failureStage`.
- `UNIQUE_DIAGNOSTIC` is never authoritative: `authoritative=false`, `posePromotionAllowed=false`. A runtime integration test forces a unique experimental result and verifies that the surrounding output remains `GROOVE_SOURCE_INCONSISTENT`, `valid=false`, with null image correction and no PLC command.
- Synthetic tests cover arbitrary rotations including 0/360, real grooves near 31°/328°, endpoint reversal via wrap, brightness reduction, additional blur, unequal fixture contrast/width/depth, partial overlap, multiple openings and missing second walls. Controlled brightness/blur cases assert each endpoint error <0.15° and midpoint error <0.10°.
- The part-019 file names, angles and coordinates are absent from runtime code/config. Sealed part-006 was not read or rerun. Existing 132112_4 manual reference was not used as runtime input and still cannot support an accuracy percentage.

## 2026-08-16 Final Gates for This Increment

- SpecKit analyze: 42 FR, 13 SC, 38 tasks; no placeholder, critical Constitution conflict or uncovered new implementation task. Two stale “fixture region” phrases were reconciled to the angular-interval contract before the final run.
- Focused gate: 57 contract/runtime/review/local-wall tests passed before deformation expansion; final local-wall suite contains 10 passing tests.
- Authoritative full gate: `uv run --with jsonschema python -m unittest discover -s tests -q` ran 405 tests in 111.673s; all passed.
- All JSON parsed; all root contract Schemas passed Draft 2020-12 meta-validation; Python compile, both affected CLI help commands and `git diff --check` passed.
- Changed-content scan found no new server/Mac absolute data root, evidence root or A2 archive path. Relevant source/spec/test trees contain no file over 1 MiB and no BMP/JPEG/PNG/MP4/RAR/ZIP.
- Server has no 140 original BMP validation set, so Mac three-fold replay remains required. The quickstart reports top-level valid, experimental candidate status and failure inventory only; it explicitly forbids calling these counts accuracy.
- `main` and `origin/main` remain `04d179628a6f3f7f2a30d2a4884ce5ef98abfffa`; this increment is feature-branch only and must not merge main.

## Mac 140-frame Replay at 8ff3889

- Mac used 140 nonsealed original BMPs and the existing three validation manifests. Experimental config SHA prefix was `79960702`; server does not possess these BMPs or JSONL and did not rerun them.
- Top-level valid remained 0/140. The earlier 33 `GROOVE_SOURCE_INCONSISTENT` frames ran local diagnostics; the other 107 failed upstream and remained `NOT_RUN`.
- All 33 local runs were `SOURCE_INCONSISTENT`: part-019 20 frames and part-008 13 frames. Each part-019 record had 48 side search entries and one final hypothesis.
- The only part-019 hypothesis still failed `sidewall_source_consistency / edge_contrast_asymmetry`; 374/369 contrast normalized difference remained approximately 0.127–0.138 against the unchanged 0.12 gate while other reported gates passed.
- Human interpretation is unchanged: the hypothesis appears to reproduce the known real-wall plus upper-right fixture-shadow mixed pair. Therefore this replay is not a recovery and is positive evidence against relaxing 0.12 to 0.14.
- Required next evidence is pre-threshold generation trace: inherited local interval, both anchors, every seed fit/rejection, side merge clusters and hypothesis merge clusters. No accuracy or valid-rate improvement is claimed.

## Candidate-generation Trace Increment

- Diagnostic output advances to `local-second-wall-diagnostic/2`; config schema and every numerical threshold remain unchanged. The 0.12 contrast gate, ±4° tangential search, minimum support and 0.5° merge threshold were not relaxed.
- Each anchor now records original endpoint angle, required opposite polarity, finite line segment, support, contrast, gradient and local profile. `localInterval.source=coarse_raw_dark_candidate` makes inherited mixed intervals explicit.
- Every seed records its search window, polarity, detected points, rejection stage (`EDGE_SAMPLING`, `LINE_CONSENSUS`, or `OUTER_CIRCLE_INTERSECTION`), fit angle/delta, line/finite segment, failed checks and merge disposition.
- Side merge clusters preserve all member/suppressed IDs, seed/fitted angles, spread, representative and the unchanged v1-compatible selection rule. Pre-merge hypotheses and hypothesis clusters similarly permit exact member accounting.
- Per-polarity summaries classify `NO_EDGE_SIGNAL`, `SINGLE_EDGE_ATTRACTOR`, or `MULTIPLE_EDGE_CLUSTERS`. This is diagnostic evidence only; it does not select a more permissive pose.
- Added a path-free `local-second-wall-trace-export/1` CLI. It selects exact image basenames from one or more JSONL files and emits no image pixels, absolute paths or human truth; output is required to remain Git-external and explicitly forbids threshold tuning.

## Verification for Candidate-generation Trace

- Focused local-wall/trace tests: 14 tests passed. Broader focused runtime/contract/review gate: 64 tests passed; the printed Git-internal-output error is an expected negative safety test.
- Full suite ran 409 tests. 408 passed; the only failure was the pre-existing legacy wall-clock assertion `<8.0s`, measured at 15.93s. An isolated rerun measured 16.00s and failed the same timing-only assertion.
- During both timing measurements, an unrelated protected-repository four-worker image batch occupied all available CPUs at roughly 30% CPU per worker. The failing legacy path does not contain or execute the default-off local diagnostic. The 8-second gate was not modified or waived; a clean-load rerun remains required before claiming the full gate passed.
- JSON parsing, all root Draft 2020-12 Schema meta-validation, Python compile, trace CLI help, diff, media/large-file and new absolute-data-path checks passed.
- After that external batch finished, the isolated unchanged legacy timing gate passed in `3.443s` against the original `<8.0s` assertion. A clean-load authoritative rerun then executed all `409 tests` in `109.561s`; all passed. No performance threshold, detector threshold or default configuration was changed to obtain this result.

## 2026-08-17 Bidirectional/Outward Wall-search Increment

- The server replay used the three locked validation manifests: fold sizes `60/40/40`, seven complete physical parts, `140` original grayscale BMPs, and no `normal:part-006`. Media, manifests, JSONL and review images remained Git-external.
- Experimental config advances to `local-second-wall-diagnostic/2`; output advances to `local-second-wall-diagnostic/3`; algorithm contract version is `0.15.0`. The repository example remains `enabled=false`. The source-consistency contrast gate remains exactly `0.12`, physical-wall merge remains exactly `0.5°`, and no PLC path is enabled.
- Each untrusted coarse start/end anchor now creates bounded `INWARD` and `OUTWARD` wrap-safe domains. Every domain samples both gradient polarities; each seed records domain, direction, angle, detected edge count, line/intersection outcome and rejection stage. Accepted fits are merged only into physical-wall clusters. Wall pairs use order-independent canonical IDs and do not merge A→B/B→A duplicates.
- Configured limits are `32` seeds/domain, `256` jobs/image and `32` physical wall candidates. Search extents are bounded by the configured maximum physical slot width. Limit overflow fails closed before pose promotion.
- The previously rejected initial start/end pair is retained as evidence but cannot be recycled as a successful experimental pair. A unique experimental wall pair remains `authoritative=false` and `posePromotionAllowed=false`; simplified review labels use `AUTO_experimental_` and never become human truth.

## Server 140-frame Replay for diagnostic/3

- Top-level result: `0/140 valid`, exactly preserving fail-closed behavior. Local bidirectional diagnostics ran on `33/140`; the remaining `107/140` stopped at their existing upstream stage.
- Final error distribution: `GROOVE_SOURCE_INCONSISTENT 33`, `HOUSING_CIRCLE_NOT_FOUND 27`, `GROOVE_RECOGNITION_AMBIGUOUS 20`, `GROOVE_RECOGNITION_FAILED 20`, `GROOVE_REFINEMENT_FAILED 20`, and `PHYSICAL_OUTER_CIRCLE_FAILED 20`.
- Per part: part-008 had `13` source-inconsistent and `7` housing-circle failures; part-009 `20` housing-circle failures; part-014 `20` groove ambiguities; part-015 `20` groove-recognition failures; part-019 `20` source-inconsistent; part-021 `20` refinement failures; part-023 `20` physical-circle failures.
- All `33` local runs produced four domains, `176` bounded jobs, two physical-wall clusters, one canonical pair and zero passed pairs. The canonical pair always failed closed; no new pose was promoted.
- On part-019, the only falling cluster remained `285.952977°..285.957352°` and the only rising cluster `309.480010°..309.481928°`. These are the same old mixed endpoints, not a recovered second true wall. The falling side accepted only `5..6` seeds/frame and the rising side exactly `5`; outward seeds mostly failed at edge sampling, with smaller line-consensus and outer-circle-intersection populations. Therefore the earlier “inward-only” defect is fixed, but real BMP evidence only proves that no additional visible wall cluster was generated; it does not prove that the opposite true wall is observable in this frame.
- The old mixed pair now explicitly fails `reuses_rejected_initial_pair`, `sidewall_source_consistency`, and `source_consistency:edge_contrast_asymmetry`. The known part-019 false positive remains blocked. part-008 also remains blocked because it has no human truth; its rejection is not called a false positive or false negative.
- Runtime `diagnostics.elapsedMs` over 140 images was P50 `2258.6 ms`, P95 `3035.3 ms`, max `3696.6 ms`; among the 33 local runs it was P50 `2883.1 ms`, P95 `3379.6 ms`, max `3696.6 ms`. This is an experimental enabled-path measurement, not the default performance path. The disabled/default path is unchanged and covered by contract tests.
- Fold JSONL SHA-256 values are `c47ace3316d2bfacadda703b6c6e98b7313858a5894ccd6458ec4f18132843cd`, `7411c7ceef40a9ef1e0bee76fd68afbce09fb8da4066756ed9c3b486d075b57c`, and `11414b8e4a465ac11fb69a7db2f3e087ef7076913a0b83b43885ac44173eecbd`. The 374/369 RAW/SIMPLIFIED contact sheet SHA-256 is `db5984c6acc44b984010084bf76258c41ca1448805147b7909c27f3cca6fbb78`.
- The review bundle compares the old 019 walls against the diagnostic/3 canonical pair and marks both experimental walls non-authoritative. It does not assert a recovered wall. Pixel-level truth is still required before changing wall generation or reporting endpoint accuracy.

## Final Verification for diagnostic/3

- SpecKit analyze after task generation found `0` critical Constitution conflicts, placeholders or uncovered new implementation requirements.
- Focused schema/runtime/review gate passed `25` tests before limit/conservation additions; the final authoritative suite ran `418 tests` in `141.114s`, all passed.
- Every root JSON Schema passed Draft 2020-12 meta-validation; the example config and a generated diagnostic/3 payload validated. Trace export now enforces accepted-wall cluster membership, raw-hypothesis membership and canonical-pair uniqueness.
- `git diff --check`, Python compile and affected CLI tests passed. Media and replay outputs remain outside Git. No accuracy, precision or “seven groups fixed” claim is made.

## 2026-08-17 Human-visible-wall Semantic Correction

- Mac保存的Git外LabelMe相对文件为`raw/review-01-Pic_2026_08_13_132433_374.json`，图像尺寸`5472x3648`。唯一shape的原label为`HUMAN_true_groove_wall_missing`，两点为`[[3266.0,258.5],[3226.0,331.0]]`。label名称来自先前错误指导，不能按字面作为“另一侧壁”真值。
- 服务器已在Git外只读复核原人工JSON SHA-256为`aba3f10c0b34c63c2407e1b418828799f732ab363d145485ba470b294a85aad0`；安全派生副本SHA-256为`fbf684e9f35a1b3b16cfab32796ea060a9b29d0b279f127b819c8025df8ff5ba`；传输压缩包SHA-256为`6ec230cdfdf820095478e3f4406bf346ac93a5ea8cf041aefe271a3b6a673678`。三者均保留Git外。
- 派生副本label为`HUMAN_confirmed_visible_real_groove_wall`，顶层flags为`human_verified=true`、`annotation_semantics=confirmed_visible_real_groove_wall_only`、`full_groove_truth=false`、`pose_truth_allowed=false`；两点几何与原件完全相同。
- 使用用户提供的两点与服务器Git外AUTO审阅JSON只读比较：人工线长`82.8025 px`；AUTO `detected_groove_wall_left`共有`26`点；AUTO点到人工无限线的距离中位`1.6417 px`、最大`2.8163 px`；两线方向差`2.895°`；人工两端到AUTO首/末端距离约`9.56 px`与`1.76 px`。这些数值支持“近乎重合”，不支持它是新的相对侧壁。
- 审核语义据此修正为`human-confirmed-visible-real-groove-wall`：285.953°cluster是一条人工确认的可见真实槽壁；309.48°为fixture shadow edge，不可与其配对。该人工线不提供相对侧壁、完整槽口、槽中点或姿态角真值。
- 相对真实槽壁在该帧是否可见仍未知，且可能被遮挡。单帧算法不得从槽宽或方位先验镜像/补造不可见壁，也不得要求人工猜线；当前顶层fail-closed是正确安全行为。局部Cartesian搜索仅对可见像素证据有效，双拍负责至少取得一张无遮挡完整开口。

## 2026-08-17 Initial MVP Partial-observation Increment

- 局部输出升至`local-second-wall-diagnostic/4`，算法契约版本升至`0.16.0`；配置仍是`local-second-wall-diagnostic/2`且默认`enabled=false`。020同源对比门保持`0.12`、物理墙merge保持`0.5°`，没有PLC路径或main合并。
- `PARTIALLY_OBSERVED`只描述“至少有墙状cluster，但完整同源唯一槽口未建立”。它输出cluster ID和观测限制，不选择真壁身份；`experimentalCandidate=null`、`authoritative=false`、`posePromotionAllowed=false`。
- 服务器只重跑Git外part-019代表帧369/374，没有重跑完整140张。两帧均为顶层`GROOVE_SOURCE_INCONSISTENT`、`valid=false`、当前角/null、图像修正/null、PLC/null；局部状态均为`PARTIALLY_OBSERVED/PARTIAL_GROOVE_OBSERVATION`。
- 两帧唯一canonical pair仍同时失败`reuses_rejected_initial_pair`、`sidewall_source_consistency`和`source_consistency:edge_contrast_asymmetry`，因此374已确认真壁与309.48°fixture边没有形成实验完整槽。运行JSONL SHA-256为`8a4b0cb4edd826a1adba1cc4e70a47e89d40a865d0c936822c4f846238eb5af6`。

## Complete-groove Review Queue from Frozen 140 Frames

- 只读盘点三折`60/40/40`、七个物理sample且不含sealed part-006。part-008有`13/20`帧到达双壁refinement候选、`7/20`为`HOUSING_CIRCLE_NOT_FOUND`；part-019有`20/20`双壁refinement候选但因人工确认partial/mixed而显式排除。
- part-009、014、015、021、023的双壁证据帧均为0，分别停在圆定位、槽歧义、槽识别、槽精修或物理外圆阶段。因此当前最小正向复核队列只选择part-008，不表示该组真实完整槽已确认。
- 组内不看预测角、修正量、置信度或门限距离，只用`sha256(sampleId|sourceImageSha256)/1`选择两帧：`Pic_2026_08_13_132229_147.bmp`（repeat 7）和`Pic_2026_08_13_132229_145.bmp`（repeat 5）。两者仍为`humanVerified=false`、`GROOVE_SOURCE_INCONSISTENT`待审样本。
- Git外产物SHA-256：`review-queue.json`=`40b85f2e7084e3bd77088db6a6ddda54d419684be4f1d2cbaecb33736306fc58`；`review-queue.csv`=`c288b0973d295fdc1835f0061ce273c2d1325ff2d55512ae493c5d5402f1672c`；`review-manifest.json`=`b4b33042168a07ea7ce58efb311da468533ce0e1c06620ab36714c7895afe142`。
- 精简RAW/SIMPLIFIED联系表已人工抽查，只显示待审墙/端点、暗区区间和非权威声明，没有人工真值框。`contact-sheet.jpg` SHA-256为`2cf1d469b36b75839fb99c8f781f21de6bd02f0f43d6e3fc6f1c6797ac132bb9`，`review-index.json`为`879699998cf445deae213006fad8ee53ff654411a0c1e49039d138ed3faf7559`；媒体仍全部Git外。

## Final Verification for Initial MVP Partial-observation Increment

- SpecKit analyze覆盖70个FR、25个SC和68个任务；无未覆盖的新实现需求、占位符或Constitution冲突。requirements checklist为`16/16`完成。
- 聚焦门：`tests.test_local_second_wall`/`test_single_real_groove`/`test_local_second_wall_trace`/`test_complete_groove_review_queue`共47项，全部通过；队列专项共3项，全部通过。
- 首次全量运行422项，421项通过；唯一失败是旧legacy适配器`<8.0s`壁钟门在并发视觉任务下测得`16.442s`。未修改或放宽该门。相同性能项独立复跑为`6.494s`并通过；随后权威全量复跑`422 tests in 143.452s`，全部通过。
- 39个根目录JSON Schema通过Draft 2020-12 meta-validation；真实队列和真实partial输出均通过对应Schema。Python compile、受影响CLI help和Git内JSON解析通过。
- `git diff --check`、媒体/大文件、绝对数据路径与原始证据污染门通过。Git中没有BMP/JPEG/PNG/MP4/RAR/ZIP、人工JSON、140张回放JSONL或客户数据绝对路径。
- `main`/`origin/main`仍为`04d179628a6f3f7f2a30d2a4884ce5ef98abfffa`；本轮仅提交并推送`021-paired-capture-slot-pose`，不合并main、不启用PLC。

## Mac Independent Gate at fc9210d

- Mac将独立验证分支快进到`fc9210dd172a1db96d20daf5b9bbe70d1d193f97`，未改代码、未合并main。聚焦测试`33/33`通过，`1`项按平台条件skip。
- Mac使用140张原始BMP、现有三折manifest和Git外实验配置独立回放；配置SHA-256为`f234a88b91971b780c6ae6dd5c786da630d090a398bce7515e40983a50de4447`。
- 顶层保持`0/140 valid`。失败分布为`GROOVE_SOURCE_INCONSISTENT 33`、`HOUSING_CIRCLE_NOT_FOUND 27`，以及`PHYSICAL_OUTER_CIRCLE_FAILED`、`GROOVE_RECOGNITION_AMBIGUOUS`、`GROOVE_RECOGNITION_FAILED`、`GROOVE_REFINEMENT_FAILED`各`20`。局部状态为`PARTIALLY_OBSERVED 33`、`NOT_RUN 107`，与服务器证据一致。
- Mac独立构建队列同样选中`normal:part-008`的`147`（rank 1）与`145`（rank 2），并正确排除part-006/019。Mac `review-queue.json` SHA-256为`b7946f853e7100bd0a52668928203765d0085b6ec6f0c6ec6817574c8570b8da`，联系表SHA-256为`d6cee826fcbddbf0e66062d60756161860dc54b78e7f4f31fce39ea92a58397c`。这些是独立Git外产物，不要求与服务器渲染文件哈希相同；可审计的核心是分支/配置哈希、输入manifest和队列选择语义。
- Mac外置相对证据目录为`initial-mvp-021-mac-fc9210d/complete-groove-review/review-bundle`，仍不进Git。人工尚未确认145/147的两墙同源、端点、无遮挡或fixture污染，所以Mac门只证明可复现性与fail-closed一致，不证明完整槽真值、姿态精度或识别率。
- 下一步仅是人工查看145/147并回答四个已版本化审阅问题。在此之前不根据AUTO图调参、不提升为真值、不合并main。

## Cross-platform Test-asset Isolation after Mac Full-suite Feedback

- Mac全量报告`Ran 394`，其中`4 errors`、`16 skip`且没有其他assertion failure。四个error同一根因：`tests/test_manual_groove_pose_review.py`三项和`tests/test_slot_pose_batch.py`一项直接使用服务器示例配置中的外置legacy资产路径。未设置Mac `PATH`时的uv child-process error已由Mac确认为调用环境问题，与槽逻辑分开记录。
- 新增`tests/slot_pose_test_support.py`，每个相关测试在系统临时目录生成可动态加载的最小legacy Python模块、参考图、LabelMe标注、实际SHA-256和隔离配置。人工槽复核测试仅调用fixture的Kasa/robust拟圆；批处理连续性测试显式mock单图检测结果，只验证“缺图后继续下一任务”的原始责任。
- 三个原人工复核用例和一个原批处理用例不再把config/inspection.example.json作为运行配置。新回归还检查临时配置的source/annotation/reference全部位于临时目录，且不含服务器专用资产根。
- 服务器聚焦门`17/17`通过；最终全量门`423 tests in 117.458s`，全部通过。本修复未改生产代码、`config/inspection.example.json`、任何资产SHA、检测门限、默认开关或PLC边界。
- Mac下一步是在更新后保持`PATH`包含其uv安装目录，重跑全量单测。此复跑只裁决跨平台测试资产隔离，不需要重跑140张BMP，也不触发算法调参或main合并。
