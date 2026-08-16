# Evidence: A2 回放验收与根因加固

## 锁定基线

- 基线与分支起点：`main@5c89563168bb0b0e4ef1d5948c914a9708aabd0c`
- 功能分支：`008-a2-replay-integrity-hardening`
- 首次测试入口：系统无 `python` 命令，退出127；这是环境入口缺失，不是测试失败。
- 隔离环境基线：`uv run --with jsonschema python -m unittest discover -s tests -v`，142 tests，41.758 s，全部通过。
- Git跟踪媒体：0；源码树超过5 MiB的文件仅位于被忽略的 `.venv` 依赖目录。

## 外置锁定回放指纹

以下只记录文件内容哈希，不记录现场绝对路径；图片、JSONL、Manifest、联系表均不进入Git。

| 工件 | SHA-256 |
|---|---|
| manifest.json | `fedaca10d4520b65eca3d749bdcbeb630ef824e5cecdde4735408eaeeeca3fce` |
| results.jsonl | `a2fc511760afade674db518fe0e8af27d64adc757a93183c0ad0fccf31f4179e` |
| config-local.json | `61651d48a56d2e059dd5f4677c975ecaedea8280aa09695876cbf6128a5587c5` |
| config-server.json | `cf68aa629bd3e5b860b028edab5a88a590f15ad3b31c34d195ef2ceb0a894582` |

## 数据用途边界

- 当前唯一人工标注样本：仅作开发/几何参考，不构成统计验证集或测试集。
- 700张已检查回放：锁定为 acceptance regression；实现期不重跑图片、不用于阈值选择。
- 独立 validation/test：`NOT_AVAILABLE`，等待新增物理样品、显式样品/工况分组以及复核标注。
- 25张JPEG诊断副本与700张可能同源，不得作为独立 validation。

## 已证实根因（修改前）

- 最终 v3 结果为491 valid、489 needs adjustment、2 in position、209 unavailable；方向271 clockwise、218 counterclockwise、2 none、209 unavailable。
- 旧 review 汇总从中间 `singleGroovePose.guidance` 计数，使20个最终 `QUALITY_REJECTED` 被错误计入 in-position，并把部分早期失败形成另一种状态拼写。
- 旧 Manifest 的700条 `datasetClass` 全为 normal；所谓500/200依赖目录语义恢复，不能作为姿态可用性的权威标签。
- 源配置可被运行时默认值接受，但不能通过当前配置Schema；现有哈希只描述源文件字节，不能直接证明有效运行阈值相同。
- 多粗槽候选在旧单槽路径中未逐个进入同一物理槽壁精修；安全修复必须有上限、只接受唯一精修幸存者并默认关闭。

## BLOCKED

- B01：坏图原因与各原因是否允许姿态引导。
- B02：圆定位失败的独立圆真值。
- B03：真实槽/阴影及槽壁真值。
- B04：静态重复性的物理样品与同条件分组。
- B05：独立、物理样品隔离且经复核的 validation/test 数据。

## 修复后验证

- 完整回归：154 tests，43.127 s，全部通过。
- 聚焦回归：54 tests，9.959 s，全部通过。
- JSON Schema：13个Schema均通过Draft 2020-12自检；两份转移源配置在允许可默认段省略后均通过。
- 两份源配置字节哈希不同，但展开默认后的有效配置哈希相同：
  `e8d51119a25e4a77a14619ef6ee769ac35ac2de5e7f684d3d3cb8cda43a38a6d`。
- 锁定700条只读JSON审计（不读图、不运行检测）：PASSED，审计wall约9.8 ms；报告SHA-256
  `33cb4d18e06a6e6435bf2ee6cad364d66662593aeca61398cffbf7b876284b32`。
- 最终权威状态：491 detected；489 needs adjustment；2 in position；209 unavailable。
- 最终权威方向：271 clockwise；218 counterclockwise；2 none；209 unavailable。
- 最终错误：圆提议/稀疏圆27、物理圆20、真槽失败60、真槽歧义41、槽壁精修41、顶层质量20。
- 旧Manifest的700条evaluation purpose仍全部`unassigned`且语义未显式化；审计因此正确输出
  `poseUsabilityMetric=BLOCKED`、repeatability=`NOT_EVALUATED`、validation/test=`NOT_AVAILABLE`，没有用目录名或唯一标注伪造标签。
- 本功能没有改变圆、真槽或槽壁生产阈值；多粗槽物理解析默认关闭，只由合成/受控测试证明fail-closed语义。
