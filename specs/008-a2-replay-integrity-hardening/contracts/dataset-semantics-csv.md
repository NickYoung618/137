# Dataset Semantics CSV Contract v1

UTF-8 CSV，逐图键控，不与采集分组绑定。

```csv
relative_path,dataset_class,product_disposition,image_disposition,pose_usable,authority,provenance
normal/frame_001.bmp,normal,UNKNOWN,USABLE,,,
bad/frame_002.bmp,bad,FAIL,USABLE,false,quality_owner,review-20260815
```

规则：

- `relative_path`必须安全、规范、唯一，且精确匹配输入根下图像。
- 传入CSV时必须覆盖全部图像，不得出现多余路径。
- `dataset_class`仅为`normal|bad`。
- disposition仅为列出的枚举；`pose_usable`为空表示未知，否则仅`true|false`。
- `pose_usable`非空时authority和provenance必填，且provenance不得声明来自当前算法输出。
- 与grouping CSV的同名dataset class冲突时拒绝。
