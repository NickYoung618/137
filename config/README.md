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
