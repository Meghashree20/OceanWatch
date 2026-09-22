# Model 3: Cleanup Priority Decision Engine

## Objective

Provide a transparent cleanup-priority decision aid for a detected hotspot. This is
a rule-based calculation, not another machine-learning model, and it does not claim
that a location is in an actual emergency condition.

## Separate data sources

### NOAA-derived factors

These values come from stored hotspot statistics generated from NOAA observations:

- `pollution_severity`: normalized from the hotspot's `average_pollution`
- `observation_density`: derived from `observation_count`
- pollution concentration statistics included in the hotspot record

### External/contextual factors

These values are not present in the NOAA dataset and must be supplied by the caller:

- `ecological_risk`: 0 to 100
- `human_exposure`: 0 to 100
- `cleanup_feasibility`: 0 to 100

The API never fills missing contextual values with defaults. A calculation without
all three values returns `status=context_required` and lists the missing factors.

## Pollution normalization

The pollution factor is calculated from actual hotspot statistics in the selected
detection run. Let $p$ be the hotspot's `average_pollution`, and let $p_{min}$ and
$p_{max}$ be the minimum and maximum `average_pollution` across that run's stored
hotspots.

```text
log_min = log(1 + p_min)
log_max = log(1 + p_max)
log_value = log(1 + clamp(p, p_min, p_max))

pollution_severity = 100 * (log_value - log_min) / (log_max - log_min)
```

The log transform reduces the influence of the highly right-skewed concentration
range. The score is clamped to 0-100. If all hotspots have the same positive average,
the score is 100; if all are zero, it is 0. This normalization uses observed run
statistics rather than undocumented severity thresholds.

Observation density is also returned transparently as:

```text
min(100, observation_count / 100 * 100)
```

It is informational and is not included in the weighted score because the required
weights already sum to 1 and do not assign density a weight.

## Priority formula

The configured weights are validated to sum to exactly 1.0:

```text
pollution_severity = 0.40
ecological_risk = 0.25
human_exposure = 0.20
cleanup_feasibility = 0.15
```

```text
priority_score =
    0.40 * pollution_severity
  + 0.25 * ecological_risk
  + 0.20 * human_exposure
  + 0.15 * cleanup_feasibility
```

The weighted sum is already normalized to 0-100 because each factor is 0-100 and the
weights sum to 1. Every contribution is returned separately so the calculation can
be audited.

Priority levels:

- 0-25: LOW, `Monitor`
- 26-50: MEDIUM, `Schedule further assessment`
- 51-75: HIGH, `Prioritize cleanup assessment`
- 76-100: CRITICAL, `Immediate cleanup assessment`

These actions are cautious planning recommendations, not claims of confirmed danger
or emergency conditions.

## API

Calculate an exact run-scoped recommendation:

```http
POST /api/recommendations/calculate
Content-Type: application/json
```

```json
{
  "cluster_id": 0,
  "detection_run_id": "952ac33e23984f31811af08639a52852",
  "ecological_risk": 80,
  "human_exposure": 60,
  "cleanup_feasibility": 40
}
```

When one or more contextual fields are omitted, the same endpoint returns HTTP 200
with `status=context_required`, `priority_score=null`, and
`missing_external_factors`. It never substitutes a default value. With all three
fields present, the response includes:

- `status`
- `hotspot`
- `factor_scores` and data sources
- `weights`
- `contributions`
- `priority_score`
- `priority_level`
- `recommendation`
- `calculation_explanation`

Existing GET recommendation endpoints remain available for compatibility. Complete
scores require the same three contextual values; without them they return
`context_required` and do not produce a priority score.

## Limitations

- Contextual factors are user-supplied and require domain-appropriate provenance.
- Pollution scores are relative to the selected detection run, not universal risk
  thresholds.
- Observation density reflects sampling density, not continuous environmental
  coverage.
- Recommendations support prioritization and assessment planning; they do not replace
  ecological, public-health, engineering, or emergency evaluation.
