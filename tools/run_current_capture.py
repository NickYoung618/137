#!/usr/bin/env python3
"""Run hole-2 detection from the sole authoritative manual reference."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.hole_2.current_capture import run_current_capture, write_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-annotation", required=True,
                        help="Frozen authoritative manual 7/Phi12.2 annotation.")
    parser.add_argument("--reference-image", required=True,
                        help="New image paired with the authoritative annotation.")
    parser.add_argument("--target-image", required=True, help="Current target image; no target annotation is accepted.")
    parser.add_argument("--config", required=True, help="Versioned current-capture registration config.")
    parser.add_argument("--out", required=True, help="External JSON result path.")
    args = parser.parse_args()

    result = run_current_capture(
        Path(args.reference_annotation),
        Path(args.reference_image),
        Path(args.target_image), Path(args.config),
    )
    write_result(Path(args.out), result)
    registration = result["registration"]
    print(
        f"qualityState={result['qualityStatus']['state']} "
        f"registrationValid={registration['registrationValid']} "
        f"orientation={None if registration['selected'] is None else registration['selected']['orientationDeg']} "
        f"7={result['features']['7']['measurementValid']} "
        f"Phi12.2={result['features']['Phi12.2']['measurementValid']} "
        f"templateSelfCheck={result['authoritativeReference']['templateSelfCheck']} "
        f"totalMs={result['timingMs']['total']:.2f}"
    )
    if result["qualityStatus"]["failureReasons"]:
        print("failureReasons=" + ";".join(result["qualityStatus"]["failureReasons"]))
    print(f"result -> {args.out}")
    return 0 if result["qualityStatus"]["technicalValid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
