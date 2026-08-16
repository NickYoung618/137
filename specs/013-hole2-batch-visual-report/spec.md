# Feature Specification: 孔2单批次可视报告

**Feature Branch**: `main`

**Created**: 2026-08-15

**Status**: Complete; server sample and all gates passed

## Scope

本功能读取现有孔2batch JSONL和仓库外原图，生成逐图JPEG预览、LabelMe兼容预测JSON及严格
按输入group分开的数量汇总。它是离线交付工具，不运行或改变孔2测量算法，不读取目标真值，
不做mm换算或生产OK/NG判断。

外置同学参考位于`/home/ubuntu/disk/dzk/hole2-classmate-reference-20260815/`。仅参考其
`draw_overlay`、序列分组和CSV/JSON报告思路；不复制f10测量核心、cv2依赖、孔1定位、标定常数、
规格上下限或生产判定。

## User stories

### US1 - 每张结果都有可审计预览（P1）

默认情况下，batch JSONL每条记录均生成缩小JPEG。尺寸7使用青色线和端点，Phi使用绿色圆；
顶部显示图片名、group、注册与两个特征的有效状态、失败原因和有效像素量测。即使执行或全部
预测失败，也生成带红色失败状态的预览。

### US2 - 原始坐标预测可在LabelMe打开（P1）

每条生成记录都有LabelMe兼容prediction JSON，`imageWidth/imageHeight`和坐标保持原图尺寸，
`imagePath`指向原图。shape最多只有`prediction:7`与`prediction:Phi12.2`，并声明它不是完整
零件轮廓也不是真值。

### US3 - normal/defective数量严格分组（P1）

`summary.json`、`summary.txt`和`index.csv`分别记录每个输入group的total、执行、注册、尺寸7、
Phi、双特征有效、失败原因及实际生成数量。不得把normal和defective合并成验收数。

### US4 - 过滤和采集序列估计（P2）

用户可选择仅无效记录或显式帧。工具按每个group内文件尾号和可配置组大小估计采集组，报告
complete/incomplete/gaps。字段必须命名`captureGroupEstimate`，并明确它未经采集规则确认，
不能解释为真实物理零件数量。

## Functional requirements

- **FR-001**: MUST 提供`tools/render_hole2_batch_report.py`，参数为`--jsonl`、`--image-root`、
  `--output-dir`。
- **FR-002**: MUST 默认处理JSONL每条记录；支持`--only-invalid`和可重复`--frame`。
- **FR-003**: MUST 使用Pillow/NumPy现有依赖，MUST NOT新增或导入opencv/cv2。
- **FR-004**: MUST 默认把预览最大宽度限制为1536且允许配置；不得放大较小原图。
- **FR-005**: MUST 用青色绘制有效尺寸7线/端点，用绿色绘制有效Phi圆。
- **FR-006**: MUST 在顶部显示图片名、group、registration、7/Phi状态与失败原因，并在有效时
  显示`lengthPx/diameterPx`。
- **FR-007**: MUST 为没有有效预测的记录保存红色失败预览。
- **FR-008**: MUST 生成LabelMe兼容JSON，原始图尺寸和预测坐标不得按预览缩放。
- **FR-009**: LabelMe shape MUST 仅为`prediction:7`和`prediction:Phi12.2`，并声明非真值、非
  完整轮廓。
- **FR-010**: MUST 输出`summary.json`、`summary.txt`、`index.csv`。
- **FR-011**: MUST 对每个输入group分别统计total、executionSuccess/error、registrationValid/
  invalid、7 valid/invalid、Phi valid/invalid、bothMeasurementsValid、失败原因和生成数量。
- **FR-012**: MUST NOT 将normal与defective合并成验收统计。
- **FR-013**: MUST 提供默认20的`--images-per-product`，但结果字段必须命名
  `captureGroupEstimate`并包含免责声明、complete/incomplete/gaps。
- **FR-014**: MUST NOT 把`total/images-per-product`描述成物理零件数。
- **FR-015**: MUST 强制输出目录位于Git工作树外，不提交原图、JSONL、JPEG、prediction JSON
  或运行目录。
- **FR-016**: MUST NOT 读取目标真值、做mm换算、输出生产OK/NG或修改孔2运行时算法、配置、
  Schema和现有质量门。
- **FR-017**: MUST NOT 包含任何f10标定常数、规格上下限或孔1定位逻辑。

## Edge cases

- executionError存在且result为空时仍须输出红色预览、prediction JSON和计数。
- registration有效但单个特征无效时，仅绘制有效特征并分别记录失败原因。
- 同名文件可存在于不同group；记录身份使用`group + 文件名`，图片解析必须唯一。
- 尾号缺失、重复或序列空洞不能伪装为complete，必须在`captureGroupEstimate`中显式记录。
- `--only-invalid`和`--frame`只影响生成资产/index；group质量统计仍覆盖完整输入JSONL，并单独
  记录实际生成数量。

## Success criteria

- **SC-001**: 默认、only-invalid、frame、原坐标LabelMe、JPEG缩放、分组计数、序列缺口和
  工作树拒绝均有自动化测试。
- **SC-002**: 服务器9帧外置样本可生成9份预览和9份prediction JSON，人工查看颜色、位置和
  顶部文字正确。
- **SC-003**: 全套unittest、compileall、`git diff --check`和大文件审计通过。
- **SC-004**: Git提交只包含013文档、工具源码和测试，不包含参考包或生成资产。
