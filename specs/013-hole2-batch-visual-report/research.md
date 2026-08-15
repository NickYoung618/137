# Research: 孔2单批次可视报告

## 外置参考审计

已完整阅读`detect_measurements.py`共1955行，并检查`f10_label.json`：该标注为3072×2048，
仅含一个label=`f10`、shape_type=`polygon`、486点的孔1对象。

### 可借鉴

- `draw_overlay`用Pillow在原图上画检测几何和状态文字。
- `write_csv`和`build_report`把逐图结果、分组摘要及异常原因落盘。
- `parse_image_sequence`/`product_group_summary`从文件尾号提取序列并报告缺口。

### 明确排除

- `cv2`梯度、连通域、Hough和孔1锚点检测；013不做任何检测。
- f10像素/mm标定、尺寸常数、规格上下限、guard band、PASS/REVIEW/FAIL和OK/NG。
- 将每20张直接定义为一个真实产品。013只输出未经采集规则确认的
  `captureGroupEstimate`。

## 设计决定

1. JSONL是唯一检测结果来源；工具不调用`current_capture.py`，所以不会改变质量状态。
2. 预览在缩小图上按同一比例绘制，节省磁盘；LabelMe JSON始终保存原始坐标。
3. 汇总不设置overall验收数，只提供`groups`对象，避免normal/defective混组。
4. 序列估计在每个group内独立进行，以该group最小尾号为估计锚点；缺失尾号或重复尾号单列。
5. 过滤只控制生成物，完整输入统计保持不变，以免only-invalid改变分母。

## 实现与服务器证据

- 工具仅导入标准库与Pillow，没有`cv2`或任何新依赖，也不调用孔2检测入口。
- 合成契约覆盖默认7条全量、only-invalid、重复frame、原坐标LabelMe、150px预览缩放、
  normal/defective分组统计、完整/缺口采集组和工作树拒绝。
- 服务器现有9帧默认运行生成9张JPEG与9份prediction JSON；所有3072×2048原图预览稳定为
  1536×1024，LabelMe仍记录3072×2048及原始坐标。
- 9帧汇总复现registration `9`、尺寸7 `4`、Phi `8`、双特征有效`4`、execution error `0`；
  失败原因数量与输入JSONL一致。
- 人工查看控制帧620确认青色尺寸7线/端点、绿色Phi圆和顶部数值清晰；完全失败帧501保留红色
  面板、红色边框及两个失败原因，没有伪造预测shape。
- 9帧尾号并非完整连续采集，`captureGroupEstimate`报告5个incomplete估计组和具体gaps，未把
  9/20或任何除法解释成物理零件数。
