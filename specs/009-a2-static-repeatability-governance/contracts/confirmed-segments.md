# Confirmed Segments CSV Contract v1

一行代表负责人确认的一个连续condition，字段为：

```csv
dataset_class,start_capture_sequence,end_capture_sequence,sample_id,condition_id,split,grouping_authority,grouping_provenance
normal,481,498,normal:part-025,pre-rotation-481-498,unassigned,capture_owner,review-20260816
normal,499,500,normal:part-025,post-rotation-499-500,unassigned,capture_owner,review-20260816
```

- 范围必须按datasetClass内的可靠`capture_sequence`定义，完整覆盖inventory且不能重叠或缺号。
- 同一个物理零件可出现多个condition，但sampleId必须相同。
- 展开后的repeatIndex在每个segment内从1连续生成。
- authority/provenance必须来自采集/现场确认，不得来自算法角度或成败结果。
