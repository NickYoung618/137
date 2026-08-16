# Tasks: 孔2单批次可视报告

## Phase 1 - Reference and specification

- [x] T001 确认HEAD=`b641037`、worktree clean和唯一远端
- [x] T002 完整阅读外置1955行脚本并检查f10 LabelMe摘要
- [x] T003 冻结可借鉴/禁止复用边界
- [x] T004 创建013 spec/research/plan/tasks/quickstart/analysis

## Phase 2 - Test first

- [x] T005 默认全量生成、缩放JPEG和原坐标LabelMe红灯测试
- [x] T006 only-invalid与重复frame选择红灯测试
- [x] T007 normal/defective计数隔离与失败原因红灯测试
- [x] T008 captureGroupEstimate complete/incomplete/gaps红灯测试
- [x] T009 Git工作树输出拒绝红灯测试

## Phase 3 - Implementation

- [x] T010 实现外置输入、图片解析和过滤
- [x] T011 实现Pillow缩放预览、状态面板与失败预览
- [x] T012 实现原坐标LabelMe prediction JSON
- [x] T013 实现summary.json/txt、index.csv和group统计
- [x] T014 实现captureGroupEstimate及非物理零件免责声明

## Phase 4 - Verification and delivery

- [x] T015 服务器9帧真实小样并人工看图
- [x] T016 全套unittest、compileall、diff check和大文件审计
- [x] T017 完成SpecKit analyze并核对禁用常数/cv2/运行时零修改
- [x] T018 提交并push origin/main，报告SHA和Mac命令
