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
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type Forecast, type ForecastMetrics } from '@/lib/api/client';

const performanceItems = [
  { label: 'MAE', description: 'Mean absolute error' },
  { label: 'MSE', description: 'Mean squared error' },
  { label: 'RMSE', description: 'Root mean squared error' },
  { label: 'R²', description: 'Coefficient of determination' },
];

export function ForecastPage() {
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
      setZone(availableZones[0] ?? '');
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!zone) return;
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

  return (
    <div>
      <PageHeader
        title="Pollution Forecast"
        description="Review historical pollution patterns and prepare for future concentration estimates from the XGBoost forecasting model."
      >
          <Badge variant="neutral">{metrics ? 'XGBoost regression · model ready' : metricsError ? 'XGBoost metrics unavailable' : 'Loading model status'}</Badge>
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
                <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-ocean-300">Region</span><span className="relative block"><MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" /><select value={zone} onChange={(event) => setZone(event.target.value)} disabled={!zones.length} className="w-full appearance-none rounded-lg border border-navy-700 bg-navy-900 py-2.5 pl-9 pr-9 text-sm text-white outline-none focus:border-cyan-400"><option value="">{zones.length ? 'Select a region' : 'No model zones available'}</option>{zones.map((availableZone) => <option key={availableZone} value={availableZone}>{availableZone}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" /></span></label>
                <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-ocean-300">Forecast horizon</span><span className="relative block"><Clock3 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" /><select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} className="w-full appearance-none rounded-lg border border-navy-700 bg-navy-900 py-2.5 pl-9 pr-9 text-sm text-white outline-none focus:border-cyan-400"><option value={3}>3 periods</option><option value={6}>6 periods</option><option value={12}>12 periods</option></select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" /></span></label>
                <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5 text-sm text-ocean-300"><CalendarDays className="mr-2 inline h-4 w-4 text-cyan-300" />Monthly aggregation</div>
                <div className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5 text-sm text-ocean-300"><SlidersHorizontal className="mr-2 inline h-4 w-4 text-cyan-300" />Backend model output</div>
              </div>
            </div>
          </CardBody>
        </Card>

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
                <Badge variant="neutral">Pending evaluation</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 gap-3">
                {performanceItems.map(({ label, description }) => (
                  <div key={label} className="border-l-2 border-cyan-200 pl-3">
                    <p className="font-display text-2xl font-bold text-navy-950">{metricValue(forecast?.model_metrics ?? metrics?.metrics, label) ?? '—'}</p>
                    <p className="mt-1 text-sm font-semibold text-navy-800">{label}</p>
                    <p className="mt-1 text-[11px] leading-4 text-ocean-500">{description}</p>
                  </div>
                ))}
              </div>
              <p className="mt-6 border-t border-ocean-100 pt-4 text-xs leading-5 text-ocean-500">
                Metrics will be populated from the validated model evaluation output. No performance values are estimated here.
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
                <p className="text-sm leading-6 text-ocean-500">The forecasting endpoint exposes predictions and aggregate model metrics, but does not expose feature-importance values. This section is therefore unavailable without inventing results.</p>
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
                <h2 className="mt-2 text-2xl font-bold text-white">How XGBoost Forecasting Works</h2>
                <div className="mt-6 flex flex-wrap items-center gap-2 text-sm font-medium text-ocean-100">
                  {['Historical observations', 'Temporal aggregation', 'Feature engineering', 'XGBoost', 'Forecast'].map((step, index, steps) => (
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

function metricValue(metrics: Record<string, unknown> | null | undefined, label: string) {
  if (!metrics) return null;
  const key = label === 'R²' ? 'r2' : label.toLowerCase();
  const value = metrics[key] ?? metrics[label];
  return typeof value === 'number' ? value.toFixed(3) : typeof value === 'string' ? value : null;
}

function ForecastChart({ forecast, error }: { forecast: Forecast | null; error: string | null }) {
  const points = [...(forecast?.historical_values ?? []), ...(forecast?.predicted_values ?? [])];
  const maxValue = Math.max(...points.map((point) => point.value), 0);
  const minValue = Math.min(...points.map((point) => point.value), 0);
  const valueRange = maxValue - minValue || 1;
  const toPoint = (point: { date: string; value: number }, index: number) => {
    const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
    const y = 92 - ((point.value - minValue) / valueRange) * 78;
    return `${x},${y}`;
  };
  const historicalCount = forecast?.historical_values.length ?? 0;
  const historicalPath = forecast?.historical_values.map((point, index) => toPoint(point, index)).join(' ') ?? '';
  const predictedPath = forecast?.predicted_values.map((point, index) => toPoint(point, historicalCount + index)).join(' ') ?? '';

  return (
    <div className="relative h-[18rem] overflow-hidden rounded-xl border border-ocean-200 bg-ocean-50 p-4 sm:h-[22rem]">
      <div className="absolute inset-0 grid-pattern opacity-60" />
      <div className="absolute inset-x-4 top-4 flex justify-between text-[10px] font-medium uppercase tracking-wider text-ocean-400">
        <span>{forecast ? 'Historical period' : 'Forecast unavailable'}</span>
        <span>{forecast ? 'Forecast horizon' : ''}</span>
      </div>
      <svg className="absolute inset-x-0 bottom-10 h-[68%] w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Historical and predicted pollution values">
        {forecast && <><polyline points={historicalPath} fill="none" stroke="#2d5868" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /><polyline points={predictedPath} fill="none" stroke="#06b6d4" strokeWidth="1.5" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" /></>}
      </svg>
      <div className="absolute bottom-4 left-4 flex flex-wrap gap-4 text-[11px] text-ocean-600">
        {forecast && <><span className="flex items-center gap-1.5"><span className="h-1.5 w-5 rounded-full bg-ocean-700" />Actual pollution</span><span className="flex items-center gap-1.5"><span className="h-1.5 w-5 rounded-full border-t-2 border-dashed border-cyan-500" />Predicted pollution</span></>}
      </div>
      {!forecast && <span className="absolute left-1/2 top-1/2 max-w-sm -translate-x-1/2 rounded-lg border border-white bg-white/90 px-3 py-2 text-center text-xs font-medium text-ocean-600 shadow-card">{error ?? 'Forecast data is not currently available from the backend.'}</span>}
    </div>
  );
}
