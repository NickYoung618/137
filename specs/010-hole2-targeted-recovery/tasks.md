# Tasks: 孔2批量诊断与定向恢复

## Phase 1 - 纯诊断交付

- [x] T001 复现9帧基线并记录具体失败维度（FR-001–FR-004）
- [x] T002 为注册候选/支持增加逐门值和 x/y 边界诊断（FR-001/FR-002）
- [x] T003 为 `Φ12.2` 增加半径/中心边界、极性和角覆盖（FR-003）
- [x] T004 为尺寸7 p1/p2 增加扫描条带与失败阶段诊断（FR-004）
- [x] T005 实现显式分组的连续失败/重复性/几何离群离线工具（FR-005/FR-006）
- [x] T006 实现 Mac 全量脚本、日志/退出码/关键统计与脚本测试（FR-007）
- [x] T007 验证诊断增量零判定变化，commit/push main（SC-002）

## Phase 2 - 注册恢复

- [x] T008 先增加 `no_valid_candidate` 触发与 ambiguous 禁止恢复测试（FR-008/FR-009）
- [x] T009 实现中心圆/壳体轮廓/侧耳多支持局部窗条件恢复（FR-008/FR-009）
- [x] T010 验证501/520与500/521后 commit/push main（SC-001/SC-003）

## Phase 3 - `Φ12.2` 恢复

- [x] T011 先增加饱和维度分支和失败保护测试（FR-010/FR-011）
- [x] T012 实现中心重定位与有极性/角覆盖/RANSAC残差多圆候选（FR-010/FR-011）
- [x] T013 验证623/1830/620后 commit/push main（SC-001/SC-003）

## Phase 4 - 尺寸7多带

- [x] T014 先增加单带污渍、跨带不一致和质量回退测试（FR-012/FR-013）
- [x] T015 实现多平行带候选和稳健聚合（FR-012/FR-013）
- [x] T016 验证621/641/1830/620后 commit/push main（SC-001/SC-003）

## Phase 5 - 一致性与最终门禁

- [x] T017 实现基于旧参考几何的排序/诊断/拒绝（FR-014/FR-015）
- [x] T018 运行9帧旧/新对照和外置单图精度（FR-016/FR-017）
- [x] T019 运行 unittest、compileall、Schema、SpecKit analyze、Git资产门禁（FR-018/SC-004）
- [x] T020 提交推送并给出 Mac 2200 张复跑命令（SC-005）

## Phase 6 - 可变点数圆验收与 LabelMe 补圆

- [x] T021 删除验收和规范中的固定77点契约，改为至少8个有限点和现有圆残差门（FR-019/SC-006）
- [x] T022 先增加可变点数、少于8点、非圆折线、覆盖不足与闭合标记测试（FR-019–FR-023/SC-006–SC-007）
- [x] T023 复用现有拟圆实现确定性 LabelMe 部分圆弧补全 CLI 与配置/报告契约（FR-020–FR-024）
- [x] T024 外置实跑55点圆弧，保留两轴、删除遮挡多边形并生成补全JSON/报告/预览（FR-024–FR-025/SC-007–SC-008）
- [x] T025 更新 README/quickstart/脱敏证据并执行完整测试、Schema、diff和污染门（FR-025）
- [x] T026 本地提交且不 push、不修改 PLC/上位机（FR-025）

## Final verification evidence

- `uv run python -m unittest discover -s tests -v`: 100 tests passed, 7 skipped;
  SHA-locked hole-2 real E2E included and passed.
- `uv run python -m compileall -q algorithms config scripts specs tests tools`: passed.
- `bash -n scripts/run_hole2_full_regression.sh`: passed; system `shellcheck` unavailable.
- External confirmed image: d7 length absolute error `1.5631 px`; `Φ12.2` diameter
  absolute error `0.1372 px`.
- External nine-frame result: registration `9/9`, d7 `5/9`, `Φ12.2` `8/9`,
  technicalComplete `5/9`; 500/521/620 control transforms and measurements unchanged.
- Phase 6 full gate: `uv run python -m unittest discover -s tests -v` passed
  `110` tests with `9` optional-Schema skips; the explicit `jsonschema` gate passed
  `18/18` tests.
- External partial-circle completion: `55` source points, `216.052850°` visible
  coverage and `1.704781/4.695070/5.368897 px` median/P95/max source radial
  residuals; the spacing-derived output contains `91` unique fitted-circle points
  plus one repeated closing point. Completed-point maximum radial residual is below
  `5e-13 px`. These are automated fit diagnostics, not human truth or production
  accuracy.
