"""Versioned short-line diagnostics and a core-external image candidate.

The desktop core remains the source of ``coreValid`` and baseline geometry.
This module only reads those values, reconstructs the legacy short-line signal
for diagnosis, and produces an independently gated reference-gradient result.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from algorithms.end_face import core
from algorithms.end_face.main_housing_registration import (
    MainHousingRegistrar,
    RegistrationResult,
    validate_registration_config,
)
from algorithms.end_face.quality import canonical_feature_label


CANDIDATE_CONFIG_SCHEMA_VERSION = "a-end-face-short-line-candidate-config/1"
CANDIDATE_CONFIG_SCHEMA_VERSION_V2 = "a-end-face-short-line-candidate-config/2"
DIAGNOSTIC_VERSION = "short-line-diagnostic/1"
CANDIDATE_SOURCE = "reference-gradient-registration-v1"
CANDIDATE_SOURCE_V2 = "main-housing-registration-v2"
CANDIDATE_SOURCES = {CANDIDATE_SOURCE, CANDIDATE_SOURCE_V2}
SUPPORTED_FEATURES = {"19", "30"}
LABELME_REFERENCE_SCHEMA_VERSION = "a-end-face-labelme-short-line-reference/1"


@dataclass(frozen=True)
class ShortLineTemplateModel:
    label: str
    shape_type: str
    points: tuple[tuple[float, float], tuple[float, float]]


@dataclass
class LabelMeShortLineReference:
    annotation_path: Path
    annotation_sha256: str
    image_path: Path
    image_sha256: str
    width: int
    height: int
    image_data_ignored: bool
    models: dict[str, ShortLineTemplateModel]
    reference_gray: np.ndarray
    reference_grad: np.ndarray

    def catalog(self) -> dict[str, Any]:
        features: dict[str, Any] = {}
        for canonical, model in sorted(self.models.items()):
            p1 = np.asarray(model.points[0], dtype=np.float64)
            p2 = np.asarray(model.points[1], dtype=np.float64)
            vector = p2 - p1
            features[canonical] = {
                "rawLabel": model.label,
                "canonicalFeature": canonical,
                "shapeType": model.shape_type,
                "points": [[float(value) for value in point] for point in model.points],
                "annotatedLengthPx": float(np.linalg.norm(vector)),
                "angleDeg": math.degrees(math.atan2(float(vector[1]), float(vector[0]))),
            }
        return {
            "schemaVersion": LABELME_REFERENCE_SCHEMA_VERSION,
            "annotationPath": str(self.annotation_path),
            "annotationSha256": self.annotation_sha256,
            "imagePath": str(self.image_path),
            "imageSha256": self.image_sha256,
            "width": self.width,
            "height": self.height,
            "imageDataIgnored": self.image_data_ignored,
            "features": features,
        }


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_labelme_short_line_reference(path: Path) -> LabelMeShortLineReference:
    """Load a strict external 19/30 template without exposing embedded image data."""
    annotation_path = path.resolve()
    if not annotation_path.is_file():
        raise ValueError(f"short-line LabelMe annotation does not exist: {annotation_path}")
    try:
        annotation = core.read_labelme(annotation_path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read short-line LabelMe annotation: {exc}") from exc
    if not isinstance(annotation, Mapping):
        raise ValueError("short-line LabelMe annotation must be an object")

    image_value = annotation.get("imagePath")
    if not isinstance(image_value, str) or not image_value.strip():
        raise ValueError("short-line LabelMe imagePath is required")
    portable_image_value = image_value.strip().replace("\\", "/")
    image_path_value = Path(portable_image_value)
    image_path = (
        image_path_value if image_path_value.is_absolute() else annotation_path.parent / image_path_value
    ).resolve()
    if not image_path.is_file():
        raise ValueError(f"short-line LabelMe reference image does not exist: {image_path}")
    reference_gray = core.load_detection_gray(image_path)
    if reference_gray.ndim != 2 or not reference_gray.size:
        raise ValueError("short-line LabelMe reference image must be a non-empty image")
    actual_height, actual_width = map(int, reference_gray.shape)
    declared_width = annotation.get("imageWidth")
    declared_height = annotation.get("imageHeight")
    if (
        not isinstance(declared_width, int)
        or isinstance(declared_width, bool)
        or not isinstance(declared_height, int)
        or isinstance(declared_height, bool)
        or declared_width != actual_width
        or declared_height != actual_height
    ):
        raise ValueError(
            "short-line LabelMe imageWidth/imageHeight must match the referenced image "
            f"(declared={declared_width}x{declared_height}, actual={actual_width}x{actual_height})"
        )

    shapes = annotation.get("shapes")
    if not isinstance(shapes, list):
        raise ValueError("short-line LabelMe shapes must be an array")
    models: dict[str, ShortLineTemplateModel] = {}
    for shape_index, shape in enumerate(shapes, start=1):
        if not isinstance(shape, Mapping):
            raise ValueError(f"short-line LabelMe shape {shape_index} must be an object")
        raw_label = str(shape.get("label", ""))
        canonical = canonical_feature_label(raw_label)
        if canonical not in SUPPORTED_FEATURES:
            continue
        if canonical in models:
            raise ValueError(f"short-line LabelMe feature {canonical} is duplicated")
        if shape.get("shape_type") != "line":
            raise ValueError(f"short-line LabelMe feature {canonical} must use shape_type 'line'")
        raw_points = shape.get("points")
        if not isinstance(raw_points, list) or len(raw_points) != 2:
            raise ValueError(f"short-line LabelMe feature {canonical} must contain exactly two points")
        points: list[tuple[float, float]] = []
        for point_index, point in enumerate(raw_points, start=1):
            if not isinstance(point, Sequence) or isinstance(point, (str, bytes, bytearray)) or len(point) != 2:
                raise ValueError(f"short-line LabelMe feature {canonical} point {point_index} must be [x, y]")
            x = _finite_number(point[0])
            y = _finite_number(point[1])
            if x is None or y is None:
                raise ValueError(f"short-line LabelMe feature {canonical} point {point_index} must be finite")
            if not (0.0 <= x < actual_width and 0.0 <= y < actual_height):
                raise ValueError(f"short-line LabelMe feature {canonical} point {point_index} is outside the image")
            points.append((x, y))
        if math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) <= 1e-9:
            raise ValueError(f"short-line LabelMe feature {canonical} endpoints must be distinct")
        models[canonical] = ShortLineTemplateModel(raw_label, "line", (points[0], points[1]))

    missing = sorted(SUPPORTED_FEATURES - set(models))
    if missing:
        raise ValueError(f"short-line LabelMe annotation is missing canonical features: {missing}")
    return LabelMeShortLineReference(
        annotation_path=annotation_path,
        annotation_sha256=_sha256_file(annotation_path),
        image_path=image_path,
        image_sha256=_sha256_file(image_path),
        width=actual_width,
        height=actual_height,
        image_data_ignored=annotation.get("imageData") is not None,
        models=models,
        reference_gray=reference_gray,
        reference_grad=core.gradient_magnitude(reference_gray),
    )


def candidate_config_sha256(config: Mapping[str, Any]) -> str:
    validate_candidate_config(config)
    return hashlib.sha256(_canonical_json(config).encode("utf-8")).hexdigest()


def _require_exact_keys(value: Mapping[str, Any], required: set[str], context: str) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing or unknown:
        raise ValueError(f"{context} keys invalid: missing={missing}, unknown={unknown}")


def _positive(value: Any, name: str, *, allow_zero: bool = False) -> float:
    number = _finite_number(value)
    valid = number is not None and (number >= 0.0 if allow_zero else number > 0.0)
    if not valid:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be a finite {qualifier} number")
    return float(number)


def validate_candidate_config(config: Mapping[str, Any]) -> None:
    if not isinstance(config, Mapping):
        raise ValueError("candidate config must be an object")
    candidate_id = config.get("candidateId")
    if candidate_id not in CANDIDATE_SOURCES:
        raise ValueError(f"candidate config has unsupported candidateId: {candidate_id!r}")
    is_v2 = candidate_id == CANDIDATE_SOURCE_V2
    required_keys = {"schemaVersion", "candidateId", "algorithmVersion", "features", "template", "search", "gates"}
    if is_v2:
        required_keys.add("registration")
    _require_exact_keys(
        config,
        required_keys,
        "candidate config",
    )
    expected_schema = CANDIDATE_CONFIG_SCHEMA_VERSION_V2 if is_v2 else CANDIDATE_CONFIG_SCHEMA_VERSION
    if config.get("schemaVersion") != expected_schema:
        raise ValueError("unsupported short-line candidate config schemaVersion")
    for field in ("candidateId", "algorithmVersion"):
        if not isinstance(config.get(field), str) or not str(config[field]).strip():
            raise ValueError(f"candidate config {field} is required")
    features = config.get("features")
    if (
        not isinstance(features, Sequence)
        or isinstance(features, (str, bytes, bytearray))
        or list(features) != ["19", "30"]
    ):
        raise ValueError("candidate features must contain canonical 19 and 30 exactly once")

    template = config.get("template")
    if not isinstance(template, Mapping):
        raise ValueError("candidate template must be an object")
    _require_exact_keys(template, {"alongExtensionPx", "halfWidthPx", "sampleStepPx"}, "candidate template")
    _positive(template["alongExtensionPx"], "template.alongExtensionPx", allow_zero=True)
    _positive(template["halfWidthPx"], "template.halfWidthPx")
    _positive(template["sampleStepPx"], "template.sampleStepPx")

    search = config.get("search")
    if not isinstance(search, Mapping):
        raise ValueError("candidate search must be an object")
    _require_exact_keys(search, {"coarse", "fine"}, "candidate search")
    search_fields = {
        "angleRadiusDeg",
        "angleStepDeg",
        "longitudinalRadiusPx",
        "longitudinalStepPx",
        "lateralRadiusPx",
        "lateralStepPx",
    }
    for level in ("coarse", "fine"):
        value = search.get(level)
        if not isinstance(value, Mapping):
            raise ValueError(f"search.{level} must be an object")
        _require_exact_keys(value, search_fields, f"search.{level}")
        for field in search_fields:
            _positive(value[field], f"search.{level}.{field}")
    for dimension in ("angle", "longitudinal", "lateral"):
        radius_key = f"{dimension}Radius{'Deg' if dimension == 'angle' else 'Px'}"
        if float(search["fine"][radius_key]) > float(search["coarse"][radius_key]):
            raise ValueError(f"search.fine.{radius_key} cannot exceed coarse radius")

    gates = config.get("gates")
    if not isinstance(gates, Mapping):
        raise ValueError("candidate gates must be an object")
    gate_fields = {
        "minimumPredictionLengthPx",
        "maximumPredictionLengthPx",
        "minimumCoverageRatio",
        "minimumTemplateStd",
        "minimumRoiContrast",
        "minimumGradientP90",
        "minimumCorrelation",
        "minimumRobustZ",
        "minimumSeparatedPeakGap",
        "separationAngleDeg",
        "separationLongitudinalPx",
        "separationLateralPx",
        "maximumAngleCorrectionDeg",
    }
    _require_exact_keys(gates, gate_fields, "candidate gates")
    numbers = {
        name: _positive(gates[name], f"gates.{name}", allow_zero=True)
        for name in gate_fields
        if name != "minimumCorrelation"
    }
    minimum_correlation = _finite_number(gates["minimumCorrelation"])
    if minimum_correlation is None:
        raise ValueError("gates.minimumCorrelation must be finite")
    numbers["minimumCorrelation"] = minimum_correlation
    if numbers["minimumPredictionLengthPx"] <= 0 or numbers["maximumPredictionLengthPx"] < numbers["minimumPredictionLengthPx"]:
        raise ValueError("candidate prediction length range must be positive and ordered")
    if not 0.0 < numbers["minimumCoverageRatio"] <= 1.0:
        raise ValueError("gates.minimumCoverageRatio must be in (0, 1]")
    if not -1.0 <= numbers["minimumCorrelation"] <= 1.0:
        raise ValueError("gates.minimumCorrelation must be in [-1, 1]")
    if numbers["maximumAngleCorrectionDeg"] > float(search["coarse"]["angleRadiusDeg"]):
        raise ValueError("maximumAngleCorrectionDeg cannot exceed coarse angle radius")
    if is_v2:
        validate_registration_config(config["registration"])


def load_candidate_config(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read short-line candidate config: {exc}") from exc
    validate_candidate_config(value)
    return value


def _axis(radius: float, step: float) -> np.ndarray:
    count = int(math.floor((2.0 * radius) / step + 1e-9))
    values = -radius + np.arange(count + 1, dtype=np.float64) * step
    if values[-1] < radius - 1e-9:
        values = np.append(values, radius)
    return values


def _fine_axis(center: float, radius: float, step: float, global_radius: float) -> np.ndarray:
    values = center + _axis(radius, step)
    values = np.clip(values, -global_radius, global_radius)
    return np.unique(np.round(values, 12))


def _oriented_coordinates(length: float, template: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    step = float(template["sampleStepPx"])
    extension = float(template["alongExtensionPx"])
    half_width = float(template["halfWidthPx"])
    along = np.arange(-length * 0.5 - extension, length * 0.5 + extension + step * 0.5, step)
    across = np.arange(-half_width, half_width + step * 0.5, step)
    return np.meshgrid(along, across, indexing="ij")


def _sample_patch(
    image: np.ndarray,
    midpoint: np.ndarray,
    theta: float,
    along_grid: np.ndarray,
    across_grid: np.ndarray,
) -> np.ndarray:
    tangent = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    normal = np.array([-tangent[1], tangent[0]], dtype=np.float64)
    xs = midpoint[0] + along_grid * tangent[0] + across_grid * normal[0]
    ys = midpoint[1] + along_grid * tangent[1] + across_grid * normal[1]
    return core.bilinear_sample(image, xs, ys)


def _batch_scores(
    image: np.ndarray,
    base_midpoint: np.ndarray,
    base_theta: float,
    angle_values_deg: np.ndarray,
    longitudinal_values: np.ndarray,
    lateral_values: np.ndarray,
    along_grid: np.ndarray,
    across_grid: np.ndarray,
    normalized_template: np.ndarray,
) -> list[dict[str, float]]:
    records: list[dict[str, float]] = []
    long_values, lat_values = np.meshgrid(longitudinal_values, lateral_values, indexing="ij")
    long_flat = long_values.reshape(-1)
    lat_flat = lat_values.reshape(-1)
    template_flat = normalized_template.reshape(1, -1)
    for correction_deg in angle_values_deg:
        theta = base_theta + math.radians(float(correction_deg))
        tangent = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
        normal = np.array([-tangent[1], tangent[0]], dtype=np.float64)
        centers = (
            base_midpoint.reshape(1, 2)
            + long_flat.reshape(-1, 1) * tangent.reshape(1, 2)
            + lat_flat.reshape(-1, 1) * normal.reshape(1, 2)
        )
        xs = (
            centers[:, 0, None, None]
            + along_grid[None, :, :] * tangent[0]
            + across_grid[None, :, :] * normal[0]
        )
        ys = (
            centers[:, 1, None, None]
            + along_grid[None, :, :] * tangent[1]
            + across_grid[None, :, :] * normal[1]
        )
        patches = core.bilinear_sample(image, xs, ys)
        finite = np.isfinite(patches)
        counts = finite.sum(axis=(1, 2))
        coverage = counts / float(patches.shape[1] * patches.shape[2])
        sums = np.where(finite, patches, 0.0).sum(axis=(1, 2))
        means = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
        centered = np.where(finite, patches - means[:, None, None], 0.0).reshape(len(patches), -1)
        norms = np.linalg.norm(centered, axis=1)
        scores = np.divide(
            (centered * template_flat).sum(axis=1),
            norms,
            out=np.full_like(norms, -1.0, dtype=np.float64),
            where=norms > 1e-9,
        )
        for index in range(len(scores)):
            records.append({
                "score": float(scores[index]),
                "coverage": float(coverage[index]),
                "angleCorrectionDeg": float(correction_deg),
                "longitudinalOffsetPx": float(long_flat[index]),
                "lateralOffsetPx": float(lat_flat[index]),
            })
    return records


def _geometry(points: tuple[np.ndarray, np.ndarray]) -> dict[str, float]:
    p1, p2 = points
    vector = p2 - p1
    return {
        "x1": float(p1[0]),
        "y1": float(p1[1]),
        "x2": float(p2[0]),
        "y2": float(p2[1]),
        "length": float(np.linalg.norm(vector)),
        "angleDeg": math.degrees(math.atan2(float(vector[1]), float(vector[0]))),
    }


def _measurement_geometry(measurements: Mapping[str, Any], label: str, reference: bool = False) -> dict[str, float] | None:
    suffix = "_ref_px" if reference else "_px"
    names = {name: f"{label}.{name}{suffix}" for name in ("x1", "y1", "x2", "y2")}
    values = {name: _finite_number(measurements.get(key)) for name, key in names.items()}
    if any(value is None for value in values.values()):
        return None
    p1 = np.array([values["x1"], values["y1"]], dtype=np.float64)
    p2 = np.array([values["x2"], values["y2"]], dtype=np.float64)
    geometry = _geometry((p1, p2))
    length_key = f"{label}.length{suffix}"
    angle_key = f"{label}.angle_{'ref_' if reference else ''}deg"
    length = _finite_number(measurements.get(length_key))
    angle = _finite_number(measurements.get(angle_key))
    if length is not None:
        geometry["length"] = length
    if angle is not None:
        geometry["angleDeg"] = angle
    return geometry


def _core_profile(target_grad: np.ndarray, geometry: Mapping[str, float] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "searchBoundsPx": [-12.0, 12.0],
        "profile": [],
        "peakOffsetPx": None,
        "peak": None,
        "median": None,
        "threshold": None,
        "peakAtBoundary": None,
        "passesCoreRule": False,
        "reconstructedFallbackReason": None,
    }
    if geometry is None:
        result["reconstructedFallbackReason"] = "missing_core_geometry"
        return result
    p1 = np.array([geometry["x1"], geometry["y1"]], dtype=np.float64)
    p2 = np.array([geometry["x2"], geometry["y2"]], dtype=np.float64)
    vector = p2 - p1
    length = float(np.linalg.norm(vector))
    if length < 4.0:
        result["reconstructedFallbackReason"] = "line_too_short"
        return result
    tangent = vector / length
    normal = np.array([-tangent[1], tangent[0]], dtype=np.float64)
    along = np.linspace(0.0, length, max(12, int(round(length)) + 1))
    across = np.arange(-12.0, 13.0, dtype=np.float64)
    along_grid, across_grid = np.meshgrid(along, across, indexing="ij")
    xs = p1[0] + along_grid * tangent[0] + across_grid * normal[0]
    ys = p1[1] + along_grid * tangent[1] + across_grid * normal[1]
    sampled = core.bilinear_sample(target_grad, xs, ys)
    if np.isnan(sampled).all():
        result["reconstructedFallbackReason"] = "sampling_out_of_bounds"
        return result
    profile = core.smooth_1d(np.nan_to_num(sampled, nan=0.0).sum(axis=0), window=3)
    peak_index = int(np.argmax(profile))
    median = float(np.median(profile))
    threshold = max(1.4 * median, median + 5.0)
    at_boundary = peak_index in {0, len(profile) - 1}
    passes = not at_boundary and float(profile[peak_index]) >= threshold
    if at_boundary:
        reason = "peak_at_search_boundary"
    elif not passes:
        reason = "peak_not_prominent"
    else:
        reason = None
    result.update({
        "profile": [float(value) for value in profile],
        "peakOffsetPx": float(across[peak_index]),
        "peak": float(profile[peak_index]),
        "median": median,
        "threshold": threshold,
        "peakAtBoundary": at_boundary,
        "passesCoreRule": passes,
        "reconstructedFallbackReason": reason,
    })
    return result


def _roi_statistics(
    target_gray: np.ndarray,
    target_grad: np.ndarray,
    geometry: Mapping[str, float] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    empty = {
        "boundsPx": None,
        "validFraction": 0.0,
        "contrastP95P05": None,
        "gradientP50": None,
        "gradientP90": None,
        "gradientMax": None,
    }
    if geometry is None:
        return empty
    p1 = np.array([geometry["x1"], geometry["y1"]], dtype=np.float64)
    p2 = np.array([geometry["x2"], geometry["y2"]], dtype=np.float64)
    vector = p2 - p1
    length = float(np.linalg.norm(vector))
    if length < 1e-9:
        return empty
    midpoint = (p1 + p2) * 0.5
    theta = math.atan2(float(vector[1]), float(vector[0]))
    step = float(config["template"]["sampleStepPx"])
    extension = float(config["template"]["alongExtensionPx"]) + float(config["search"]["coarse"]["longitudinalRadiusPx"])
    half_width = float(config["template"]["halfWidthPx"]) + float(config["search"]["coarse"]["lateralRadiusPx"])
    along = np.arange(-length * 0.5 - extension, length * 0.5 + extension + step * 0.5, step)
    across = np.arange(-half_width, half_width + step * 0.5, step)
    along_grid, across_grid = np.meshgrid(along, across, indexing="ij")
    tangent = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    normal = np.array([-tangent[1], tangent[0]], dtype=np.float64)
    xs = midpoint[0] + along_grid * tangent[0] + across_grid * normal[0]
    ys = midpoint[1] + along_grid * tangent[1] + across_grid * normal[1]
    intensities = core.bilinear_sample(target_gray, xs, ys)
    gradients = core.bilinear_sample(target_grad, xs, ys)
    finite = np.isfinite(intensities) & np.isfinite(gradients)
    if not finite.any():
        return empty
    valid_intensity = intensities[finite]
    valid_gradient = gradients[finite]
    return {
        "boundsPx": {
            "minX": float(np.nanmin(xs)),
            "minY": float(np.nanmin(ys)),
            "maxX": float(np.nanmax(xs)),
            "maxY": float(np.nanmax(ys)),
        },
        "validFraction": float(finite.mean()),
        "contrastP95P05": float(np.percentile(valid_intensity, 95) - np.percentile(valid_intensity, 5)),
        "gradientP50": float(np.percentile(valid_gradient, 50)),
        "gradientP90": float(np.percentile(valid_gradient, 90)),
        "gradientMax": float(np.max(valid_gradient)),
    }


def _check(check_id: str, passed: bool, rule: Any, observed: Any, *, required: bool = True) -> dict[str, Any]:
    return {"id": check_id, "required": required, "passed": bool(passed), "rule": rule, "observed": observed}


def _transition(core_valid: bool, candidate_valid: bool) -> str:
    if core_valid and candidate_valid:
        return "both_valid"
    if not core_valid and candidate_valid:
        return "recovered"
    if core_valid and not candidate_valid:
        return "regressed"
    return "both_invalid"


FAILURE_CATEGORY_BY_CHECK = {
    "registration_valid": "registration_failed",
    "projected_geometry": "invalid_prediction",
    "prediction_fields": "invalid_prediction",
    "prediction_length": "invalid_prediction",
    "core_path_consistency": "core_path_inconsistent",
    "reference_template_coverage": "insufficient_coverage",
    "target_roi_coverage": "insufficient_coverage",
    "candidate_patch_coverage": "insufficient_coverage",
    "template_texture": "no_edge",
    "roi_contrast": "no_edge",
    "gradient_energy": "no_edge",
    "minimum_correlation": "fit_instability",
    "robust_prominence": "low_prominence",
    "separated_peak_gap": "competing_peak",
    "search_interior": "boundary_peak",
    "angle_correction": "direction_deviation",
    "finite_geometry": "fit_instability",
}


def _angle_delta_deg(value: float, baseline: float) -> float:
    return (value - baseline + 180.0) % 360.0 - 180.0


class ShortLineCandidateEvaluator:
    """Evaluate 19/30 without modifying the baseline core result."""

    def __init__(
        self,
        reference_model: Any,
        config: Mapping[str, Any],
        config_path: Path | None = None,
        labelme_reference_path: Path | None = None,
    ):
        validate_candidate_config(config)
        self.reference_model = reference_model
        self.config = json.loads(_canonical_json(config))
        self.config_path = config_path.resolve() if config_path is not None else None
        self.config_sha256 = candidate_config_sha256(self.config)
        self.models = {
            canonical_feature_label(str(model.label)): model
            for model in reference_model.shapes
            if getattr(model, "shape_type", None) == "line"
            and canonical_feature_label(str(model.label)) in SUPPORTED_FEATURES
            and len(getattr(model, "points", [])) == 2
        }
        self.labelme_reference = (
            load_labelme_short_line_reference(labelme_reference_path)
            if labelme_reference_path is not None
            else None
        )
        self.main_housing_registrar: MainHousingRegistrar | None = None
        if self.config["candidateId"] == CANDIDATE_SOURCE_V2:
            if self.labelme_reference is None:
                raise ValueError(
                    "main-housing-registration-v2 is blocked without an external 19/30 LabelMe reference"
                )
            self.main_housing_registrar = MainHousingRegistrar(
                self.labelme_reference.reference_gray,
                {
                    canonical: model.points
                    for canonical, model in self.labelme_reference.models.items()
                },
                self.config["registration"],
            )
        self.template_models = (
            self.labelme_reference.models if self.labelme_reference is not None else self.models
        )
        self.template_gradient = (
            self.labelme_reference.reference_grad
            if self.labelme_reference is not None
            else np.asarray(getattr(reference_model, "reference_grad", np.empty((0, 0))), dtype=np.float64)
        )
        for canonical, template_model in self.template_models.items():
            length = math.hypot(
                template_model.points[1][0] - template_model.points[0][0],
                template_model.points[1][1] - template_model.points[0][1],
            )
            minimum = float(self.config["gates"]["minimumPredictionLengthPx"])
            maximum = float(self.config["gates"]["maximumPredictionLengthPx"])
            if not minimum <= length <= maximum:
                raise ValueError(
                    f"short-line LabelMe feature {canonical} annotated length {length:.6f}px "
                    f"is outside candidate range [{minimum}, {maximum}]"
                )

    @property
    def provenance(self) -> dict[str, Any]:
        labelme = self.labelme_reference
        return {
            "candidateId": self.config["candidateId"],
            "algorithmVersion": self.config["algorithmVersion"],
            "configSha256": self.config_sha256,
            "configPath": str(self.config_path) if self.config_path is not None else None,
            "referenceMode": "external_labelme" if labelme is not None else "desktop_core",
            "referenceSchemaVersion": LABELME_REFERENCE_SCHEMA_VERSION if labelme is not None else None,
            "referenceAnnotationPath": str(labelme.annotation_path) if labelme is not None else None,
            "referenceAnnotationSha256": labelme.annotation_sha256 if labelme is not None else None,
            "referenceImagePath": str(labelme.image_path) if labelme is not None else None,
            "referenceImageSha256": labelme.image_sha256 if labelme is not None else None,
        }

    def evaluate_image(
        self,
        image_path: Path,
        measurements: Mapping[str, Any],
        feature_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.evaluate_gray(core.load_detection_gray(image_path), measurements, feature_quality)

    def evaluate_gray(
        self,
        target_gray: np.ndarray,
        measurements: Mapping[str, Any],
        feature_quality: Mapping[str, Any],
    ) -> dict[str, Any]:
        target = np.asarray(target_gray, dtype=np.float64)
        if target.ndim != 2 or not target.size:
            raise ValueError("short-line candidate target must be a non-empty grayscale array")
        target_grad = core.gradient_magnitude(target)
        registration = (
            self.main_housing_registrar.register(target)
            if self.main_housing_registrar is not None
            else None
        )
        output: dict[str, Any] = {}
        for canonical in self.config["features"]:
            model = self.models.get(canonical)
            template_model = self.template_models.get(canonical)
            if model is None or template_model is None:
                continue
            raw_label = str(model.label)
            status = feature_quality.get(raw_label)
            if not isinstance(status, Mapping):
                status = next(
                    (
                        item for item in feature_quality.values()
                        if isinstance(item, Mapping) and item.get("canonicalFeature") == canonical
                    ),
                    {},
                )
            output[raw_label] = self._evaluate_feature(
                model,
                template_model,
                canonical,
                target,
                target_grad,
                measurements,
                status,
                registration,
            )
        return output

    def _evaluate_feature(
        self,
        model: Any,
        template_model: Any,
        canonical: str,
        target_gray: np.ndarray,
        target_grad: np.ndarray,
        measurements: Mapping[str, Any],
        status: Mapping[str, Any],
        registration: RegistrationResult | None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        label = str(model.label)
        core_valid = status.get("coreValid") is True
        core_target = _measurement_geometry(measurements, label, reference=False)
        core_reference = _measurement_geometry(measurements, label, reference=True)
        core_record = {
            "coreValid": core_valid,
            "source": status.get("source"),
            "reason": status.get("reason"),
            "target": core_target,
            "reference": core_reference,
            "fields": dict(status.get("fields", {})) if isinstance(status.get("fields"), Mapping) else {},
        }
        core_search = _core_profile(target_grad, core_target)
        core_search["coreSource"] = status.get("source")
        core_search["coreFallbackReason"] = status.get("reason")
        is_v2 = self.config["candidateId"] == CANDIDATE_SOURCE_V2
        projected_geometry: dict[str, float] | None = None
        if is_v2 and registration is not None and registration.valid:
            projected_points = registration.project_points(template_model.points)
            projected_geometry = _geometry(
                (np.asarray(projected_points[0], dtype=np.float64), np.asarray(projected_points[1], dtype=np.float64))
            )
        candidate_base = projected_geometry if is_v2 else core_target
        roi = _roi_statistics(target_gray, target_grad, candidate_base, self.config)
        checks: list[dict[str, Any]] = []
        gates = self.config["gates"]
        if is_v2:
            checks.extend([
                _check(
                    "registration_valid",
                    registration is not None and registration.valid,
                    "independent main-housing registration passes all required gates",
                    registration.to_dict() if registration is not None else None,
                ),
                _check(
                    "projected_geometry",
                    projected_geometry is not None,
                    "external 19/30 endpoints projected through accepted registration",
                    projected_geometry,
                ),
            ])
        else:
            checks.append(_check("prediction_fields", core_target is not None, "finite baseline x1/y1/x2/y2", core_target))
        length = candidate_base["length"] if candidate_base is not None else None
        checks.append(_check(
            "prediction_length",
            length is not None and float(gates["minimumPredictionLengthPx"]) <= length <= float(gates["maximumPredictionLengthPx"]),
            {"minimum": gates["minimumPredictionLengthPx"], "maximum": gates["maximumPredictionLengthPx"]},
            length,
        ))
        expected_core_pass = core_search["passesCoreRule"]
        source = str(status.get("source") or "")
        known_core_source = source in {"short_line_lateral_edge", "short_line_transform_fallback"}
        consistency = not known_core_source or core_valid == bool(expected_core_pass)
        checks.append(_check(
            "core_path_consistency",
            consistency,
            "coreValid agrees with reconstructed fixed short-line rule for known short-line sources",
            {"coreValid": core_valid, "reconstructedPass": expected_core_pass, "source": source},
            required=not is_v2,
        ))

        candidate_search: dict[str, Any] = {
            "templateReference": {
                "mode": self.provenance["referenceMode"],
                "rawLabel": str(template_model.label),
                "annotatedLengthPx": math.hypot(
                    template_model.points[1][0] - template_model.points[0][0],
                    template_model.points[1][1] - template_model.points[0][1],
                ),
            },
            "registration": registration.to_dict() if registration is not None else None,
            "projectedGeometry": projected_geometry,
            "searchBounds": {
                "angleCorrectionDeg": [-float(self.config["search"]["coarse"]["angleRadiusDeg"]), float(self.config["search"]["coarse"]["angleRadiusDeg"])],
                "longitudinalOffsetPx": [-float(self.config["search"]["coarse"]["longitudinalRadiusPx"]), float(self.config["search"]["coarse"]["longitudinalRadiusPx"])],
                "lateralOffsetPx": [-float(self.config["search"]["coarse"]["lateralRadiusPx"]), float(self.config["search"]["coarse"]["lateralRadiusPx"])],
            },
            "best": None,
            "separatedSecond": None,
            "scoreMedian": None,
            "scoreMad": None,
            "robustZ": None,
            "separatedPeakGap": None,
            "atSearchBoundary": None,
        }
        candidate_target: dict[str, float] | None = None
        candidate_reference: dict[str, float] | None = None
        delta: dict[str, float] | None = None

        if candidate_base is not None and length is not None and length > 1e-9:
            p1 = np.array([candidate_base["x1"], candidate_base["y1"]], dtype=np.float64)
            p2 = np.array([candidate_base["x2"], candidate_base["y2"]], dtype=np.float64)
            base_midpoint = (p1 + p2) * 0.5
            base_theta = math.atan2(float(p2[1] - p1[1]), float(p2[0] - p1[0]))
            ref_p1 = np.asarray(template_model.points[0], dtype=np.float64)
            ref_p2 = np.asarray(template_model.points[1], dtype=np.float64)
            ref_midpoint = (ref_p1 + ref_p2) * 0.5
            ref_theta = math.atan2(float(ref_p2[1] - ref_p1[1]), float(ref_p2[0] - ref_p1[0]))
            along_grid, across_grid = _oriented_coordinates(length, self.config["template"])
            template_scale = (
                float(registration.scale)
                if is_v2 and registration is not None and registration.scale is not None
                else 1.0
            )
            template_patch = _sample_patch(
                self.template_gradient,
                ref_midpoint,
                ref_theta,
                along_grid / template_scale,
                across_grid / template_scale,
            )
            template_finite = np.isfinite(template_patch)
            template_coverage = float(template_finite.mean())
            template_values = template_patch[template_finite]
            template_mean = float(template_values.mean()) if template_values.size else 0.0
            template_std = float(template_values.std()) if template_values.size else 0.0
            centered_template = np.where(template_finite, template_patch - template_mean, 0.0)
            template_norm = float(np.linalg.norm(centered_template))
            normalized_template = centered_template / template_norm if template_norm > 1e-9 else centered_template
            checks.append(_check(
                "reference_template_coverage",
                template_coverage >= float(gates["minimumCoverageRatio"]),
                gates["minimumCoverageRatio"],
                template_coverage,
            ))
            checks.append(_check(
                "template_texture",
                template_std >= float(gates["minimumTemplateStd"]),
                gates["minimumTemplateStd"],
                template_std,
            ))

            coarse = self.config["search"]["coarse"]
            coarse_angles = _axis(float(coarse["angleRadiusDeg"]), float(coarse["angleStepDeg"]))
            coarse_long = _axis(float(coarse["longitudinalRadiusPx"]), float(coarse["longitudinalStepPx"]))
            coarse_lat = _axis(float(coarse["lateralRadiusPx"]), float(coarse["lateralStepPx"]))
            coarse_records = _batch_scores(
                target_grad,
                base_midpoint,
                base_theta,
                coarse_angles,
                coarse_long,
                coarse_lat,
                along_grid,
                across_grid,
                normalized_template,
            )
            coarse_records.sort(key=lambda item: item["score"], reverse=True)
            coarse_best = coarse_records[0]
            fine = self.config["search"]["fine"]
            fine_angles = _fine_axis(
                coarse_best["angleCorrectionDeg"],
                float(fine["angleRadiusDeg"]),
                float(fine["angleStepDeg"]),
                float(coarse["angleRadiusDeg"]),
            )
            fine_long = _fine_axis(
                coarse_best["longitudinalOffsetPx"],
                float(fine["longitudinalRadiusPx"]),
                float(fine["longitudinalStepPx"]),
                float(coarse["longitudinalRadiusPx"]),
            )
            fine_lat = _fine_axis(
                coarse_best["lateralOffsetPx"],
                float(fine["lateralRadiusPx"]),
                float(fine["lateralStepPx"]),
                float(coarse["lateralRadiusPx"]),
            )
            fine_records = _batch_scores(
                target_grad,
                base_midpoint,
                base_theta,
                fine_angles,
                fine_long,
                fine_lat,
                along_grid,
                across_grid,
                normalized_template,
            )
            fine_records.sort(key=lambda item: item["score"], reverse=True)
            best = fine_records[0]
            separated = next(
                (
                    item for item in coarse_records[1:]
                    if abs(item["angleCorrectionDeg"] - coarse_best["angleCorrectionDeg"]) >= float(gates["separationAngleDeg"])
                    or abs(item["longitudinalOffsetPx"] - coarse_best["longitudinalOffsetPx"]) >= float(gates["separationLongitudinalPx"])
                    or abs(item["lateralOffsetPx"] - coarse_best["lateralOffsetPx"]) >= float(gates["separationLateralPx"])
                ),
                {"score": -1.0, "coverage": 0.0, "angleCorrectionDeg": None, "longitudinalOffsetPx": None, "lateralOffsetPx": None},
            )
            scores = np.asarray([record["score"] for record in coarse_records], dtype=np.float64)
            score_median = float(np.median(scores))
            score_mad = float(np.median(np.abs(scores - score_median)))
            robust_z = (coarse_best["score"] - score_median) / (1.4826 * score_mad + 1e-9)
            separated_gap = coarse_best["score"] - float(separated["score"])
            at_boundary = (
                abs(best["angleCorrectionDeg"]) >= float(coarse["angleRadiusDeg"]) - 1e-9
                or abs(best["longitudinalOffsetPx"]) >= float(coarse["longitudinalRadiusPx"]) - 1e-9
                or abs(best["lateralOffsetPx"]) >= float(coarse["lateralRadiusPx"]) - 1e-9
            )
            best_theta = base_theta + math.radians(best["angleCorrectionDeg"])
            best_tangent = np.array([math.cos(best_theta), math.sin(best_theta)], dtype=np.float64)
            best_normal = np.array([-best_tangent[1], best_tangent[0]], dtype=np.float64)
            best_midpoint = (
                base_midpoint
                + best["longitudinalOffsetPx"] * best_tangent
                + best["lateralOffsetPx"] * best_normal
            )
            best_patch = _sample_patch(
                target_grad,
                best_midpoint,
                best_theta,
                along_grid,
                across_grid,
            )
            best_patch_values = best_patch[np.isfinite(best_patch)]
            best_gradient_p90 = (
                float(np.percentile(best_patch_values, 90)) if best_patch_values.size else None
            )
            best["gradientP90"] = best_gradient_p90
            candidate_search.update({
                "best": best,
                "coarseBest": coarse_best,
                "separatedSecond": separated,
                "scoreMedian": score_median,
                "scoreMad": score_mad,
                "robustZ": robust_z,
                "separatedPeakGap": separated_gap,
                "atSearchBoundary": at_boundary,
            })

            checks.extend([
                _check("target_roi_coverage", roi["validFraction"] >= float(gates["minimumCoverageRatio"]), gates["minimumCoverageRatio"], roi["validFraction"]),
                _check("roi_contrast", roi["contrastP95P05"] is not None and roi["contrastP95P05"] >= float(gates["minimumRoiContrast"]), gates["minimumRoiContrast"], roi["contrastP95P05"]),
                _check("gradient_energy", best_gradient_p90 is not None and best_gradient_p90 >= float(gates["minimumGradientP90"]), gates["minimumGradientP90"], best_gradient_p90),
                _check("candidate_patch_coverage", best["coverage"] >= float(gates["minimumCoverageRatio"]), gates["minimumCoverageRatio"], best["coverage"]),
                _check("minimum_correlation", best["score"] >= float(gates["minimumCorrelation"]), gates["minimumCorrelation"], best["score"]),
                _check("robust_prominence", robust_z >= float(gates["minimumRobustZ"]), gates["minimumRobustZ"], robust_z),
                _check("separated_peak_gap", separated_gap >= float(gates["minimumSeparatedPeakGap"]), gates["minimumSeparatedPeakGap"], separated_gap),
                _check("search_interior", not at_boundary, "best candidate is inside all global search bounds", best),
                _check("angle_correction", abs(best["angleCorrectionDeg"]) <= float(gates["maximumAngleCorrectionDeg"]), gates["maximumAngleCorrectionDeg"], best["angleCorrectionDeg"]),
            ])

            candidate_theta = best_theta
            tangent = best_tangent
            normal = best_normal
            midpoint = best_midpoint
            half = tangent * (length * 0.5)
            raw_candidate_target = _geometry((midpoint - half, midpoint + half))
            finite_geometry = all(math.isfinite(value) for value in raw_candidate_target.values())
            checks.append(_check("finite_geometry", finite_geometry, "all candidate geometry values finite", raw_candidate_target))
            required_failed = [item["id"] for item in checks if item["required"] and not item["passed"]]
            if not required_failed:
                candidate_target = raw_candidate_target
                if is_v2 and registration is not None and registration.valid:
                    inverse = registration.inverse_points((
                        (candidate_target["x1"], candidate_target["y1"]),
                        (candidate_target["x2"], candidate_target["y2"]),
                    ))
                    ref_candidate_p1 = np.asarray(inverse[0])
                    ref_candidate_p2 = np.asarray(inverse[1])
                    candidate_reference = _geometry((ref_candidate_p1, ref_candidate_p2))
                else:
                    transform_values = {
                        "target_center_x": _finite_number(measurements.get("transform.target_center_x_px")),
                        "target_center_y": _finite_number(measurements.get("transform.target_center_y_px")),
                        "scale": _finite_number(measurements.get("transform.scale")),
                        "rotation_deg": _finite_number(measurements.get("transform.rotation_deg")),
                    }
                    if all(value is not None for value in transform_values.values()) and transform_values["scale"] > 0:
                        transform = core.SimilarityTransform(
                            tuple(self.reference_model.alignment_center),
                            (transform_values["target_center_x"], transform_values["target_center_y"]),
                            transform_values["scale"],
                            math.radians(transform_values["rotation_deg"]),
                            "candidate-inverse",
                        )
                        ref_candidate_p1 = np.asarray(transform.inverse_point((candidate_target["x1"], candidate_target["y1"])))
                        ref_candidate_p2 = np.asarray(transform.inverse_point((candidate_target["x2"], candidate_target["y2"])))
                        candidate_reference = _geometry((ref_candidate_p1, ref_candidate_p2))
                if core_target is not None:
                    core_midpoint = np.array([
                        (core_target["x1"] + core_target["x2"]) * 0.5,
                        (core_target["y1"] + core_target["y2"]) * 0.5,
                    ])
                    candidate_midpoint = np.array([
                        (candidate_target["x1"] + candidate_target["x2"]) * 0.5,
                        (candidate_target["y1"] + candidate_target["y2"]) * 0.5,
                    ])
                    endpoint_delta = np.array([
                        math.hypot(candidate_target["x1"] - core_target["x1"], candidate_target["y1"] - core_target["y1"]),
                        math.hypot(candidate_target["x2"] - core_target["x2"], candidate_target["y2"] - core_target["y2"]),
                    ])
                    delta = {
                        "midpointDistancePx": float(np.linalg.norm(candidate_midpoint - core_midpoint)),
                        "angleDeg": _angle_delta_deg(candidate_target["angleDeg"], core_target["angleDeg"]),
                        "endpointRmsPx": float(np.sqrt(np.mean(endpoint_delta * endpoint_delta))),
                        "lengthPx": candidate_target["length"] - core_target["length"],
                    }
        else:
            checks.extend([
                _check("reference_template_coverage", False, gates["minimumCoverageRatio"], None),
                _check("template_texture", False, gates["minimumTemplateStd"], None),
            ])

        failed_checks = [item["id"] for item in checks if item["required"] and not item["passed"]]
        failure_categories = sorted({
            FAILURE_CATEGORY_BY_CHECK.get(check_id, "unspecified") for check_id in failed_checks
        })
        candidate_valid = not failed_checks and candidate_target is not None
        if not candidate_valid:
            candidate_target = None
            candidate_reference = None
            delta = None
        diagnostic = {
            "diagnosticVersion": DIAGNOSTIC_VERSION,
            "feature": label,
            "canonicalFeature": canonical,
            "roi": roi,
            "coreSearch": core_search,
            "candidateSearch": candidate_search,
            "checks": checks,
            "failedChecks": failed_checks,
            "failureCategories": failure_categories,
        }
        candidate = {
            "candidateValid": candidate_valid,
            "source": self.config["candidateId"],
            "target": candidate_target,
            "reference": candidate_reference,
            "deltaFromCore": delta,
            "elapsedMs": (time.perf_counter() - started) * 1000.0,
        }
        return {
            "feature": label,
            "canonicalFeature": canonical,
            "candidateId": self.config["candidateId"],
            "algorithmVersion": self.config["algorithmVersion"],
            "configSha256": self.config_sha256,
            "core": core_record,
            "candidate": candidate,
            "diagnostic": diagnostic,
            "transition": _transition(core_valid, candidate_valid),
        }
