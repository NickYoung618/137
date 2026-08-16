# Data Model: D7边缘层证据

## PairedTransitionSample

- `tangentCoordinatePx`: 扫描剖面沿边界切向的位置。
- `outerTransitionPx` / `innerTransitionPx`: 相反极性原始过渡。
- `contourMidpointPx`: 两过渡的物理轮廓中点。
- `pairWidthPx` / `outerPeak` / `innerPeak`: 审计证据。

## RobustLayerFit

- `attempted`: 是否因初始方向/残差失败而尝试。
- `used`: 是否稳健层拟合最终通过原门。
- `initialFailureStage`: 触发稳健拟合的初始失败阶段。
- `rawPointCount` / `inlierPointCount`: 原始成对中点与原残差门内支持数。
- `lineEquation` / `medianResidualPx` / `axisCosine`: 最终拟合及原质量门证据。

## State transitions

```text
paired samples insufficient -> invalid
initial paired fit passes all original gates -> primary valid (unchanged)
initial paired fit direction/residual fails
  -> robust paired-layer fit
     -> original gates all pass -> paired-layer recovery valid
     -> otherwise -> invalid
```

单梯度multiband不再拥有直接到`measurementValid=true`的状态转换。
