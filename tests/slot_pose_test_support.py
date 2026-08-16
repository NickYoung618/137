"""Cross-platform, self-contained legacy assets for slot-pose tests only."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.dataset_common import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]

_MINIMAL_LEGACY_SOURCE = '''\
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
from PIL import Image


def fit_circle(points):
    values = np.asarray(points, dtype=float)
    x = values[:, 0]
    y = values[:, 1]
    matrix = np.column_stack((x, y, np.ones(len(values))))
    target = -(x * x + y * y)
    d, e, f = np.linalg.lstsq(matrix, target, rcond=None)[0]
    center_x = -float(d) / 2.0
    center_y = -float(e) / 2.0
    radius = max(0.0, center_x * center_x + center_y * center_y - float(f)) ** 0.5
    return center_x, center_y, radius


def robust_fit_circle(points, initial):
    return fit_circle(points)


def geometric_circle_fit(points, initial=None):
    return fit_circle(points)


def build_reference_model(annotation_path):
    annotation_path = Path(annotation_path)
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    return SimpleNamespace(reference_path=(annotation_path.parent / payload["imagePath"]).resolve())


def load_detection_gray(path):
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64)


def outer_boundary_edge_point(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def bilinear_sample(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def parabolic_peak(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def object_bbox_center(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def polar_resample(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def find_outer_notch_angle(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def estimate_rotation_by_notch(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def estimate_rotation_by_polar(*args, **kwargs):
    raise NotImplementedError("test fixture only")


def estimate_global_transform(*args, **kwargs):
    raise NotImplementedError("test fixture only")
'''


def write_minimal_legacy_source(root: Path) -> Path:
    """Write a loadable legacy module with only the functions test adapters require."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "minimal_legacy_a_end_face.py"
    source.write_text(_MINIMAL_LEGACY_SOURCE, encoding="utf-8")
    return source


def write_isolated_slot_pose_config(root: Path) -> Path:
    """Create a complete temporary config whose locked assets all live under ``root``."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = write_minimal_legacy_source(root)
    reference = root / "reference.png"
    Image.new("L", (32, 32), 127).save(reference)
    annotation = root / "annotation.json"
    annotation.write_text(
        json.dumps({
            "version": "5.0.1",
            "flags": {},
            "shapes": [],
            "imagePath": reference.name,
            "imageData": None,
            "imageWidth": 32,
            "imageHeight": 32,
        }),
        encoding="utf-8",
    )
    config = json.loads(
        (PROJECT_ROOT / "config" / "inspection.example.json").read_text(encoding="utf-8")
    )
    config["config_id"] = "cross-platform-isolated-test-fixture"
    config["legacy_asset"] = {
        "source_path": str(source),
        "source_sha256": sha256_file(source),
        "annotation_path": str(annotation),
        "annotation_sha256": sha256_file(annotation),
        "reference_path": str(reference),
        "reference_sha256": sha256_file(reference),
    }
    config_path = root / "inspection.test.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return config_path
