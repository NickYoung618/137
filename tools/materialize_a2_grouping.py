#!/usr/bin/env python3
"""Expand compact human-confirmed capture segments into per-image A2 grouping."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.evaluation_governance import expand_confirmed_segments, read_csv


FIELDS = ["relative_path", "source_image_sha256", "sample_id", "condition_id", "repeat_index", "split", "dataset_class", "grouping_authority", "grouping_provenance"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--segments", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = expand_confirmed_segments(read_csv(args.inventory), read_csv(args.segments))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader(); writer.writerows(rows)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Materialized confirmed grouping: images={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
