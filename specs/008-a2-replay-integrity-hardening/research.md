# Research: A2 回放验收与根因加固

## Decision 1: 最终结果是唯一动作权威

**Decision**: 汇总、CSV和overlay优先读取顶层v3 `result`；中间 `singleGroovePose.guidance` 独立命名为 pre-quality/intermediate guidance。

**Rationale**: 700条中20个 `QUALITY_REJECTED` 的中间几何为到位，但顶层已正确fail-closed。当前review读取中间对象导致2被报成22。

**Alternatives considered**: 删除中间角会损失诊断；让质量拒绝仍输出角会破坏安全契约。均拒绝。

## Decision 2: 坏目录不是姿态负标签

**Decision**: `datasetClass`、产品质量、图像质量、`poseUsable`分字段；只有带authority/provenance的 `poseUsable=false` 才产生权威姿态误引导指标。

**Rationale**: Manifest把700条全标normal；联系表中的多张坏图仍有清晰圆和实体槽。目录名不能说明是否允许姿态引导。

**Alternatives considered**: 硬编码`坏`路径、将产品NG全部当姿态NG、从当前算法valid反推poseUsable。都会制造标签泄漏或错误业务语义。

## Decision 3: 每图语义CSV独立于采集分组

**Decision**: 使用按 `relative_path` 键控的外置CSV；提供dataset class、三类disposition、pose usability、authority和provenance。若传入则必须覆盖每个Manifest图像且无重复/冲突。

**Rationale**: 现有grouping CSV可携带class但会把业务语义和重复性分组耦合；本批没有权威20帧分组。

**Alternatives considered**: 前缀规则虽省行数但可能把组内例外覆盖；它可作为CSV生成前的人工辅助，不进入Manifest核心契约。

## Decision 4: 源配置与有效配置双身份

**Decision**: 保留源字节哈希；新增canonical effective hash。有效视图包含展开的pose/detector和资产哈希，不包含config id、格式、机器路径。

**Rationale**: Mac/server源配置路径必然不同，省略默认与显式默认也会产生不同文件哈希，但算法行为可能完全相同。

**Alternatives considered**: 只记录源哈希无法比较行为；把路径纳入有效哈希破坏跨机一致；移除源哈希损失审计链。

## Decision 5: Schema允许省略可默认项

**Decision**: conditional required不再要求可由loader完整补齐的 `physical_outer_circle`/`groove_recognition`；materialized输出必须包含并通过Schema。

**Rationale**: 现状loader明确支持缺省并有严格值校验，Schema却拒绝同一输入。非破坏修复应对齐既有兼容行为。

**Alternatives considered**: 强制所有旧配置补字段会造成不必要兼容破坏；完全不做Schema验证会失去合同门。

## Decision 6: 多候选只按物理精修唯一化

**Decision**: opt-in resolver对最多3个已通过粗槽门的候选逐一调用现有sidewall+circle-intersection refiner。恰好1个成功才继续；0、多个、超限失败。

**Rationale**: 接受集上分数差不可证明真槽，85°也不能用于选槽。物理精修是现有、独立、可解释证据。

**Alternatives considered**: 最高score、固定candidate-002、固定角区、跨帧运动、目标角最近者均会泄漏现场/目标信息；训练模型缺少标签且超出范围。

## Decision 7: 默认关闭真实多候选恢复

**Decision**: 能力实现并合成验证，但默认disabled；需独立真槽/阴影标注集验证后显式开启。

**Rationale**: 当前700条只有结果与缩略图，没有候选级人工真值。结构正确不等于生产泛化已证实。

**Alternatives considered**: 默认开启会改变41张真实歧义结果而无权威验证；完全不实现则无法验证安全恢复路线。

## Decision 8: 圆和粗槽阈值不在008修改

**Decision**: audit报告原始值、按pixel scale换算的有效门和margin；生成标注队列，不自动推荐/写回阈值。

**Rationale**: 27稀疏圆和20最终圆多为残差边界失败，但没有外圆真值；60槽失败也没有真槽标注。

**Alternatives considered**: 直接放宽会把acceptance当tuning；使用85°或成功组角度反标会泄漏目标。

## Decision 9: 自适应联系表布局

**Decision**: 由图数、tile高度和JPEG最大安全高度推导最少列数，700图至少5列；输出前验证宽高。

**Rationale**: 固定3列时700图高约100,620px，超过JPEG实现限制；5列为60,200px。

**Alternatives considered**: 丢弃部分图违反全量审阅；分页可作为未来扩展，但会改变现有单文件工作流。

## Decision 10: 性能口径

**Decision**: JSON审计报告总wall/记录数/峰值RSS；检测耗时继续区分只有`elapsedMs`的记录与batch wall，不以缺失47条的分位数冒充全700端到端。

**Rationale**: 当前P50/P95仅有653个内部elapsed样本。

**Alternatives considered**: 给缺失记录填0会污染分位数；重新检测700图本轮无原图且无必要。
