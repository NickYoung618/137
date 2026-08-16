# Quickstart: 复核D7 v6回退首版决策

本流程只读取仓库外JSONL，不运行目标真值驱动检测，也不写入仓库。

```bash
cd '/path/to/137壳体检测-孔2柱面和端面检测'
export HOLE2_010_030_JSONL='/path/to/current-capture-results.jsonl'

python3 - "$HOLE2_010_030_JSONL" <<'PY'
import collections, json, pathlib, sys

rows = [json.loads(line) for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if line.strip()]
for group in ("normal-group-010", "normal-group-030"):
    features = [row["result"]["features"]["7"] for row in rows if row["group"] == group]
    print(group, "total", len(features))
    print("measurementValid", sum(bool(item["measurementValid"]) for item in features))
    print("evidenceComplete", sum(bool(item["evidenceComplete"]) for item in features))
    print("sourceDetector", collections.Counter(item["sourceDetector"] for item in features))
    print("recoveryPass", collections.Counter(str(item["recoveryPass"]) for item in features))
PY
```

定向安全契约：

```bash
uv run --with jsonschema python -m unittest \
  tests.test_current_capture_contract.CurrentCaptureContractTests.test_measurement_validity_is_independent_from_evidence_completeness \
  tests.test_current_capture_registration.CurrentCaptureRegistrationTests.test_d7_fallback_requires_original_v6_quality_gate
```

预期解释：010为20个measurement-valid、0个evidence-complete；这不是20个精度PASS，也不是20个生产OK。
