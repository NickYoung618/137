# Quickstart: A端面槽姿态MVP验证

项目根目录：`/home/ubuntu/disk/dzk/槽姿态引导算法`

## 1. 安装固定依赖并运行测试

```bash
cd '/home/ubuntu/disk/dzk/槽姿态引导算法'
uv sync
uv run python -m unittest discover -s tests -v
```

预期：Manifest、契约、视觉、CLI和评估测试全部通过。

## 2. 生成小型合成扫角数据

```bash
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir /tmp/slot-pose-synthetic \
  --angles=-170,-90,-30,0,30,90,170 \
  --repeats 3 \
  --seed 137
```

预期：只在`/tmp`生成小PNG、`ground_truth.csv`和显式测试配置，不生成或复制生产大图。

## 3. 单图检测

```bash
uv run python algorithms/slot_pose/main.py \
  --image /tmp/slot-pose-synthetic/synthetic/sample_synthetic/angle_pos_030p00/repeat_001.png \
  --config /tmp/slot-pose-synthetic/synthetic-config.json \
  --task-id synthetic-smoke \
  --out /tmp/slot-pose-synthetic/result.json \
  --strict
```

预期：适配器通过哈希加载历史A端面核心；`valid=true`且角度接近`+30°`，输出绑定图像、配置和
历史资产指纹。

## 4. 默认配置安全失败

```bash
uv run python algorithms/slot_pose/main.py \
  --image /home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/reference.bmp \
  --config config/inspection.example.json \
  --task-id reference-fail-closed \
  --out /tmp/slot-pose-reference-result.json
```

预期：命令不崩溃；因现场坐标约定未确认或图像质量/槽定义不满足，结果`valid=false`且正式角度为空。

## 5. Manifest验证

```bash
uv run python tools/make_manifest.py \
  --input /tmp/slot-pose-synthetic/synthetic \
  --output /tmp/slot-pose-synthetic/manifest.json \
  --dataset-id slot-pose-synthetic-smoke \
  --task slot_pose \
  --expected-repeats 3

uv run python tools/validate_dataset.py \
  --manifest /tmp/slot-pose-synthetic/manifest.json \
  --data-root /tmp/slot-pose-synthetic/synthetic \
  --config /tmp/slot-pose-synthetic/synthetic-config.json \
  --report /tmp/slot-pose-synthetic/validation.json
```

预期：全部小图哈希与分组验证通过。

## 6. Mac侧后续正式验证

Mac路径`/Users/daizekai/Desktop/壳体项目/A2.rar`未同步到服务器。代码同步回Mac后，在外置目录
解压或实现受控流式读取；先生成Manifest和标注，再运行批处理与`tools/evaluate_slot_pose.py`。
生产角度、重复性和PLC结论必须等待B-001至B-005关闭。
