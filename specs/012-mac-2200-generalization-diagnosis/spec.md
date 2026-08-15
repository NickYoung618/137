# Feature Specification: Mac 2200 泛化退化诊断

**Feature Branch**: `main`

**Created**: 2026-08-15

**Status**: Directed implementation complete; pending Mac 2200 acceptance

**Input**: Mac 对 `79aa6a4` 与 `3ee4b4f` 的外置 2200 张逐图差异和批量质量汇总。

## Scope and cohort boundary

- `normal` 是唯一检测率验收组，共 2000 张好样品。
- `defective` 是独立观察组，共 200 张坏品；其有效数不得合并到 normal，也不得用于证明
  好样品检测率改善。
- 诊断提交完成并获得明确实施授权后，本增量只实现分数契约分离与geometry多证据决策；
  不修改配置门限，不放宽legacy `0.35`或比例偏差`0.08`。
- 外置 JSON、图片、JSONL 和批量输出不进入 Git。

## Frozen evidence

外置证据目录：`/home/ubuntu/disk/dzk/hole2-mac-2200-diagnostic-20260815/`。

| Evidence | SHA-256 |
|---|---|
| `mac-2200-delta-diagnostic.json` | `b241c09642173507266d50b23a85c9ed093eb325b6b937ea6e726c734173f352` |
| `baseline-79aa6a4-quality-summary.json` | `94c6aeb96a3c295cd5d7444a17f4e42649b115411930b4ec35c6793117cdf6ce` |
| `candidate-3ee4b4f-quality-summary.json` | `7cd07b436f45959650f294b9b3cea9d9bb84548a9c81a055c6e4c7444a62e4e5` |

三份证据均记录运行时未读取目标真值，两个版本均无执行错误。

## User Scenarios & Testing

### User Story 1 - 正常组退化可归因（Priority: P1）

算法工程师可以只用 normal 2000 张证据，解释注册提升但尺寸7和 `Phi12.2` 检测率下降的
直接原因，并把自身检测失败与上游/组合门耦合分开。

**Independent Test**: 从两个 summary 和 delta 的 normal 节点重新计算 valid、lost、gained 和
lostReasons，结果与本规格冻结数字逐项相等。

**Acceptance Scenarios**:

1. **Given** normal 2000 张，**When** 对比两个版本，**Then** registration 为
   `1962→1985`、尺寸7为 `1863→1772`、Phi为 `1922→1826`。
2. **Given** 尺寸7的136张 lost，**When** 按最终失败原因分解，**Then** 105张来自Phi上游、
   30张来自geometry硬拒绝、仅1张来自自身切线拟合。

---

### User Story 2 - 相位分数语义审计（Priority: P1）

算法工程师可以判断 reference-phase 分数和 legacy magnitude 分数是否同义，并在没有全局降低
门限的情况下提出可测试的定向修复。

**Independent Test**: 代码路径与105张 normal lost 的质量分布共同证明：相位候选的有符号
一维梯度统计被继续拿去与 legacy 二维梯度幅值的 `0.35` 门比较。

**Acceptance Scenarios**:

1. **Given** 105张旧版Phi有效且新版仅报 `edge_peak_below_gate` 的 normal 图，**When** 检查
   新版相位质量，**Then** 残差、点数、极性支持和角覆盖分布必须完整记录。
2. **Given** 两种分数统计定义不同，**When** 形成修复候选，**Then** 不得以全局降低
   `min_edge_peak_normalized` 作为结论。

---

### User Story 3 - 几何比例语义审计（Priority: P1）

算法工程师可以区分“比例离群诊断”和“有证据的错边拒绝”，避免把没有逐图真值的离群直接
当成已证明错误。

**Independent Test**: 比较 `79aa6a4`、`526c080` 和 `3ee4b4f` 的代码历史，并核验36张
normal geometry rejected 的分布和30张旧有效转失效。

**Acceptance Scenarios**:

1. **Given** `79aa6a4` 基线，**When** 检查运行时结果与源码，**Then** 该版本没有
   `geometryConsistency` 运行时门。
2. **Given** 当前 `3ee4b4f`，**When** deviation 超过 `0.08`，**Then** 两个特征都会被清空并
   标为 `geometry_ratio_inconsistent`；文档必须指出该硬拒绝最早在 `526c080` 引入。
3. **Given** 36张图没有逐图目标标注，**When** 解释离群，**Then** 只能称为“未经标注证实的
   比例离群”，不能称为已证明错边。

---

### User Story 4 - 下一轮修复与复测可判定（Priority: P2）

负责人可以在开始改代码前审阅定向修复候选、测试矩阵、风险和Mac验收门，并明确决定是否
进入实现。

**Independent Test**: 每个根因至少有一个不依赖目标真值运行时输入的修复候选、失败保护测试
和Mac normal验收条件。

**Acceptance Scenarios**:

