"""Slot-pose-owned bounded radial edge candidates over the locked A-end core."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from algorithms.end_face import core


def gaussian_blur_fast(arr: np.ndarray, sigma: float = core.DEFAULT_SMOOTH_SIGMA) -> np.ndarray:
    """Numerically equivalent bandwidth-reduced blur; preserve float64 output."""
    src = arr.astype(np.float32, copy=False)
    if sigma <= 0:
        return src.astype(np.float64)
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    padded = np.pad(src, ((0, 0), (radius, radius)), mode="edge")
    horizontal = np.zeros_like(src)
    for index, weight in enumerate(kernel):
        horizontal += padded[:, index:index + src.shape[1]] * weight
    padded = np.pad(horizontal, ((radius, radius), (0, 0)), mode="edge")
    output = np.zeros_like(src)
    for index, weight in enumerate(kernel):
        output += padded[index:index + src.shape[0], :] * weight
    return output.astype(np.float64)


def load_detection_gray_fast(path: Path) -> np.ndarray:
    return gaussian_blur_fast(core.load_gray(path))


def enumerate_radial_edge_candidates(
    radii: np.ndarray,
    values: np.ndarray,
    *,
    min_gradient: float = 8.0,
    separation_px: float = 3.0,
    max_peaks: int = 8,
    polarity: str | None = None,
    min_background_persistence_ratio: float = 0.0,
    min_contrast: float = 0.0,
) -> list[dict[str, float | str]]:
    rr = np.asarray(radii, dtype=np.float64)
    vv = np.asarray(values, dtype=np.float64)
    if rr.ndim != 1 or vv.ndim != 1 or rr.size != vv.size or rr.size < 2:
        raise ValueError("radial evidence must be equal-length one-dimensional arrays")
    if not np.isfinite(rr).all() or not np.isfinite(vv).all():
        raise ValueError("radial evidence must be finite")
    if (
        not math.isfinite(float(min_gradient)) or float(min_gradient) <= 0.0
        or not math.isfinite(float(separation_px)) or float(separation_px) <= 0.0
        or isinstance(max_peaks, bool) or not isinstance(max_peaks, int) or max_peaks <= 0
        or not math.isfinite(float(min_contrast)) or float(min_contrast) < 0.0
    ):
        raise ValueError("peak controls must be positive and finite")
    if polarity not in {None, "bright_to_dark", "dark_to_bright"}:
        raise ValueError("polarity must be bright_to_dark, dark_to_bright or None")
    if (
        not math.isfinite(float(min_background_persistence_ratio))
        or not 0.0 <= float(min_background_persistence_ratio) <= 1.0
    ):
        raise ValueError("min_background_persistence_ratio must be in [0,1]")
    derivative = np.diff(vv)
    strengths = np.abs(derivative)
    peak_mask = strengths >= float(min_gradient)
    peak_mask[1:] &= strengths[1:] >= strengths[:-1]
    peak_mask[:-1] &= strengths[:-1] >= strengths[1:]
    candidates = np.flatnonzero(peak_mask)
    if candidates.size:
        candidates = candidates[np.lexsort((candidates, -strengths[candidates]))]
    outer_count = max(8, len(vv) // 5)
    dark_level = float(np.percentile(vv[-outer_count:], 30))
    bright_level = float(np.percentile(vv, 85))
    if bright_level - dark_level < float(min_contrast):
        return []
    threshold = dark_level + 0.45 * (bright_level - dark_level)
    selected: list[dict[str, float | str]] = []
    for raw_index in candidates:
        index = int(raw_index)
        edge_polarity = "bright_to_dark" if derivative[index] < 0.0 else "dark_to_bright"
        if polarity is not None and edge_polarity != polarity:
            continue
        score = -derivative if edge_polarity == "bright_to_dark" else derivative
        delta = core.parabolic_peak(score, index)
        radius = float((rr[index] + rr[index + 1]) / 2.0 + delta * float(rr[1] - rr[0]))
        if any(abs(radius - float(item["radiusPx"])) < float(separation_px) for item in selected):
            continue
        tail = vv[min(index + 3, len(vv)):]
        persistence = float(np.mean(tail < threshold)) if edge_polarity == "bright_to_dark" and tail.size else 0.0
        if persistence < float(min_background_persistence_ratio):
            continue
        gradient = float(derivative[index])
        selected.append({
            "radiusPx": radius, "gradient": gradient, "strength": abs(gradient),
            "polarity": edge_polarity, "backgroundPersistenceRatio": persistence,
        })
        if len(selected) >= max_peaks:
            break
    return selected


def outer_boundary_edge_candidates(
    target_gray: np.ndarray,
    center: tuple[float, float],
    angle: float,
    predicted_radius: float,
    *,
    min_gradient: float = 4.0,
    separation_px: float = 3.0,
    max_peaks: int = 8,
    min_background_persistence_ratio: float = 0.95,
) -> list[dict[str, float | str]]:
    radii, profile = core.sample_radial(target_gray, center[0], center[1], angle, predicted_radius, 90)
    if len(radii) < 45:
        return []
    values = core.smooth_1d(profile, 9)
    peaks = enumerate_radial_edge_candidates(
        radii, values, min_gradient=min_gradient, separation_px=separation_px,
        max_peaks=max_peaks, polarity="bright_to_dark",
        min_background_persistence_ratio=min_background_persistence_ratio,
        min_contrast=12.0,
    )
    return [
        {
            **item,
            "x": center[0] + float(item["radiusPx"]) * math.cos(angle),
            "y": center[1] + float(item["radiusPx"]) * math.sin(angle),
        }
        for item in peaks
    ]
