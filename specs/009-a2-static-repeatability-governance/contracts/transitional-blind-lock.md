# Transitional Blind Lock Contract v1

- 选择输入只允许confirmed grouped Manifest；不得传入或读取results。
- 候选按完整sample聚合，排序键为固定版本盐与排序后source SHA集合的SHA-256。
- 选中sample的所有condition和全部图像进入blind Manifest；不允许按condition拆分。
- 锁文件必须声明`NON_STRICT_TRANSITIONAL`、`priorExposure=true`、`maxExecutionCount=1`。
- 已存在锁内容不同、源Manifest变化或sample泄漏时拒绝覆盖。
- 一次性执行在启动检测前以独占创建写入`execution-claim.json`；中途失败也消耗唯一执行次数，不得删除claim后重跑。
