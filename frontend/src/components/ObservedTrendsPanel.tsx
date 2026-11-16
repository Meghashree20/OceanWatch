import { AlertTriangle, Activity, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import type { PollutionTrendAssessment, PollutionRiskLevel } from '@/lib/api/client';

const riskStyles: Record<PollutionRiskLevel, { badge: 'cyan' | 'teal' | 'warning' | 'error'; marker: string }> = {
  LOW: { badge: 'cyan', marker: '#06b6d4' },
  MEDIUM: { badge: 'teal', marker: '#14b8a6' },
  HIGH: { badge: 'warning', marker: '#f97316' },
  CRITICAL: { badge: 'error', marker: '#ef4444' },
};

function formatDate(value: string | null | undefined) {
  if (!value) return 'Unavailable';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Unavailable' : parsed.toLocaleString();
}

export function ObservedTrendsPanel({
  assessment,
  loading,
  error,
  onRefresh,
}: {
  assessment: PollutionTrendAssessment | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const trends = assessment?.trends ?? [];
  const highRiskCount = trends.filter((trend) => trend.risk_level === 'HIGH' || trend.risk_level === 'CRITICAL').length;
  const criticalCount = trends.filter((trend) => trend.risk_level === 'CRITICAL').length;

  return (
    <Card className="overflow-hidden border border-cyan-200 shadow-md">
      <CardHeader className="border-b border-cyan-100 bg-white px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-cyan-700" />
              <h2 className="text-lg font-bold text-navy-950">Observed pollution risk &amp; trend watch</h2>
              <Badge variant="cyan">Measured · not a forecast</Badge>
            </div>
            <p className="mt-1 text-xs text-ocean-600">
              Equal-length, adjacent observation windows. Risk bands use configured concentration thresholds; map filters do not change this system-wide assessment.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh assessment
          </Button>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            Unable to load observed trend assessment: {error}
          </div>
        )}
        {assessment && (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <RiskSummary level="LOW" count={trends.filter((trend) => trend.risk_level === 'LOW').length} />
            <RiskSummary level="MEDIUM" count={trends.filter((trend) => trend.risk_level === 'MEDIUM').length} />
            <RiskSummary level="HIGH" count={trends.filter((trend) => trend.risk_level === 'HIGH').length} />
            <RiskSummary level="CRITICAL" count={criticalCount} />
          </div>
        )}
        {loading && !assessment && <p className="text-sm text-ocean-600">Assessing available observation history…</p>}
        {!loading && assessment?.status === 'insufficient_data' && (
          <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Not enough recent measurements meet the configured minimum to assess a spatial cell. Missing observations are not treated as zero pollution.
          </p>
        )}
        {assessment?.data_freshness.status === 'stale' && (
          <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            Historical assessment only: the latest observation is {assessment.data_freshness.age_days} days old. New alerts are suppressed until fresher observations are available.
          </p>
        )}
        {!loading && assessment && assessment.status === 'ready' && (
          <>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ocean-700">
              <span><strong>High / critical cells:</strong> {highRiskCount}</span>
              <span><strong>Eligible cells:</strong> {assessment.coverage.recent_comparable_cells ?? trends.length}</span>
              <span><strong>Latest observation:</strong> {formatDate(assessment.latest_observation)}</span>
              <span className={assessment.data_freshness.status === 'stale' ? 'font-semibold text-red-700' : ''}>
                <strong>Data freshness:</strong> {assessment.data_freshness.status}
                {assessment.data_freshness.age_days === null ? '' : ` · ${assessment.data_freshness.age_days} days old`}
              </span>
              <span><strong>Comparison:</strong> {assessment.windows?.days_per_window ?? '—'} days per window</span>
              <span><strong>Excluded records:</strong> {assessment.coverage.excluded_observations ?? 0}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-xs">
                <thead>
                  <tr className="border-y border-ocean-100 bg-ocean-50 text-[11px] uppercase tracking-wide text-ocean-600">
                    <th className="px-3 py-2">Risk</th>
                    <th className="px-3 py-2">Location cell</th>
                    <th className="px-3 py-2">Observed mean</th>
                    <th className="px-3 py-2">Change vs prior</th>
                    <th className="px-3 py-2">Trend evidence</th>
                    <th className="px-3 py-2">Data quality</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ocean-100">
                  {trends.slice(0, 12).map((trend) => (
                    <tr key={`${trend.location.latitude}:${trend.location.longitude}`}>
                      <td className="px-3 py-3"><Badge variant={riskStyles[trend.risk_level].badge}>{trend.risk_level}</Badge></td>
                      <td className="px-3 py-3 font-mono">{trend.location.latitude.toFixed(2)}, {trend.location.longitude.toFixed(2)}°</td>
                      <td className="px-3 py-3">{trend.comparison.recent_mean_pieces_m3.toFixed(3)} pieces/m³</td>
                      <td className="px-3 py-3">
                        {trend.comparison.previous_mean_pieces_m3 === null
                          ? 'No comparable baseline'
                          : `${trend.comparison.absolute_change_pieces_m3?.toFixed(3)} pieces/m³ (${trend.comparison.relative_change === null ? '—' : `${(trend.comparison.relative_change * 100).toFixed(1)}%`})`}
                      </td>
                      <td className="px-3 py-3">
                        {trend.change_types.length ? trend.change_types.map((value) => value.replace(/_/g, ' ')).join(', ') : trend.trend_direction}
                        <div className="mt-1 text-[10px] text-ocean-500">
                          {trend.evidence.recent_observation_count} recent samples / {trend.evidence.recent_sampling_site_count} sites
                          {trend.evidence.previous_observation_count === null ? '' : ` · ${trend.evidence.previous_observation_count} prior samples`}
                        </div>
                      </td>
                      <td className="px-3 py-3 capitalize">{trend.evidence.data_quality}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {trends.length > 12 && <p className="text-xs text-ocean-500">Showing the 12 highest assessed cells.</p>}
          </>
        )}
        {assessment?.thresholds && (
          <p className="flex items-start gap-2 border-t border-ocean-100 pt-3 text-[11px] text-ocean-500">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Configured bands (pieces/m³): {Object.entries(assessment.thresholds).map(([level, threshold]) => `${level}: ${threshold}`).join(' · ')}.
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function RiskSummary({ level, count }: { level: PollutionRiskLevel; count: number }) {
  const style = riskStyles[level];
  return (
    <div className="flex items-center justify-between rounded-xl border border-ocean-100 bg-white px-4 py-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ocean-500">{level} observed-risk cells</p>
        <p className="mt-1 text-2xl font-bold text-navy-950">{count}</p>
      </div>
      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: style.marker }} />
    </div>
  );
}
