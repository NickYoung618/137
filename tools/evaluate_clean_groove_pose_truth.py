#!/usr/bin/env python3
"""Evaluate independent visible-circle arc and clean-groove pose truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.clean_groove_pose_truth_evaluation import build_clean_groove_pose_truth_evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_clean_groove_pose_truth_evaluation(args.validation, args.results, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "ok", **report["summary"], "output": args.output.name}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
