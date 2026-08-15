# Quickstart: Mac 2200定向复测与双版本审核

## 1. 同步候选

以下所有路径都必须换成Mac上的真实路径；不要原样复制`/实际/...`。可以把Finder中的文件或
文件夹拖入终端，让macOS自动填写路径。

```bash
cd '/实际/137壳体检测-孔2柱面和端面检测'
git pull --ff-only origin main
```

## 2. 严格分组运行2200张

```bash
bash scripts/run_hole2_full_regression.sh \
  '/实际/旧参考/annotation.json' \
  '/实际/旧参考/reference.bmp' \
  '/实际/normal-2000' \
  '/实际/defective-200' \
  '/实际/仓库外输出/hole2-full-regression-012' \
  4
```

验收只看`quality-summary.json`的`groups.normal`：registration `>=1962`、尺寸7 `>=1863`、
Phi `>=1922`，并按既有同一口径确认比例离群不增加。`groups.defective`只单列观察。

## 3. 生成状态变化帧的old/new审核资产

```bash
uv run python tools/render_hole2_batch_changes.py \
  --old-jsonl '/实际/旧版输出/current-capture-results.jsonl' \
  --new-jsonl '/实际/新版输出/current-capture-results.jsonl' \
  --image-root '/实际/包含normal和defective图片的外置根目录' \
  --output-dir '/实际/仓库外输出/hole2-012-review'
```

工具按`group + 文件名`配对，默认只输出注册/尺寸7/Phi状态或失败原因发生变化的帧。红色是旧版，
青色是新版。每帧目录包含：

- `old-new-overlay.png`：两个版本的尺寸7线/端点与Phi圆；顶部有版本、状态、失败原因和质量摘要。
- `old-new-predictions.labelme.json`：可在LabelMe打开的预测shape与完整审核元数据。

这些shape只是两个测量目标，不是所有零件轮廓，也不是真值标注。

## 4. 审核一个指定帧

指定文件名或不带扩展名的stem；`--frame`可以重复：

```bash
uv run python tools/render_hole2_batch_changes.py \
  --old-jsonl '/实际/旧版输出/current-capture-results.jsonl' \
  --new-jsonl '/实际/新版输出/current-capture-results.jsonl' \
  --image-root '/实际/外置图片根目录' \
  --output-dir '/实际/仓库外输出/hole2-012-controls' \
  --frame 'Pic_2026_08_12_215431_500' \
  --frame 'Pic_2026_08_12_215605_521' \
  --frame 'Pic_2026_08_12_215725_620'
```

若两个JSONL的group不同，工具会拒绝配对；不要通过改组名把normal和defective混在一起。

## 5. 已完成的最终验收记录

提交`2523ada6757e571987f4b40cc9b185acc387f71b`已在Mac完成T031：

- normal 2000：registration `1985`、尺寸7 `1901`、Phi `1955`、technicalComplete `1901`、
  execution errors `0`；三项门全部通过。
- 相对`3ee4b4f`状态变化129张，全部`False→True`，无`True→False`。
- normal同定义geometry离群36张，未增加；13张有独立风险证据并硬拒绝。
- defective 200：registration `159`、尺寸7 `108`、Phi `109`，独立观察且状态变化0。
- 最新唯一真值单图：尺寸7误差`0.717320388069254 px`，Phi直径误差
  `0.10530510518583469 px`，PASS。
- 审核工具匹配2200、变化129、渲染129、old/new unmatched均为0。

Mac运行目录和审核生成物仅作外置事实证据，不应复制进仓库或提交Git。
