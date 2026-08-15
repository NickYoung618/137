# Quickstart: A2多槽角色几何与Mac验收

## 1. 服务器全量测试

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

## 2. 历史legacy扫角回归

```bash
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-legacy" --angles=-175,-170,-165,0,165,170,175 --repeats 1 --seed 137
uv run python tools/make_manifest.py \
  --input "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic" \
  --output "${TMPDIR:-/tmp}/slot-pose-legacy/manifest.json" \
  --dataset-id legacy-smoke --task slot_pose --expected-repeats 1
uv run python tools/run_slot_pose_batch.py \
  --manifest "${TMPDIR:-/tmp}/slot-pose-legacy/manifest.json" \
  --data-root "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic" \
  --config "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic-config.json" \
  --output "${TMPDIR:-/tmp}/slot-pose-legacy/results.jsonl"
```

## 3. paired合成真值回归

```bash
uv run python tools/generate_synthetic_paired_notches.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-paired" --seed 137
uv run python tools/run_slot_pose_batch.py \
  --manifest "${TMPDIR:-/tmp}/slot-pose-paired/manifest.json" \
  --data-root "${TMPDIR:-/tmp}/slot-pose-paired/images" \
  --config "${TMPDIR:-/tmp}/slot-pose-paired/config.json" \
  --output "${TMPDIR:-/tmp}/slot-pose-paired/results.jsonl"
```

预期：平移、缩放、亮度/噪声和±180°环绕正样本通过；缺一槽、多余暗区、配对歧义、
裁切和错误配置样本fail-closed。

## 4. Mac A2外置数据一键验收

在读取A2前，先以`multi_notch_roles`合成图验证通用角色分配（额外候选不导致失败，角色缺失/歧义必须失败）：

```bash
uv run python tools/generate_synthetic_multi_notches.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-multi-role" --seed 137
```

先根据采集记录准备显式分组CSV，再执行：

```bash
uv run python tools/run_a2_acceptance.py \
  --normal-root "$A2_NORMAL_ROOT" \
  --bad-root "$A2_BAD_ROOT" \
  --grouping "$A2_GROUPING_CSV" \
  --truth "$A2_TRUTH_CSV" \
  --config "$A2_CONFIG" \
  --output-dir "$A2_REPORT_DIR"
```

该命令按顺序生成并验证Manifest、运行批处理、校验truth，然后分别生成`normal-report.json`和
`bad-report.json`。所有路径由命令行提供；原图、压缩包和派生大图不写入仓库。

将批处理结果生成人工核对包（必须指向仓库外目录）：

```bash
uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULTS_JSONL" \
  --data-root "$A2_DATA_ROOT" --output-dir "$A2_REVIEW_DIR"
```

输出含`review.json`、`candidates.csv`、`failures.csv`、`overlays/`和`contact-sheet.jpg`。其中角色组合只是现场勾选用假设，
`roleSuggestionsAreAuthoritative=false`固定表示它们不是业务真值。
新审阅图中绿色表示通过单帧几何门的`grooveCandidates`，红色表示被拒绝的原始暗区；
颜色仅表示几何过滤结果，不表示已确认datum/target角色。

比较全画面与开发ROI的跨帧候选稳定性、门控成功率、错误码和耗时（输出仍必须在仓库外）：

```bash
uv run python tools/summarize_slot_pose_diagnostics.py \
  --run "full-frame=$A2_FULL_REVIEW_JSON" \
  --run "development-roi=$A2_ROI_REVIEW_JSON" \
  --cluster-threshold-deg 8 --output "$A2_DIAGNOSTIC_COMPARISON"
```

跨帧稳定只能证明图像特征可重复；固定工装、遮挡和光照边界也可能高度稳定，不得因此自动分配datum/target角色。

## 5. 单真实槽运行模式

复制配置到Git外目录，将`detector.diagnostic_mode`显式设为`single_real_groove`；保持
`single_groove_pose.expected_accepted_groove_count=1`并显式选择v2单槽目标契约。v2固定：

- 物理外圆圆心为原点，图像向右`+X`、向下`+Y`；
- 向下`+Y`半轴为datum，顺时针为正；
- 真实槽口中点必须满足`x<centerX,y>=centerY`；
- 实测角目标`+85°`、公差`±5°`；
- 图像纠偏正为顺时针、负为逆时针。
- 粗暗区边界只作搜索初值；最终角必须来自左右亚像素侧壁拟合线与gyj物理外圆的两个交点。

不得依据候选数量自动切换模式。然后运行原批处理和审阅：

