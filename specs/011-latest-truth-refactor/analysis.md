# SpecKit Analyze: 孔2最新唯一真值边缘语义重构

**Analyzed**: 2026-08-15

## Cross-artifact consistency

- `spec.md` 的16项功能需求均映射到 `tasks.md` T001–T016。
- `research.md` 的两个根因分别映射到尺寸7成对极性实现和 Phi 参考相位实现；没有采用
  固定像素补偿、标称尺寸或目标真值运行时输入。
- `data-model.md` 的新增质量字段均由 `current_capture.py` 输出；结果继续使用既有版本化
  result contract，新增字段位于开放的 `quality` 对象内。
- `quickstart.md` 区分无真值检测、离线诊断/验收和 Mac 全量回归。
- `tests/test_current_capture_contract.py` 继续证明 runtime contract 不含 target annotation；
  最新真实 E2E 冻结图片和唯一真值哈希。

## Constitution and safety checks

- `algorithms/hole_2/main.py` 在本增量中无 diff；修改位于 current-capture 适配层。
- 目标原图、LabelMe、JSONL、PNG和运行输出均在 Git 工作树外。
- Phi `0.88→0.84` 受控两阶段搜索、注册主门、v6质量回退和几何比例只诊断/拒绝语义保留。
- 错误极性测试显式失败；局部相位兼容回退不降低原门限并记录来源。

## Evidence review

- 最新单图：尺寸7长度误差 `0.717320 px`；Phi直径误差 `0.105305 px`，两项均通过。
- 9帧：注册 `9/9`，Phi `8/9`；尺寸7 `4/9`。500/521/620三张控制帧两特征均有效，
  注册变换相对旧版逐参数零差。623旧尺寸7为 `362.131337 px`，新版因配对轮廓失败显式
  无效，未保留疑似错边。
- 服务器没有2200张；Mac门仍是未完成的外部最终验收，不得把9帧结论外推。

## Findings

未发现阻断提交的规格歧义、需求遗漏、运行时真值泄漏或门限放宽。唯一未闭环项是 Mac
2200张外置最终验收，已有无绝对路径脚本和明确接受门。
