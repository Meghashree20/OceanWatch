import {
  Activity,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Database,
  Map,
  Radar,
  ShieldCheck,
  Target,
  TrendingUp,
  Waves,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type Hotspot, type PollutionObservation, type Recommendation } from '@/lib/api/client';

export function IntelligencePage() {
  const [observations, setObservations] = useState<PollutionObservation[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [totalObservations, setTotalObservations] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      oceanWatchApi.getSummaryStatistics(),
      oceanWatchApi.getHotspots({ limit: 500 }),
      oceanWatchApi.getPriorityResults(),
      oceanWatchApi.getObservations({ limit: 10 }),
    ]).then(([dataStats, hotspotResponse, recommendationResponse, observationResponse]) => {
      if (!active) return;
      setTotalObservations(dataStats.total_observations);
      setHotspots(hotspotResponse.data);
      setRecommendations(recommendationResponse.data);
      setObservations(observationResponse.data);
    }).catch((requestError: Error) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, []);

  const highestConcentration = observations.reduce((highest, observation) => Math.max(highest, observation.measurement), 0);
  const criticalCount = recommendations.filter((recommendation) => recommendation.priority_level === 'CRITICAL').length;
  const metrics = [
    { label: 'Total observations', value: totalObservations === null ? '—' : totalObservations.toLocaleString(), detail: error ?? 'From data statistics endpoint', icon: Database },
    { label: 'Detected hotspots', value: hotspots.length ? hotspots.length.toLocaleString() : '—', detail: 'Returned hotspot clusters', icon: Radar },
    { label: 'Highest concentration', value: highestConcentration ? highestConcentration.toFixed(2) : '—', detail: observations.length ? 'Loaded observations' : 'No observations loaded', icon: TrendingUp },
    { label: 'Critical priority locations', value: recommendations.length ? criticalCount.toLocaleString() : '—', detail: recommendations.length ? 'Backend recommendation results' : 'No recommendation results', icon: Target },
  ];
  return (
    <div>
      <PageHeader
        title="OceanWatch Intelligence"
        description="A high-level command center for marine pollution observations, emerging hotspots, forecast signals, and cleanup priorities."
      >
        <Badge variant="neutral" icon={<Activity className="h-3.5 w-3.5" />}>Unified intelligence layer · live data pending</Badge>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map(({ label, value, detail, icon: Icon }) => (
            <Card key={label}>
              <CardBody className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium text-ocean-500">{label}</p>
                    <p className="mt-3 font-display text-3xl font-bold text-navy-950">{value}</p>
                    <p className="mt-2 text-[11px] leading-4 text-ocean-500">{detail}</p>
                  </div>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700"><Icon className="h-4 w-4" /></div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>

        <div className="mt-8 grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700"><Waves className="h-4 w-4" /></div>
                    <h2 className="text-base font-bold text-navy-950">Marine Pollution Overview</h2>
                  </div>
                  <p className="mt-2 text-sm text-ocean-500">A compact view of where observation coverage and pollution signals will be summarized.</p>
                </div>
                <Badge variant="cyan">Overview</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="grid gap-4 md:grid-cols-[1.25fr_0.75fr]">
                <OverviewMap observations={observations} />
                <div className="space-y-3">
                  <SignalRow label="Observation coverage" value="—" note="Pending records" />
                  <SignalRow label="Spatial signal" value="—" note="Pending hotspot run" />
                  <SignalRow label="Current data status" value="Pending" note="FastAPI connection" />
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2"><Map className="h-4 w-4 text-cyan-600" /><h2 className="text-base font-bold text-navy-950">Interactive Hotspot Map</h2></div>
                <Badge variant="neutral">Preview</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <HotspotPreview hotspots={hotspots} />
              <div className="mt-4 flex justify-end"><Button to="/hotspots" variant="ghost" size="sm">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button></div>
            </CardBody>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-teal-600" /><h2 className="text-base font-bold text-navy-950">Pollution Trend</h2></div><Badge variant="neutral">Signal preview</Badge></div>
            </CardHeader>
            <CardBody>
              <TrendPreview observations={observations} />
              <div className="mt-4 flex items-center justify-between gap-3"><p className="text-xs text-ocean-500">Historical trend data will appear after API integration.</p><Button to="/data" variant="ghost" size="sm">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button></div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-cyan-600" /><h2 className="text-base font-bold text-navy-950">Forecast Preview</h2></div><Badge variant="neutral">XGBoost</Badge></div>
            </CardHeader>
            <CardBody>
              <div className="rounded-xl border border-dashed border-ocean-300 bg-ocean-50 p-5">
                <div className="flex items-center justify-between"><span className="text-xs font-medium text-ocean-500">Forecast horizon</span><span className="font-mono text-sm font-semibold text-navy-800">—</span></div>
                <div className="mt-4 h-2 rounded-full bg-ocean-200"><div className="h-full w-1/2 rounded-full bg-cyan-300/50" /></div>
                <p className="mt-4 text-xs leading-5 text-ocean-500">Predicted concentration and horizon will appear here when a model output is available.</p>
              </div>
              <div className="mt-4 flex justify-end"><Button to="/forecast" variant="ghost" size="sm">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button></div>
            </CardBody>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Target className="h-4 w-4 text-amber-600" /><h2 className="text-base font-bold text-navy-950">Cleanup Priority Preview</h2></div><Badge variant="neutral">Decision support</Badge></div>
            </CardHeader>
            <CardBody>
              <div className="grid gap-3 sm:grid-cols-3"><PriorityItem label="Highest level" /><PriorityItem label="Top location" /><PriorityItem label="Overall score" /></div>
              <div className="mt-5 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-800"><CircleHelp className="mt-0.5 h-4 w-4 shrink-0" /><span>Contextual inputs and priority scores are pending validated data.</span></div>
              <div className="mt-4 flex justify-end"><Button to="/priority" variant="ghost" size="sm">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button></div>
            </CardBody>
          </Card>
          <Card>
            <CardHeader><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Database className="h-4 w-4 text-ocean-700" /><h2 className="text-base font-bold text-navy-950">Recent Data</h2></div><Badge variant="neutral">Latest records</Badge></div></CardHeader>
            <CardBody>
              <div className="space-y-2">{observations.slice(0, 3).map((observation) => <RecentRow key={observation.unique_id} observation={observation} />)}{!observations.length && <p className="py-6 text-center text-xs text-ocean-500">No recent observations returned.</p>}</div>
              <div className="mt-4 flex justify-end"><Button to="/data" variant="ghost" size="sm">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button></div>
            </CardBody>
          </Card>
        </div>

        <Card className="mt-6 bg-navy-950 text-white">
          <CardBody className="p-6 sm:p-7">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300"><ShieldCheck className="h-4 w-4" /> System readiness</div>
                <h2 className="mt-3 text-2xl font-bold">Model Health</h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-ocean-300">A compact status view for the analytical modules that power OceanWatch. Detailed metrics remain in the model workspace.</p>
              </div>
              <div className="grid grid-cols-3 gap-2 sm:gap-3"><HealthItem label="Hotspots" /><HealthItem label="Forecast" /><HealthItem label="Priority" /></div>
              <Button to="/models" variant="outline" size="sm" className="border-navy-600 bg-navy-900 text-white hover:border-cyan-400 hover:bg-navy-800 hover:text-white">View full analysis <ArrowRight className="h-3.5 w-3.5" /></Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function SignalRow({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="rounded-xl border border-ocean-100 bg-ocean-50 p-3"><div className="flex items-center justify-between gap-3"><span className="text-xs font-medium text-ocean-500">{label}</span><span className="font-mono text-sm font-semibold text-navy-800">{value}</span></div><p className="mt-1 text-[11px] text-ocean-400">{note}</p></div>;
}

function OverviewMap({ observations }: { observations: PollutionObservation[] }) {
  return <div className="relative h-56 overflow-hidden rounded-xl border border-ocean-200 bg-ocean-50 dot-pattern">{observations.map((observation) => <span key={observation.unique_id} className="absolute h-2 w-2 rounded-full bg-cyan-500" style={{ left: `${Math.min(95, Math.max(5, ((observation.longitude + 180) / 360) * 100))}%`, top: `${Math.min(95, Math.max(5, ((90 - observation.latitude) / 180) * 100))}%` }} />)}<span className="absolute bottom-3 left-3 rounded-md bg-white/90 px-2.5 py-1.5 text-[10px] font-medium text-ocean-600 shadow-card">Observation coordinates</span></div>;
}

function HotspotPreview({ hotspots }: { hotspots: Hotspot[] }) {
  return <div className="relative h-56 overflow-hidden rounded-xl border border-ocean-200 bg-navy-950 grid-pattern">{hotspots.map((hotspot) => <span key={hotspot.cluster_id} className="absolute h-3 w-3 rounded-full bg-cyan-300 shadow-glow" style={{ left: `${Math.min(95, Math.max(5, ((hotspot.centroid.longitude + 180) / 360) * 100))}%`, top: `${Math.min(95, Math.max(5, ((90 - hotspot.centroid.latitude) / 180) * 100))}%` }} />)}<span className="absolute bottom-3 left-3 rounded-md border border-ocean-700 bg-navy-900/90 px-2.5 py-1.5 text-[10px] font-medium text-ocean-300">Backend hotspot centroids</span></div>;
}

function TrendPreview({ observations }: { observations: PollutionObservation[] }) {
  const max = Math.max(...observations.map((observation) => observation.measurement), 0);
  const points = observations.map((observation, index) => `${observations.length === 1 ? 50 : (index / (observations.length - 1)) * 100},${92 - (observation.measurement / (max || 1)) * 80}`).join(' ');
  return <div className="relative h-44 overflow-hidden rounded-xl border border-ocean-200 bg-ocean-50 p-4"><div className="absolute inset-0 grid-pattern opacity-60" /><svg className="absolute inset-x-4 bottom-8 h-2/3 w-[calc(100%-2rem)]" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Pollution observation trend">{observations.length > 0 && <polyline points={points} fill="none" stroke="#0e7490" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />}</svg>{!observations.length && <span className="absolute left-1/2 top-1/2 -translate-x-1/2 rounded-md bg-white/90 px-2.5 py-1.5 text-[10px] font-medium text-ocean-600 shadow-card">Trend data unavailable</span>}</div>;
}

function PriorityItem({ label }: { label: string }) {
  return <div className="rounded-xl border border-ocean-100 bg-ocean-50 p-3"><p className="text-[11px] text-ocean-500">{label}</p><p className="mt-2 font-mono text-lg font-semibold text-navy-950">—</p><p className="mt-1 text-[10px] text-ocean-400">Pending score</p></div>;
}

function RecentRow({ observation }: { observation: PollutionObservation }) {
  return <div className="flex items-center justify-between gap-3 rounded-lg border border-ocean-100 bg-ocean-50 px-3 py-3"><div className="flex items-center gap-2.5"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white text-ocean-500"><Database className="h-3.5 w-3.5" /></span><div><p className="text-xs font-medium text-navy-800">{observation.unique_id}</p><p className="mt-0.5 text-[10px] text-ocean-400">{observation.region ?? observation.ocean ?? 'Location unavailable'}</p></div></div><span className="font-mono text-[10px] text-ocean-400">{observation.measurement}</span></div>;
}

function HealthItem({ label }: { label: string }) {
  return <div className="rounded-xl border border-navy-700 bg-navy-900 px-3 py-3 text-center"><CheckCircle2 className="mx-auto h-4 w-4 text-ocean-400" /><p className="mt-2 text-[11px] text-ocean-200">{label}</p><p className="mt-1 text-[10px] text-ocean-400">Pending</p></div>;
}
