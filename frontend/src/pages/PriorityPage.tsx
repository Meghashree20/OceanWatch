import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Info,
  MapPin,
  ShieldCheck,
  Target,
  Waves,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type Recommendation } from '@/lib/api/client';

export function PriorityPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    oceanWatchApi.getPriorityResults()
      .then((response) => { if (active) { setRecommendations(response.data); setSelected(response.data[0] ?? null); } })
      .catch((requestError: Error) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const weights = selected?.weights ?? {};
  const scoringFactors = [
    { key: 'pollution_severity', label: 'Pollution Severity', color: 'bg-cyan-500', track: 'bg-cyan-100' },
    { key: 'ecological_risk', label: 'Ecological Risk', color: 'bg-teal-500', track: 'bg-teal-100' },
    { key: 'human_exposure', label: 'Human Exposure', color: 'bg-amber-400', track: 'bg-amber-100' },
    { key: 'cleanup_feasibility', label: 'Cleanup Feasibility', color: 'bg-navy-500', track: 'bg-navy-100' },
  ];

  const factorDetails = scoringFactors.map((factor) => ({
    ...factor,
    weight: weights[factor.key] === undefined ? '—' : `${(weights[factor.key] * 100).toFixed(0)}%`,
    value: scoreValue(selected?.factor_scores[factor.key]?.score),
    note: selected?.factor_scores[factor.key]?.source?.toString() ?? 'No recommendation selected',
  }));

  return (
    <div>
      <PageHeader
        title="Cleanup Priority Intelligence"
        description="Rank pollution locations using transparent, explainable priority scoring."
      >
        <Badge variant="neutral" icon={<Info className="h-3.5 w-3.5" />}>
          {loading ? 'Loading recommendation data' : error ? 'Recommendation data unavailable' : recommendations.length ? 'Backend recommendation results' : 'No recommendation results'}
        </Badge>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                      <Target className="h-4 w-4" />
                    </div>
                    <h2 className="text-base font-bold text-navy-950">Scoring framework</h2>
                  </div>
                  <p className="mt-2 max-w-xl text-sm leading-5 text-ocean-500">
                    Each factor contributes to a weighted score once validated contextual data is available.
                  </p>
                </div>
                <Badge variant="cyan">100% total</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="space-y-5">
                {scoringFactors.map(({ label, key, color, track }) => (
                  <div key={label}>
                    <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                      <span className="font-semibold text-navy-800">{label}</span>
                      <span className="font-mono text-xs font-semibold text-ocean-600">{weights[key] === undefined ? '—' : `${(weights[key] * 100).toFixed(0)}%`}</span>
                    </div>
                    <div className={`h-2.5 overflow-hidden rounded-full ${track}`}>
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${(weights[key] ?? 0) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex items-center justify-between border-t border-ocean-100 pt-4 text-sm">
                <span className="font-semibold text-navy-800">Total</span>
                <span className="font-mono font-bold text-navy-950">{selected ? `${Object.values(weights).reduce((sum, weight) => sum + weight, 0) * 100}%` : '—'}</span>
              </div>
            </CardBody>
          </Card>

          <Card className="bg-navy-950 text-white">
            <CardBody className="flex h-full flex-col justify-between p-6 sm:p-7">
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/15 text-cyan-300">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <h2 className="mt-5 text-2xl font-bold">A transparent score for action.</h2>
                  <p className="mt-3 text-sm leading-6 text-ocean-300">
                  Priority levels and scores are displayed exactly as returned by the existing recommendation service. Missing contextual inputs remain unavailable rather than being inferred here.
                </p>
              </div>
              <div className="mt-8 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((level, index) => (
                  <div key={level} className="flex items-center gap-2 rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5">
                    <span className={`h-2 w-2 rounded-full ${['bg-emerald-400', 'bg-amber-300', 'bg-orange-400', 'bg-red-400'][index]}`} />
                    <span className="text-[11px] font-semibold tracking-wide text-ocean-100">{level}</span>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.55fr_0.45fr]">
          <Card>
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-700">
                      <BarChart3 className="h-4 w-4" />
                    </div>
                    <h2 className="text-base font-bold text-navy-950">Priority ranking</h2>
                  </div>
                  <p className="mt-2 text-sm text-ocean-500">Locations and scores will populate from the connected scoring output.</p>
                </div>
                <Badge variant="neutral">Awaiting data</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[920px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-ocean-200 text-[10px] uppercase tracking-wider text-ocean-500">
                      <th className="pb-3 pr-4 font-semibold">Rank</th>
                      <th className="pb-3 pr-4 font-semibold">Location</th>
                      <th className="pb-3 pr-4 font-semibold">Pollution Severity</th>
                      <th className="pb-3 pr-4 font-semibold">Ecological Risk</th>
                      <th className="pb-3 pr-4 font-semibold">Human Exposure</th>
                      <th className="pb-3 pr-4 font-semibold">Cleanup Feasibility</th>
                      <th className="pb-3 pr-4 font-semibold">Priority Score</th>
                      <th className="pb-3 font-semibold">Priority Level</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recommendations.map((recommendation, index) => <RecommendationRow key={`${recommendation.cluster.cluster_id ?? index}`} recommendation={recommendation} rank={index + 1} onSelect={() => setSelected(recommendation)} />)}
                    {!loading && !error && recommendations.length === 0 && <tr><td colSpan={8} className="py-12 text-center text-sm text-ocean-500">No recommendation results are currently available.</td></tr>}
                    {error && <tr><td colSpan={8} className="py-12 text-center text-sm text-red-600">Unable to load recommendations: {error}</td></tr>}
                    {loading && <tr><td colSpan={8} className="py-12 text-center text-sm text-ocean-500">Loading recommendations...</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="mt-5 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-800">
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Ecological risk, human exposure, and cleanup feasibility are contextual inputs. No values are inferred without validated data.</span>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-cyan-600" />
                <h2 className="text-base font-bold text-navy-950">Priority levels</h2>
              </div>
            </CardHeader>
            <CardBody className="pt-5">
              <div className="space-y-2">
                {[
                  ['LOW', 'bg-emerald-100 text-emerald-800'],
                  ['MEDIUM', 'bg-amber-100 text-amber-800'],
                  ['HIGH', 'bg-orange-100 text-orange-800'],
                  ['CRITICAL', 'bg-red-100 text-red-800'],
                ].map(([level, classes]) => (
                  <div key={level} className={`flex items-center justify-between rounded-lg px-3 py-3 text-xs font-semibold ${classes}`}>
                    <span>{level}</span>
                    <span className="font-normal opacity-70">Threshold pending</span>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-xs leading-5 text-ocean-500">Level thresholds will be defined with the scoring implementation and validated domain inputs.</p>
            </CardBody>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-100 text-navy-700">
                  <ChevronRight className="h-4 w-4" />
                </div>
                <h2 className="text-base font-bold text-navy-950">Selected location</h2>
              </div>
            </CardHeader>
            <CardBody>
              <div className="rounded-xl border border-dashed border-ocean-300 bg-ocean-50 p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-cyan-700">{selected ? `Cluster ${selected.cluster.cluster_id ?? '—'}` : 'No location selected'}</p>
                <p className="mt-2 text-sm leading-5 text-ocean-600">{selected?.calculation_explanation ?? 'Select a ranked location when recommendation data is available to inspect its decision context.'}</p>
              </div>
              <div className="mt-5 space-y-4">
                <DetailRow label="Overall score" value={scoreValue(selected?.priority_score)} />
                <DetailRow label="Reason for ranking" value={selected?.recommendation ?? '—'} />
                <DetailRow label="Recommended action" value={selected?.recommended_action ?? '—'} />
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                  <Waves className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-navy-950">Weighted score breakdown</h2>
                  <p className="mt-1 text-xs text-ocean-500">Selected location contribution view</p>
                </div>
              </div>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                {factorDetails.map(({ label, weight, value, note }, index) => (
                  <div key={label}>
                    <div className="mb-1.5 flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-navy-800">{label}</span>
                      <span className="font-mono text-xs text-ocean-500">{weight} · {value}</span>
                    </div>
                    <div className="h-2 rounded-full bg-ocean-100">
                      <div className={`h-full rounded-full ${['bg-cyan-400', 'bg-teal-400', 'bg-amber-300', 'bg-navy-400'][index]} opacity-60`} style={{ width: weight }} />
                    </div>
                    <p className="mt-1 text-[11px] text-ocean-400">{note}</p>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        <Card className="mt-6 bg-ocean-950 text-white">
          <CardBody className="p-6 sm:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-2xl">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300">
                  <CheckCircle2 className="h-4 w-4" /> Decision support method
                </div>
                <h2 className="mt-3 text-2xl font-bold">How Priority Is Calculated</h2>
                <p className="mt-3 text-sm leading-6 text-ocean-300">
                  Each location receives a transparent weighted score from pollution severity, ecological risk, human exposure, and cleanup feasibility. The final score maps to a priority level for action planning.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2 text-sm font-medium text-ocean-100">
                <span className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2">Validated inputs</span>
                <ArrowRight className="h-4 w-4 text-cyan-300" />
                <span className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2">Weighted score</span>
                <ArrowRight className="h-4 w-4 text-cyan-300" />
                <span className="rounded-lg border border-navy-700 bg-navy-900 px-3 py-2">Priority level</span>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-ocean-100 pb-3 last:border-0 last:pb-0">
      <span className="text-xs font-medium text-ocean-500">{label}</span>
      <span className="text-right text-sm font-medium text-navy-800">{value}</span>
    </div>
  );
}

function scoreValue(value: unknown) {
  return typeof value === 'number' ? value.toFixed(2) : '—';
}

function RecommendationRow({ recommendation, rank, onSelect }: { recommendation: Recommendation; rank: number; onSelect: () => void }) {
  const factor = (name: string) => scoreValue(recommendation.factor_scores[name]?.score);
  const cluster = recommendation.cluster;
  const location = [cluster.region, cluster.ocean].filter((value): value is string => typeof value === 'string' && value.length > 0).join(' · ') || `Cluster ${cluster.cluster_id ?? '—'}`;
  return <tr className="cursor-pointer border-b border-ocean-100 last:border-0 hover:bg-ocean-50" onClick={onSelect}>
    <td className="py-4 pr-4 font-mono text-xs text-ocean-500">{String(rank).padStart(2, '0')}</td>
    <td className="py-4 pr-4 font-medium text-navy-800">{location}</td>
    <td className="py-4 pr-4 text-ocean-500">{factor('pollution_severity')}</td>
    <td className="py-4 pr-4 text-ocean-500">{factor('ecological_risk')}</td>
    <td className="py-4 pr-4 text-ocean-500">{factor('human_exposure')}</td>
    <td className="py-4 pr-4 text-ocean-500">{factor('cleanup_feasibility')}</td>
    <td className="py-4 pr-4 font-mono text-ocean-500">{scoreValue(recommendation.priority_score)}</td>
    <td className="py-4"><Badge variant={recommendation.priority_level === 'UNAVAILABLE' ? 'neutral' : 'cyan'}>{recommendation.priority_level}</Badge></td>
  </tr>;
}
