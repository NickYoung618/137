# Evidence: A2 多组静态重复性与过渡盲测治理

## Baseline

- 分支基线：`008-a2-replay-integrity-hardening@bff21fa`；工作树干净。
- 修改前完整回归：156 tests，58.516 s，全部通过。
- 远程核对：槽姿态与孔2/端面提交均从`4b8c9be`后独立发展；集成策略为正常merge两边历史，禁止force push。
- 锁定700条源Manifest SHA-256：`fedaca10d4520b65eca3d749bdcbeb630ef824e5cecdde4735408eaeeeca3fce`。
- 锁定700条results JSONL SHA-256：`a2fc511760afade674db518fe0e8af27d64adc757a93183c0ad0fccf31f4179e`。

## TDD and Contracts

- 首次聚焦运行因`tools.evaluation_governance`不存在产生2个ImportError，确认测试先红。
- 实现后009聚焦与008审计回归：23 tests，全部通过（含confirmed segments展开、覆盖与重叠拒绝）。
- 收尾审阅新增2个TDD用例：首次运行分别因“capture sequence缺口未拒绝”和“中断运行未预占次数”失败；
  实现后聚焦回归2/2与总聚焦23/23通过。
- 新增4个Schema；实现前全仓库13个Schema，当前功能分支共17个，Draft 2020-12自检全部通过。
- 修改核心算法文件数：0。新增/修改均限离线治理、CLI、Schema、测试和文档。

## Locked 700-record JSON-only Dry-run

外置产物目录标签：`a2-static-repeatability-009-20260816-v2`。该dry-run读取已有Manifest/results JSONL和用户确认的分组语义，不读取BMP、不运行检测、不依据结果选择分组。

### Input and preparation

- canonical inventory：700；normal 500；bad 200；700个源SHA唯一。
- inventory CSV SHA-256：`37e1b15ca463c0965929f30192f49e718c7a881543f2cf8b99ff8fd35deab212`。
- confirmed grouping CSV SHA-256：`8608abb0cb4e30403ec1baa65a9250e278f244f771d8a8f5876ea953ce098605`。
- 人工confirmed segments（36行数据段）SHA-256：`4dbb8ef38cfc37d7ad50a4b930aa4d181db7c323d5853b73768647af0a9e6463`。
- 由segments工具展开的700行grouping SHA-256：`4bf6f343fa5f2ae225beff012a8a221790ba5b62f442f296f650e0a59b587560`；
  展开过程未接收或读取算法results。
- prepared Manifest文件SHA-256：`0ba304db245b846a324f12716b0688866b344025956e9ec72da68bc8397a7e2c`。
- eligibility文件SHA-256：`54f5c63ddffed4fc9215e271f753bb4218ec4002f53ce8b81a8a24d47b2b68af`。
- prepare wall约0.15 s，峰值RSS约34 MiB，imagesRead=false。
- 使用segments重复dry-run后，资格文件SHA仍为
  `54f5c63ddffed4fc9215e271f753bb4218ec4002f53ce8b81a8a24d47b2b68af`，组数、排除原因、静态统计和选中sample均不变。

### Group eligibility

- condition总数36；采集资格合格24；排除12；总帧数700，零删除。
- normal 1–480形成24个20帧合格组。
- `normal:part-025/pre-rotation-481-498`：18帧，`FRAME_COUNT_LT_20`。
- `normal:part-025/post-rotation-499-500`：2帧，`FRAME_COUNT_LT_20`。
- 10个bad 20帧组：`BAD_SEMANTICS_UNCONFIRMED`；没有把目录名转成权威poseUsable。
- normal/bad跨目录物理样品关系未确认，dry-run使用class-qualified sample ID。

### Static multi-group result

- 权威采集组24、480帧；检测有效353，失败127，有效率73.5417%。
- 组内中心化角残差：n=353，range 0.017087°，sample std 0.001609°，P95绝对残差0.003336°。
- 单组角极差最差：`normal:part-002/fixed-pose`，0.017087°。
- 最低有效率组：`normal:part-009/fixed-pose`，0/20；失败帧保留在分母且角/几何为null。
- 引导组：顺时针10，逆时针8，混合/不可用6，目标附近0；三类覆盖=`BLOCKED`，缺`TARGET_NEAR`。
- 静态报告文件SHA-256：`737b1daf41de0517afe52d597595f4ca94cab392aeac8a67d2f80df42c637b2b`。
- 这些是已查看回放的重复性/有效率诊断，不是角度accuracy或泛化结论。

### Transitional blind lock

- 选择算法：`minimum_sha256_of_sorted_sample_source_hashes` v1；固定盐`a2-transitional-blind-v1`；不接受results参数。
- 候选：24个完整且语义合格normal sample；确定性选中`normal:part-006/fixed-pose`，20张。
- 状态：`NON_STRICT_TRANSITIONAL`、`priorExposure=true`、`strictUnseenClaimed=false`、最多执行1次。
- blind canonical SHA：`fb0de4f6fa0118ff6405fb34f35d315a537442344fbb7571fd4ea2ad1c83a0e3`。
- development canonical SHA：`db46507fdc8d6d5fd431b8439a70d8a79585b9cce052cc79cfe50c2414b29597`；680张，与20张blind交集为0。
- lock payload SHA：`1e434c980fc51acc3b7e6af88042f977e2dd49d5f67e6974548b756c1e9c13df`。
- 锁文件SHA-256：`ec544e1d57cf81cddff17ba296f230f3153aa4d1a43aa77e13f5534fc33cf59a`。
- 本轮只冻结，没有执行该20图Manifest；未来release candidate通过一次性CLI运行。

## Validation before remote integration

- 最新完整回归：175 tests，55.308 s，全部通过。
- 17个JSON Schema Draft 2020-12自检通过；3个真实dry-run payload通过对应Schema。
- `py_compile`、`git diff --check`通过。
- Git差异不含图片、视频、压缩包、私有CSV、外置报告或现场绝对路径。

## Remaining BLOCKED

- badReason/poseUsable及质量authority/provenance。
- normal与bad跨目录物理零件映射。
- 目标85°附近的至少一个合格20帧静态组。
- 新采、物理隔离、此前未查看的正式validation/test零件。
- 质量负责人确认重复性与有效率PASS/FAIL门限；PLC映射继续阻塞。
