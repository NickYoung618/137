#!/usr/bin/env python3
"""Dormant compatibility CLI for a superseded wall-contamination request.

Definitive human clarification A states that both detected groove-wall lines are
correct and clean.  Only non-groove candidate marks overlap incompletely marked
fixture-shadow regions.  The former request for HUMAN wall-overlap subsegments
must therefore never produce new annotation artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence


DORMANT_MESSAGE = (
    "fixture-contamination annotation is DORMANT/INAPPLICABLE after definitive "
    "human clarification A: groove walls are clean; only non-groove candidate "
    "marks overlap incompletely marked fixture-shadow regions"
)


def prepare_fixture_contamination_annotation(
    review_index_path: Path,
    image_ids: list[str],
    output_dir: Path,
    *,
    same_real_square_groove: str,
    fully_visible_unoccluded: str,
    endpoints_on_outer_shoulders: str,
    fixture_shadow_overlap: str,
) -> dict[str, Any]:
    """Reject the superseded request before reading input or writing output."""

    del (
        review_index_path,
        image_ids,
        output_dir,
        same_real_square_groove,
        fully_visible_unoccluded,
        endpoints_on_outer_shoulders,
        fixture_shadow_overlap,
    )
    raise ValueError(DORMANT_MESSAGE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "This command is retained only to reject superseded invocations. "
            "It never reads the review bundle or creates output."
        ),
    )
    parser.add_argument("--review-index", required=True, type=Path)
    parser.add_argument("--image-id", action="append", required=True)
    parser.add_argument(
        "--same-real-square-groove",
        required=True,
        choices=("YES", "NO", "UNSURE"),
    )
    parser.add_argument(
        "--fully-visible-unoccluded",
        required=True,
        choices=("YES", "NO", "UNSURE"),
    )
    parser.add_argument(
        "--endpoints-on-outer-shoulders",
        required=True,
        choices=("YES", "NO", "UNSURE"),
    )
    parser.add_argument(
        "--fixture-shadow-overlap",
        required=True,
        choices=("NONE", "PARTIAL", "ENTIRE", "UNKNOWN"),
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        prepare_fixture_contamination_annotation(
            args.review_index,
            args.image_id,
            args.output_dir,
            same_real_square_groove=args.same_real_square_groove,
            fully_visible_unoccluded=args.fully_visible_unoccluded,
            endpoints_on_outer_shoulders=args.endpoints_on_outer_shoulders,
            fixture_shadow_overlap=args.fixture_shadow_overlap,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("dormant fixture-contamination command unexpectedly continued")


if __name__ == "__main__":
    raise SystemExit(main())
