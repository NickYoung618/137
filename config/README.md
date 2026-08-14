# 配置约定

单图 CLI 接收标注、待测图、输出路径、`pixel-size` 和版本化定位质量策略。
`inspection.example.json` 仅记录部署时应受控的运行字段示例；`end_face_quality.example.json` 是
默认的 `a-end-face-quality-policy/1`。

- `core_source_sha256` 必须与仓库内原样复用核心一致。
- `annotation_path`、参考图和待测图必须位于 Git 仓库外。
- `pixel_size=1.0` 表示只输出像素量；物理标定确认前不得把它解释为毫米。
- 本仓库不保存视觉引导、PLC 地址或机械坐标映射配置。
- `requiredFiniteMetrics` 固定要求中心、尺度和旋转为有限值。
- `scaleRange`、`centerMarginPx` 和 `allowedMethodPrefixes` 只判断端面定位，不修改核心测量结果。
- `orientationEvidence` 要求 polar rotation score 或 notch prominence 至少一项过门限；默认分别为 3 和 12。
- `requiredFeatureLabels` 默认为空；只有经现场评审确认的定位必要特征才可加入。
- 46 的 NCC `0.55`、中间环模板 `0.35`、径向点数/残差和短线峰值规则属于核心固定条件，
  由核心 SHA-256 约束，不在策略中覆盖。

孔2运行配置以 `hole2_inspection.example.json` 为模板复制到外部工作目录，现场值不得直接覆盖模板。

- `calibration.mm_per_px`：毫米/参考像素，必须来自受控标定；为 `null` 时重复性工具只输出像素。
- `feature_mappings`：把算法CSV列映射到稳定业务特征。Φ12.2直接使用
  `Phi12_2_diameter_px`；`Phi12_2_r`作为可追溯的拟合半径保留。
- `tolerance.confirmed=false`：表示不得用于正式OK/NG。
- `repeatability.tiers`：需求中的0.10、0.05、0.03 mm档；当前模板暂以极差评估，口径待确认。
- `current_capture_registration.v1.json` 中 `Φ12.2` 主半径下限固定为 `0.88`；只有主候选在下界饱和时才以 `recovery_min_radius_scale_ratio=0.84` 执行一次恢复搜索。
