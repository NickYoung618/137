#!/usr/bin/env python3
"""Build default-off single or direction-independent 180deg paired guidance."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from algorithms.slot_pose.half_turn_guidance import run_manifest, validate_config

def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    output = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        payload = json.loads(line); sha = (payload.get("image") or {}).get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or sha in output:
            raise ValueError(f"invalid or duplicate image SHA at line {number}")
        output[sha] = payload
    return output

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--single-results", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        config = json.loads(args.config.read_text(encoding="utf-8")); validate_config(config)
        results = run_manifest(manifest, load_jsonl(args.single_results), config)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) for item in results) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2
    print(f"Wrote {args.output}: requests={len(results)} valid={sum(bool(x['valid']) for x in results)}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