```bash
uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --config "$A2_SINGLE_GROOVE_CONFIG" --output "$A2_SINGLE_RESULTS"
uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --results "$A2_SINGLE_RESULTS" \
  --data-root "$A2_DATA_ROOT" --output-dir "$A2_SINGLE_REVIEW_DIR"
uv run python tools/summarize_slot_pose_diagnostics.py \
  --run "single-real-groove=$A2_SINGLE_REVIEW_DIR/review.json" \
  --output "$A2_SINGLE_SUMMARY"
```

检查`physicalOuterCircleAccepted`、`grooveRefinementStatusCounts`、`yDownDatumAngleAvailable`、
`targetToleranceStatusCounts`和`imageFrameCorrectionAvailable`，不要用顶层`result.valid`替代槽识别、
亚像素精修或公差评估成功率。
B-005未确认时预期错误为`PLC_MAPPING_UNCONFIRMED`而不是`GROOVE_RECOGNITION_FAILED`；
`signedRelativeRotationDeg`仍必须为`null`。v1配置继续为`NOT_EVALUATED`，不会静默获得v2语义。

## 6. 正式结论门禁

B-001目标实体、B-003图像角、B-006 datum、B-007目标/公差/方向和B-008目标槽映射已经关闭。
B-002真实数据分组、B-004精度/节拍验收门槛和B-005 PLC契约仍未关闭；报告可提供测量、公差和
图像纠偏诊断，但顶层PLC可执行角仍为空，不接入PLC。

## 7. 用LabelMe制作物理外圆标准答案

在原始BMP上人工创建一个`circle`，标签必须为`physical_outer_circle_truth`；不要把算法圆
复制成标注。标注完成后在LabelMe JSON的根级`flags`中设置
`human_verified=true`和`independent_from_algorithm=true`，再由另一人复核：

```bash
uv run python tools/build_labelme_circle_truth.py \
  --annotation "$LABELME_JSON" --image-root "$A2_BMP_ROOT" \
  --annotator "$ANNOTATOR" --reviewer "$REVIEWER" \
  --truth-version a2-circle-v1 --output "$CIRCLE_TRUTH_JSON"
```

输出只保存受控相对路径和哈希。两点`circle`适合独立复核已拟合圆，但若已经精细标注了长可见圆弧，
优先使用下一节的多点robust/geometric参考；JPEG诊断副本上的重复性不是绝对精度。

## 8. 审阅人工外圆弧与开放槽边界

源标注、原BMP和全部输出必须位于Git工作树外。源标签通过参数映射，不能假定固定点数：

```bash
uv run python tools/review_labelme_groove_pose.py \
  --annotation "$MANUAL_GROOVE_DIR/manual.json" \
  --image "$MANUAL_GROOVE_DIR/source.bmp" \
  --config config/inspection.example.json \
  --circle-label 1 --groove-label 2 \
  --target-angle-deg 85 --target-quadrant lower_left \
  --report "$MANUAL_GROOVE_DIR/manual-groove-pose-review.json" \
  --semantic-copy "$MANUAL_GROOVE_DIR/manual-groove-semantic-copy.json" \
  --preview "$MANUAL_GROOVE_DIR/manual-groove-pose-preview.jpg"
```

如果LabelMe确实含非空`imageData`可省略`--image`；为空时必须显式提供外置图像。语义副本标记为
非运行时、非正式真值，源JSON不会覆盖。旧v1审阅目标仍可保持`NOT_EVALUATED`；离线报告另以
`manual-groove-y-down-target-diagnostic/1`复用Y下半轴数学约定，并明确标记中点来自人工边界端点。
生产运行时v2不读取该LabelMe，也不会把人工来源伪装成自动亚像素交点。

## 9. 人工拟合参考与自动亚像素结果对照

先对同一原始BMP运行`single_real_groove` v2，再将第8节的人工审阅报告与运行时结果比较：

```bash
uv run python tools/compare_pose_reference.py \
  --manual-review "$MANUAL_GROOVE_DIR/manual-groove-pose-review.json" \
  --runtime-result "$MANUAL_GROOVE_DIR/runtime-v2.json" \
  --output "$MANUAL_GROOVE_DIR/manual-vs-runtime-comparison.json"
```

比较器强制图像SHA-256和锁定gyj源SHA-256一致，分开报告圆心向量/距离、半径差、圆心误差的角度
影响上界，以及人工槽边界中点与自动侧壁—外圆交点中点的环形差。约1646 px半径下`1 px≈0.0348°`
只作理论分辨率预算；单张、单人、未独立复核结果固定为`DEVELOPMENT_REFERENCE`，不得称为生产准确率。
