import {
  BarChart3,
  CalendarDays,
  ChevronDown,
  Clock3,
  Database,
  Gauge,
  MapPin,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type Forecast, type ForecastMetrics } from '@/lib/api/client';
import { useDashboardFilters } from '@/lib/dashboardFilters';

const performanceItems = [
  { label: 'MAE', description: 'Mean absolute error' },
  { label: 'RMSE', description: 'Root mean squared error' },
  { label: 'R²', description: 'Coefficient of determination' },
];

export function ForecastPage() {
  const { filters, setFilters } = useDashboardFilters();
  const [zones, setZones] = useState<string[]>([]);
  const [zone, setZone] = useState('');
  const [horizon, setHorizon] = useState(3);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [metrics, setMetrics] = useState<ForecastMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      oceanWatchApi.getModelMetrics().catch((requestError: Error) => { if (active) setMetricsError(requestError.message); return null; }),
      oceanWatchApi.getObservations({ limit: 1000 }).catch(() => null),
    ]).then(([modelMetrics, observations]) => {
      if (!active) return;
      if (modelMetrics) setMetrics(modelMetrics);
      const observationZones = observations?.data.map((observation) => observation.region).filter((value): value is string => Boolean(value)) ?? [];
      const availableZones = modelMetrics?.zones?.length ? modelMetrics.zones : [...new Set(observationZones)];
      setZones(availableZones);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!zones.length) return;
    if (filters.region === 'ALL') {
      setZone((current) => zones.includes(current) ? current : zones[0]);
    } else if (zones.includes(filters.region)) {
      setZone(filters.region);
      setError(null);
    } else {
      setZone('');
      setForecast(null);
      setError(`No trained forecast zone is available for ${filters.region}.`);
    }
  }, [filters.region, zones]);

  useEffect(() => {
    if (!zone) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    oceanWatchApi.getForecast(zone, horizon)
      .then((response) => { if (active) setForecast(response); })
      .catch((requestError: Error) => { if (active) { setForecast(null); setError(requestError.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [zone, horizon]);

  const latestObserved = forecast?.historical_values[forecast.historical_values.length - 1]?.value;
  const latestForecast = forecast?.predicted_values[forecast.predicted_values.length - 1]?.value;
  const change = latestObserved && latestForecast ? ((latestForecast - latestObserved) / latestObserved) * 100 : null;
  const evaluationMetrics = getXgboostMetrics(forecast?.model_metrics ?? metrics?.metrics);
  const usesXgboost = Boolean(forecast && !forecast.message.toLowerCase().includes('persistence baseline'));

  return (
    <div>
      <PageHeader
        title="Pollution Forecast"
        description="Review historical pollution patterns and prepare for future concentration estimates from the backend forecasting model."
      >
          <Badge variant="neutral">{metrics ? 'Model ready' : metricsError ? 'Model metrics unavailable' : 'Loading model status'}</Badge>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <Card className="overflow-hidden border-navy-800 bg-navy-950 text-white">
          <CardBody className="p-5 sm:p-6">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300">
                  <SlidersHorizontal className="h-3.5 w-3.5" /> Forecast controls
                </div>
                <p className="mt-2 text-sm text-ocean-300">Choose the context for the next model run.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 xl:flex-1 xl:pl-8">
                <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-ocean-300">Region</span><span className="relative block"><MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" /><select value={zone} onChange={(event) => { setZone(event.target.value); setFilters((current) => ({ ...current, region: event.target.value || 'ALL' })); }} disabled={!zones.length} className="w-full appearance-none rounded-lg border border-navy-700 bg-navy-900 py-2.5 pl-9 pr-9 text-sm text-white outline-none focus:border-cyan-400"><option value="">{zones.length ? 'Select a region' : 'No model zones available'}</option>{zones.map((availableZone) => <option key={availableZone} value={availableZone}>{availableZone}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" /></span></label>
                <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-ocean-300">Forecast horizon</span><span className="relative block"><Clock3 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" /><select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} className="w-full appearance-none rounded-lg border border-navy-700 bg-navy-900 py-2.5 pl-9 pr-9 text-sm text-white outline-none focus:border-cyan-400"><option value={3}>3 periods</option><option value={6}>6 periods</option><option value={12}>12 periods</option></select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" /></span></label>
                <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5 text-sm text-ocean-300"><CalendarDays className="mr-2 inline h-4 w-4 text-cyan-300" />Monthly aggregation</div>
                <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5 text-sm text-ocean-300"><SlidersHorizontal className="mr-2 inline h-4 w-4 text-cyan-300" />Backend model output</div>
              </div>
            </div>
          </CardBody>
        </Card>

        {(filters.startDate || filters.endDate || filters.ocean !== 'ALL') && (
          <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-xs leading-5 text-sky-900">
            Forecasts use the trained region-month model output. The forecast endpoint accepts a region zone and horizon, but does not support date-range or ocean filters.
          </div>
        )}

        <div className="mt-8 grid gap-6 xl:grid-cols-[1.45fr_0.55fr]">
          <Card>
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                      <TrendingUp className="h-4 w-4" />
                    </div>
                    <h2 className="text-base font-bold text-navy-950">Actual Pollution vs Predicted Pollution</h2>
                  </div>
                  <p className="mt-2 text-sm text-ocean-500">{forecast ? `Observed and predicted concentration for ${forecast.zone}.` : 'Observed and forecasted concentration will appear here when a backend model output is available.'}</p>
                </div>
                <Badge variant="cyan">{loading ? 'Loading' : forecast ? 'Live API data' : 'Data unavailable'}</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <ForecastChart forecast={forecast} error={error} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-700">
                  <Gauge className="h-4 w-4" />
                </div>
                <h2 className="text-base font-bold text-navy-950">Forecast summary</h2>
              </div>
            </CardHeader>
            <CardBody className="pt-5">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                {[
                  { label: 'Latest observed concentration', value: latestObserved?.toFixed(2) ?? '—', detail: forecast ? 'Latest historical value' : 'No forecast loaded', icon: Database },
                  { label: 'Forecasted concentration', value: latestForecast?.toFixed(2) ?? '—', detail: forecast ? 'Last predicted period' : 'No forecast loaded', icon: TrendingUp },
                  { label: 'Change %', value: change === null ? '—' : `${change.toFixed(1)}%`, detail: 'Last prediction vs latest observation', icon: BarChart3 },
                  { label: 'Forecast horizon', value: forecast ? `${forecast.horizon} periods` : '—', detail: forecast?.message ?? 'Model output unavailable', icon: Clock3 },
                ].map(({ label, value, detail, icon: Icon }) => (
                  <div key={label} className="rounded-xl border border-ocean-100 bg-ocean-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs font-medium leading-5 text-ocean-500">{label}</p>
                      <Icon className="h-4 w-4 shrink-0 text-cyan-600" />
                    </div>
                    <p className="mt-2 font-display text-2xl font-bold text-navy-950">{value}</p>
                    <p className="mt-1 text-[11px] text-ocean-500">{detail}</p>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
                    <BarChart3 className="h-4 w-4" />
                  </div>
                  <h2 className="text-base font-bold text-navy-950">Model performance</h2>
                </div>
                <Badge variant={evaluationMetrics ? 'cyan' : 'neutral'}>{evaluationMetrics ? 'Validated evaluation' : 'Evaluation unavailable'}</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 gap-3">
                {performanceItems.map(({ label, description }) => (
                  <div key={label} className="border-l-2 border-cyan-200 pl-3">
                    <p className="font-display text-2xl font-bold text-navy-950">{metricValue(evaluationMetrics, label) ?? '—'}</p>
                    <p className="mt-1 text-sm font-semibold text-navy-800">{label}</p>
                    <p className="mt-1 text-[11px] leading-4 text-ocean-500">{description}</p>
                  </div>
                ))}
              </div>
              <p className="mt-6 border-t border-ocean-100 pt-4 text-xs leading-5 text-ocean-500">
                {evaluationMetrics
                  ? 'Metrics are reported by the backend model evaluation output and are not estimates.'
                  : 'The API did not provide genuine XGBoost evaluation metrics for this model output.'}
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                  <Sparkles className="h-4 w-4" />
                </div>
                <h2 className="text-base font-bold text-navy-950">Feature importance</h2>
              </div>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <p className="text-sm leading-6 text-ocean-500">The forecasting endpoint exposes predictions and evaluation metrics, but does not expose feature-importance values or confidence intervals. Those values are not fabricated here.</p>
              </div>
              <p className="mt-5 text-xs leading-5 text-ocean-500">Relative importance values will be supplied by the fitted XGBoost model.</p>
            </CardBody>
          </Card>
        </div>

        <Card className="mt-6 bg-ocean-950 text-white">
          <CardBody className="p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-400/15 text-cyan-300">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-cyan-300">Model workflow</p>
                <h2 className="mt-2 text-2xl font-bold text-white">How the forecast is produced</h2>
                <div className="mt-6 flex flex-wrap items-center gap-2 text-sm font-medium text-ocean-100">
                  {['Historical observations', 'Temporal aggregation', 'Feature engineering', usesXgboost ? 'XGBoost' : 'Persistence baseline', 'Forecast'].map((step, index, steps) => (
                    <span key={step} className="flex items-center gap-2">
                      <span className="rounded-lg border border-ocean-700 bg-ocean-900 px-3 py-2">{step}</span>
                      {index < steps.length - 1 && <span className="text-cyan-300" aria-hidden="true">→</span>}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function getXgboostMetrics(metrics: Record<string, unknown> | null | undefined) {
  if (!metrics || typeof metrics.xgboost !== 'object' || metrics.xgboost === null) return null;
  return metrics.xgboost as Record<string, unknown>;
}

function metricValue(metrics: Record<string, unknown> | null, label: string) {
  if (!metrics) return null;
  const key = label === 'R²' ? 'r2' : label.toLowerCase();
  const value = metrics[key] ?? metrics[label];
  return typeof value === 'number' ? value.toFixed(3) : typeof value === 'string' ? value : null;
}

function ForecastChart({ forecast, error }: { forecast: Forecast | null; error: string | null }) {
  const allPoints = useMemo(() => [
    ...(forecast?.historical_values ?? []).map((point) => ({ ...point, series: 'historical' as const })),
    ...(forecast?.predicted_values ?? []).map((point) => ({ ...point, series: 'predicted' as const })),
  ], [forecast]);
  const [rangePreset, setRangePreset] = useState<'ALL' | 'RECENT_HALF' | 'RECENT_QUARTER'>('ALL');
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(Math.max(allPoints.length - 1, 0));
  const [showHistorical, setShowHistorical] = useState(true);
  const [showPredicted, setShowPredicted] = useState(true);
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<number | null>(null);

  useEffect(() => {
    setRangePreset('ALL');
    setStartIndex(0);
    setEndIndex(Math.max(allPoints.length - 1, 0));
    setHoveredPoint(null);
    setSelectedPoint(null);
    setShowHistorical(true);
    setShowPredicted(true);
  }, [forecast?.zone, forecast?.horizon, allPoints.length]);

  const visiblePoints = useMemo(() => {
    if (!allPoints.length) return [];
    return allPoints.slice(
      Math.max(0, Math.min(startIndex, allPoints.length - 1)),
      Math.min(allPoints.length, Math.max(startIndex + 1, endIndex + 1)),
    );
  }, [allPoints, startIndex, endIndex]);
  const maxValue = Math.max(...visiblePoints.map((point) => point.value), 0);
  const minValue = Math.min(...visiblePoints.map((point) => point.value), 0);
  const valueRange = maxValue - minValue || 1;
  const toPoint = (point: typeof allPoints[number], index: number) => {
    const x = visiblePoints.length === 1 ? 50 : (index / (visiblePoints.length - 1)) * 100;
    const y = 92 - ((point.value - minValue) / valueRange) * 78;
    return `${x},${y}`;
  };
  const historicalPoints = visiblePoints.filter((point) => point.series === 'historical');
  const predictedPoints = visiblePoints.filter((point) => point.series === 'predicted');
  const historicalPath = historicalPoints.map((point) => toPoint(point, visiblePoints.indexOf(point))).join(' ');
  const predictedPath = [
    ...(historicalPoints.length > 0 && predictedPoints.length > 0 ? [historicalPoints[historicalPoints.length - 1]] : []),
    ...predictedPoints,
  ].map((point) => toPoint(point, visiblePoints.indexOf(point))).join(' ');
  const hovered = hoveredPoint === null ? null : visiblePoints[hoveredPoint] ?? null;
  const selected = selectedPoint === null ? null : visiblePoints[selectedPoint] ?? null;
  const reset = () => {
    setRangePreset('ALL');
    setStartIndex(0);
    setEndIndex(Math.max(allPoints.length - 1, 0));
    setHoveredPoint(null);
    setSelectedPoint(null);
    setShowHistorical(true);
    setShowPredicted(true);
  };
  const setRange = (preset: typeof rangePreset) => {
    setRangePreset(preset);
    setSelectedPoint(null);
    const total = allPoints.length;
    const start = preset === 'RECENT_HALF' ? Math.floor(total * 0.5) : preset === 'RECENT_QUARTER' ? Math.floor(total * 0.75) : 0;
    setStartIndex(start);
    setEndIndex(Math.max(total - 1, 0));
  };
  const zoom = (direction: 'in' | 'out') => {
    if (!allPoints.length) return;
    setSelectedPoint(null);
    const span = endIndex - startIndex;
    if (direction === 'in' && span > 3) {
      const delta = Math.max(1, Math.floor(span * 0.2));
      setStartIndex((value) => Math.min(value + delta, endIndex - 3));
      setEndIndex((value) => Math.max(value - delta, startIndex + 3));
    } else if (direction === 'out') {
      const delta = Math.max(1, Math.floor(span * 0.25));
      setStartIndex((value) => Math.max(0, value - delta));
      setEndIndex((value) => Math.min(allPoints.length - 1, value + delta));
    }
    setRangePreset('ALL');
  };
  const setDateBound = (value: string, bound: 'start' | 'end') => {
    if (!value || !allPoints.length) return;
    setSelectedPoint(null);
    setRangePreset('ALL');
    if (bound === 'start') {
      const index = allPoints.findIndex((point) => point.date >= value);
      if (index >= 0) setStartIndex(Math.min(index, endIndex));
    } else {
      let index = -1;
      allPoints.forEach((point, pointIndex) => {
        if (point.date <= value) index = pointIndex;
      });
      if (index >= 0) setEndIndex(Math.max(index, startIndex));
    }
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-ocean-200 bg-ocean-50 p-4 sm:h-[25rem]">
      <div className="absolute inset-0 grid-pattern opacity-60" />
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 text-[10px] font-medium uppercase tracking-wider text-ocean-400">
        <span>{forecast ? 'Historical period' : 'Forecast unavailable'}</span>
        <span>{forecast ? 'Forecast horizon' : ''}</span>
      </div>
      {forecast && (
        <div className="relative z-10 mt-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            {([
              ['ALL', 'All'],
              ['RECENT_HALF', 'Recent 50%'],
              ['RECENT_QUARTER', 'Recent 25%'],
            ] as const).map(([preset, label]) => (
              <button key={preset} type="button" onClick={() => setRange(preset)} className={`rounded border px-2 py-1 text-[10px] font-semibold ${rangePreset === preset ? 'border-cyan-500 bg-cyan-100 text-cyan-900' : 'border-ocean-200 bg-white/80 text-ocean-600 hover:bg-white'}`}>
                {label}
              </button>
            ))}
            <button type="button" onClick={() => zoom('in')} disabled={endIndex - startIndex <= 3} className="rounded border border-ocean-200 bg-white/80 px-2 py-1 text-[10px] font-semibold text-ocean-600 hover:bg-white disabled:opacity-40">Zoom +</button>
            <button type="button" onClick={() => zoom('out')} disabled={startIndex === 0 && endIndex === allPoints.length - 1} className="rounded border border-ocean-200 bg-white/80 px-2 py-1 text-[10px] font-semibold text-ocean-600 hover:bg-white disabled:opacity-40">Zoom −</button>
            <button type="button" onClick={reset} className="rounded border border-ocean-200 bg-white/80 px-2 py-1 text-[10px] font-semibold text-ocean-600 hover:bg-white">Reset</button>
          </div>
          <span className="font-mono normal-case">{visiblePoints.length} points</span>
        </div>
      )}
      {forecast && visiblePoints.length > 0 && (
        <div className="relative z-10 mt-2 grid grid-cols-2 gap-2 sm:flex sm:items-center">
          <label className="flex min-w-0 items-center gap-2 text-[10px] font-semibold text-ocean-600">
            <span>From</span>
            <input
              type="date"
              aria-label="Forecast chart start date"
              min={allPoints[0]?.date}
              max={visiblePoints[visiblePoints.length - 1]?.date}
              value={visiblePoints[0]?.date ?? ''}
              onChange={(event) => setDateBound(event.target.value, 'start')}
              className="min-w-0 rounded border border-ocean-200 bg-white px-2 py-1 font-mono text-[10px] text-ocean-700"
            />
          </label>
          <label className="flex min-w-0 items-center gap-2 text-[10px] font-semibold text-ocean-600">
            <span>To</span>
            <input
              type="date"
              aria-label="Forecast chart end date"
              min={visiblePoints[0]?.date}
              max={allPoints[allPoints.length - 1]?.date}
              value={visiblePoints[visiblePoints.length - 1]?.date ?? ''}
              onChange={(event) => setDateBound(event.target.value, 'end')}
              className="min-w-0 rounded border border-ocean-200 bg-white px-2 py-1 font-mono text-[10px] text-ocean-700"
            />
          </label>
        </div>
      )}
      <svg className="relative z-0 mt-2 h-52 w-full sm:h-60" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Historical and predicted pollution values" onMouseLeave={() => setHoveredPoint(null)}>
        {forecast && <>
          {showHistorical && <polyline points={historicalPath} fill="none" stroke="#2d5868" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />}
          {showPredicted && <polyline points={predictedPath} fill="none" stroke="#06b6d4" strokeWidth="1.5" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />}
          {visiblePoints.map((point, index) => {
            const [x, y] = toPoint(point, index).split(',');
            const isVisible = point.series === 'historical' ? showHistorical : showPredicted;
            if (!isVisible) return null;
            return (
              <g key={`${point.series}-${point.date}-${index}`}>
                <circle cx={x} cy={y} r={selectedPoint === index ? 3 : hoveredPoint === index ? 2.5 : 1.5} fill={point.series === 'historical' ? '#2d5868' : '#06b6d4'} stroke="white" strokeWidth="0.8" vectorEffect="non-scaling-stroke" />
                <rect
                  x={Number(x) - 4}
                  y="5"
                  width="8"
                  height="90"
                  fill="transparent"
                  className="cursor-pointer outline-none focus-visible:stroke-cyan-600 focus-visible:stroke-1"
                  role="button"
                  tabIndex={0}
                  aria-label={`Inspect ${point.series === 'historical' ? 'actual' : 'predicted'} pollution on ${point.date}: ${point.value.toFixed(3)} pieces per cubic meter`}
                  onMouseEnter={() => setHoveredPoint(index)}
                  onFocus={() => setHoveredPoint(index)}
                  onBlur={() => setHoveredPoint(null)}
                  onClick={() => setSelectedPoint(index)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedPoint(index);
                    }
                  }}
                >
                  <title>{`${point.series === 'historical' ? 'Actual' : 'Predicted'} · ${point.date} · ${point.value.toFixed(3)} pieces/m³`}</title>
                </rect>
              </g>
            );
          })}
        </>}
      </svg>
      {forecast && (
        <div className="relative z-10 flex flex-wrap gap-2 text-[11px] text-ocean-600">
          <button type="button" onClick={() => setShowHistorical((value) => !value)} className={`flex items-center gap-1.5 rounded px-1.5 py-1 ${showHistorical ? '' : 'opacity-40 line-through'}`}><span className="h-1.5 w-5 rounded-full bg-ocean-700" />Actual pollution</button>
          <button type="button" onClick={() => setShowPredicted((value) => !value)} className={`flex items-center gap-1.5 rounded px-1.5 py-1 ${showPredicted ? '' : 'opacity-40 line-through'}`}><span className="h-1.5 w-5 rounded-full border-t-2 border-dashed border-cyan-500" />Predicted pollution</button>
          <span className="ml-auto text-[10px] text-ocean-400">Hover a point for date and value</span>
        </div>
      )}
      {forecast && forecast.message.toLowerCase().includes('persistence baseline') && (
        <p className="relative z-10 mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-900">
          This zone is shown with a persistence baseline because the backend did not find sufficient regional XGBoost reliability. The values are not an XGBoost forecast.
        </p>
      )}
      {(hovered || selected) && (
        <div className="relative z-10 mt-2 rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-xs text-white shadow-lg">
          <div className="flex items-center justify-between gap-4"><span className="font-semibold">{(selected ?? hovered)?.series === 'historical' ? 'Actual pollution' : 'Predicted pollution'}</span><span className="font-mono text-cyan-300">{(selected ?? hovered)?.date}</span></div>
          <p className="mt-1 font-mono text-ocean-200">{(selected ?? hovered)?.value.toFixed(3)} pieces/m³</p>
        </div>
      )}
      {!forecast && <span className="absolute left-1/2 top-1/2 max-w-sm -translate-x-1/2 rounded-lg border border-white bg-white/90 px-3 py-2 text-center text-xs font-medium text-ocean-600 shadow-card">{error ?? 'Forecast data is not currently available from the backend.'}</span>}
    </div>
  );
}
