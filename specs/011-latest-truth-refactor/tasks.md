# Tasks: 孔2最新唯一真值边缘语义重构

## Phase 1 - SpecKit 与诊断

- [x] T001 核验 clean HEAD、远端祖先关系、全套测试并推送 `96eb8b3`
- [x] T002 冻结最新唯一真值哈希并复现基线
- [x] T003 完成 specify/clarify/research/plan/tasks
- [x] T004 实现外置叠加图、尺寸7成对梯度和 Phi 径向剖面诊断工具
- [x] T005 运行真实诊断、记录具体物理边缘根因并提交推送

## Phase 2 - 检测重构

- [x] T006 先增加尺寸7成对极性、多扫描支持及失败不误恢复测试
- [x] T007 实现尺寸7轮廓中心拟合、质量字段与原 v6 严格回退
- [x] T008 先增加 Phi 极性、参考相位、角覆盖及错误边界拒绝测试
- [x] T009 实现 Phi 参考相位亚像素点、多圆稳健拟合与原门限接线
- [x] T010 最新单图运行时无真值检测并通过 `7<=2 px`、`Phi<=1 px`

## Phase 3 - 交付与门禁

- [x] T011 更新真实 E2E 为最新哈希；旧审核改为非阻断历史报告
- [x] T012 实现无绝对路径单图验收脚本与日志/产物契约测试
- [x] T013 复跑9帧并核验500/521/620无新增失效
- [x] T014 运行 unittest、compileall、Schema、SpecKit analyze 与媒体/大文件审计
- [x] T015 更新 quickstart、标记任务完成、分里程碑 commit/push main
- [x] T016 给出 Mac 2200张复测命令与最终接受门

## Final verification evidence

- `uv run --with jsonschema python -m unittest discover -s tests -v`: `119` tests passed，
  包含 Schema 与 SHA 锁定最新真实 E2E，无 skip。
- `uv run python -m compileall -q algorithms config scripts specs tests tools`: passed。
- `bash -n` 两个回归脚本 passed；系统未安装 `shellcheck`，由脚本契约测试补充。
- 最新单图一键脚本：`PASS`；尺寸7误差 `0.717320 px`，Phi直径误差 `0.105305 px`。
- 9帧：registration `9/9`、尺寸7 `4/9`、Phi `8/9`；500/521/620均完整有效，
  变换与旧版零差。623旧尺寸7疑似错边被显式拒绝。
- `algorithms/hole_2/main.py` 在011增量中的 diff 为0字节；当前 SHA-256 为
  `6406447ef90ac96f6fa3626eb50f0166c871a6d643d6579dbd8c3b473eac847f`。
- Git无大于1MiB跟踪文件，无跟踪图片、压缩包或JSONL；Mac 2200张仍待外置最终验收。
