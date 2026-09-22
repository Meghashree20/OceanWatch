"""Transparent, rule-based cleanup priority decision engine."""

from dataclasses import dataclass
from math import log1p
from typing import Any, Dict, Optional


DEFAULT_WEIGHTS = {
    "pollution_severity": 0.40,
    "ecological_risk": 0.25,
    "human_exposure": 0.20,
    "cleanup_feasibility": 0.15,
}
ACTION_BY_LEVEL = {
    "LOW": "Monitor",
    "MEDIUM": "Schedule further assessment",
    "HIGH": "Prioritize cleanup assessment",
    "CRITICAL": "Immediate cleanup assessment",
}
CONTEXT_FIELDS = ("ecological_risk", "human_exposure", "cleanup_feasibility")


@dataclass
class RecommendationConfig:
    density_reference_count: int = 100
    weights: Optional[Dict[str, float]] = None

    def resolved_weights(self) -> Dict[str, float]:
        weights = dict(self.weights or DEFAULT_WEIGHTS)
        if set(weights) != set(DEFAULT_WEIGHTS):
            raise ValueError(f"Weights must contain exactly: {sorted(DEFAULT_WEIGHTS)}")
        if any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError("Recommendation weights must be non-negative and sum to 1.")
        return weights


def _priority_level(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def normalize_pollution_score(average_pollution: float, reference_min: float, reference_max: float) -> float:
    """Normalize actual run pollution statistics to 0-100 using log min-max."""
    if reference_max < reference_min:
        raise ValueError("Pollution reference maximum must be >= minimum.")
    if reference_max == reference_min:
        return 100.0 if reference_max > 0 else 0.0
    value = min(max(float(average_pollution), reference_min), reference_max)
    denominator = log1p(reference_max) - log1p(reference_min)
    return round(100.0 * (log1p(value) - log1p(reference_min)) / denominator, 2)


def score_hotspot(
    hotspot: Dict[str, Any],
    ecological_risk: Optional[float] = None,
    human_exposure: Optional[float] = None,
    cleanup_feasibility: Optional[float] = None,
    config: Optional[RecommendationConfig] = None,
    pollution_reference: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Score a hotspot without inventing external/contextual factor values."""
    config = config or RecommendationConfig()
    weights = config.resolved_weights()
    average_pollution = float(hotspot.get("average_pollution", 0.0))
    reference = pollution_reference or {"min": average_pollution, "max": average_pollution}
    pollution_score = normalize_pollution_score(average_pollution, reference["min"], reference["max"])
    density = min(100.0, max(0.0, float(hotspot.get("observation_count", 0)) / config.density_reference_count * 100))
    factor_scores = {
        "pollution_severity": {"score": pollution_score, "source": "NOAA-derived average_pollution", "normalization": "log1p min-max across selected detection run hotspot averages"},
        "observation_density": {"score": round(density, 2), "source": "NOAA-derived observation_count", "normalization": f"observation_count / {config.density_reference_count}, capped at 100; informational and not weighted"},
        "ecological_risk": {"score": ecological_risk, "source": "External/contextual input"},
        "human_exposure": {"score": human_exposure, "source": "External/contextual input"},
        "cleanup_feasibility": {"score": cleanup_feasibility, "source": "External/contextual input"},
    }
    missing = [name for name in CONTEXT_FIELDS if factor_scores[name]["score"] is None]
    base = {
        "hotspot": hotspot,
        "cluster": hotspot,
        "factor_scores": factor_scores,
        "weights": weights,
        "missing_external_factors": missing,
        "calculation_explanation": "Pollution uses log-scaled min-max normalization of actual average pollution values within the selected detection run. External factors are supplied by the caller and are not present in NOAA data.",
    }
    if missing:
        return {
            **base,
            "status": "context_required",
            "priority_score": None,
            "priority_level": "UNAVAILABLE",
            "factor_scores": factor_scores,
            "weighted_components": None,
            "weights": weights,
            "contributions": None,
            "recommendation": "Provide all external/contextual factors before calculating cleanup priority.",
            "recommended_action": "Provide all external/contextual factors before calculating cleanup priority.",
            "missing_external_factors": missing,
        }

    for name in CONTEXT_FIELDS:
        if not 0 <= factor_scores[name]["score"] <= 100:
            raise ValueError(f"{name} must be between 0 and 100.")
    weighted_components = {name: round(weights[name] * factor_scores[name]["score"], 2) for name in weights}
    priority_score = round(sum(weighted_components.values()), 2)
    priority_level = _priority_level(priority_score)
    action = ACTION_BY_LEVEL[priority_level]
    return {
        **base,
        "status": "calculated",
        "priority_score": priority_score,
        "priority_level": priority_level,
        "factor_scores": factor_scores,
        "weighted_components": weighted_components,
        "contributions": weighted_components,
        "recommendation": action,
        "recommended_action": action,
        "missing_external_factors": [],
    }