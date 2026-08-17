#!/usr/bin/env python3
"""Summarize default-off source-consistency adjudication from runtime JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import write_json


def load_jsonl(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: result must be an object")
                records.append(value)
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: Counter[str] = Counter()
    effective: Counter[str] = Counter()
    original: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    guidance: Counter[str] = Counter()
    directions: Counter[str] = Counter()
    valid_count = 0
    plc_non_null_count = 0
    adjudication_count = 0
    for record in records:
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        diagnostics = record.get("diagnostics") if isinstance(record.get("diagnostics"), dict) else {}
        adjudication = diagnostics.get("sidewallSourceConsistencyAdjudication")
        if not isinstance(adjudication, dict):
            refinement = diagnostics.get("grooveRefinement")
            if isinstance(refinement, dict):
                adjudication = refinement.get("sourceConsistencyAdjudication")
        if isinstance(adjudication, dict):
            adjudication_count += 1
            decisions[str(adjudication.get("decision") or "UNKNOWN")] += 1
            effective[str(adjudication.get("effectiveStatus") or "UNKNOWN")] += 1
            original[str(adjudication.get("originalStatus") or "UNKNOWN")] += 1
        error = record.get("error")
        errors[str(error.get("code") if isinstance(error, dict) else "NONE")] += 1
        guidance[str(result.get("guidanceStatus") or "UNKNOWN")] += 1
        directions[str(result.get("rotationDirection") or "NONE")] += 1
        valid_count += result.get("valid") is True
        plc_non_null_count += result.get("plcCommand") is not None
    return {
        "schemaVersion": "source-consistency-adjudication-summary/1",
        "resultCount": len(records),
        "adjudicationCount": adjudication_count,
        "validCount": valid_count,
        "decisionCounts": dict(sorted(decisions.items())),
        "effectiveStatusCounts": dict(sorted(effective.items())),
        "originalStatusCounts": dict(sorted(original.items())),
        "errorCounts": dict(sorted(errors.items())),
        "guidanceStatusCounts": dict(sorted(guidance.items())),
        "rotationDirectionCounts": dict(sorted(directions.items())),
        "plcCommandNonNullCount": plc_non_null_count,
        "manualTruthAppliedAtRuntime": False,
        "authoritative": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = summarize(load_jsonl(args.results))
        if args.output is not None:
            write_json(args.output, payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