1. **Given** 本轮诊断完成，**When** 未收到继续实现授权，**Then** 仓库运行时代码、配置和测试
   保持不变。
2. **Given** 后续候选实现，**When** 运行Mac全量复测，**Then** normal 必须满足
   registration `>=1962`、尺寸7 `>=1863`、Phi `>=1922`，比例离群不增加。
3. **Given** defective 200 张输出，**When** 汇报结果，**Then** 必须单列观察，不进入上述门。

## Edge Cases

- 同一帧可能同时发生注册变化、Phi变化和尺寸7变化；归因必须依据逐特征 old→new 状态，不能
  用 overall 总数反推。
- 36张 geometry rejected 中只有30张属于旧有效→新无效；其余6张不能在缺少完整逐图结果时
  擅自归类为检测率 lost。
- 文件名连续后缀只用于描述时间/序号簇，不得据此推断固定20帧样品组；重复组仍须由 manifest
  或显式参数定义。
- `phaseFallback=null` 可以证明未走相位 fallback，但 delta 没有通用 `recoveryPass` 字段时，
  不得臆测其他恢复分支。
- 单图真值通过不能覆盖2000张 normal 泛化退化；反过来，批量检测率恢复也不能牺牲单图精度。

## Functional Requirements

- **FR-001**: MUST 严格以 normal 2000 张作为检测率验收组，defective 200 张只作独立观察。
- **FR-002**: MUST 冻结三份外置证据名称、SHA-256、版本和组别，不提交证据文件本身。
- **FR-003**: MUST 复算并记录 normal/defective 的 valid、lost、gained、原因和执行错误。
- **FR-004**: MUST 验证 phase edge peak 与 legacy magnitude peak 的计算语义和门限接线。
- **FR-005**: MUST NOT 把全局降低 `0.35` 门限作为相位退化的修复结论。
- **FR-006**: MUST 核验 geometryConsistency 的代码历史及其是否改变最终 measurementValid。
- **FR-007**: MUST 将无逐图真值的 geometry outlier 标为未经标注证实，不得宣称已证明错边。
- **FR-008**: MUST 把尺寸7自身检测退化与Phi上游/geometry组合门耦合分别计数。
- **FR-009**: MUST 分析105张相位分数 lost 的连续序号簇、sourceDetector、fallback、半径比、
  残差、点数、极性支持和角覆盖。
- **FR-010**: MUST 明确能区分“正确弱相位边”和“错误边”的多证据组合，不依赖目标标注、
  文件名、哈希、标称尺寸或固定像素补偿。
- **FR-011**: MUST 给出测试先行的定向修复候选；本轮不得实施候选。
- **FR-012**: MUST 保持最新唯一真值单图尺寸7误差 `<=2 px`、Phi直径误差 `<=1 px` 为后续门。
- **FR-013**: MUST 保持 normal 最终门 registration `>=1962`、尺寸7 `>=1863`、Phi `>=1922`，
  且按同一统计定义的比例离群不增加。
- **FR-014**: MUST NOT 让运行时读取目标真值，或硬编码文件名/hash、310、541.13、12.2及固定补偿。
- **FR-015**: MUST NOT 修改本诊断阶段的算法、配置、Schema、契约或测试门。
- **FR-016**: MUST 在纯文档提交后停止，等待明确的实现指令。

## Key Entities

- **Acceptance cohort**: normal 2000 张；唯一参与检测率门的好样品集合。
- **Observation cohort**: defective 200 张；只用于观察失败保护，不参与好样品接受。
- **Status transition**: 同一图片、同一特征的 old/new valid、source、failureReason 和质量字段。
- **Phase evidence bundle**: 相位峰、残差、内点数、极性支持、角覆盖、半径比和候选来源。
- **Geometry consistency report**: 旧参考比例、目标比例、绝对偏差、阈值及是否改变最终有效性。

## Success Criteria

- **SC-001**: normal 与 defective 的汇总在所有文档中严格分开且数字相互一致。
- **SC-002**: A/B/C 三个根因均同时具有批量证据和源码/历史证据。
- **SC-003**: 105张的全部要求维度和连续序号簇有可追溯统计，不把20帧连续段解释成样品组。
- **SC-004**: 修复候选不包含全局门限放宽、真值泄漏、标称值拉回或固定像素补偿。
- **SC-005**: 测试矩阵覆盖强正确、弱但一致、错误极性/低覆盖/高残差、geometry离群和D7上游耦合。
- **SC-006**: 本提交相对 `3ee4b4f` 只新增 `specs/012-mac-2200-generalization-diagnosis/` 文档。

## Assumptions

- `mac-2200-delta-diagnostic.json` 是同一2000 normal与200 defective资产上两个提交的逐图差异。
- 三份证据的 runtimeInputs 显示相同旧参考资产指纹，目标真值未进入运行时。
- 当前只有一张最新人工真值；其余normal图没有逐图标注，因此只能验证检测率和图像质量证据，
  不能直接计算批量像素精度。
