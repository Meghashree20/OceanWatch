import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Database,
  Eye,
  Gauge,
  Layers3,
  Map as MapIcon,
  Radar,
  Route,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Waves,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { SectionHeader } from '@/components/ui/SectionHeader';
import { cn } from '@/lib/utils';
import { oceanWatchApi, type HotspotStats, type PollutionObservation } from '@/lib/api/client';

export function HomePage() {
  return (
    <div>
      <HeroSection />
      <WhyOceanWatchSection />
      <CapabilitiesSection />
      <WorkflowSection />
      <ImpactSection />
      <FinalCtaSection />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 1. HERO                                                             */
/* ------------------------------------------------------------------ */

function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-navy-950 text-white">
      <div className="absolute inset-0 grid-pattern opacity-[0.07]" />
      <div className="absolute -right-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-cyan-500/[0.06] blur-3xl" />
      <div className="absolute -bottom-40 left-1/4 h-[28rem] w-[28rem] rounded-full bg-teal-500/[0.05] blur-3xl" />

      <div className="container-page relative grid items-center gap-14 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-10 lg:py-28">
        {/* Left: copy */}
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3.5 py-1.5 text-xs font-medium text-cyan-300">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
            </span>
            Marine Plastic Pollution Intelligence System
          </div>

          <h1 className="mt-7 text-4xl font-bold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
            Turning marine pollution data{' '}
            <span className="text-cyan-400">into action</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-ocean-200 sm:text-lg">
            OceanWatch uses data analytics and machine learning to identify
            marine plastic pollution hotspots, forecast pollution trends, and
            prioritize cleanup efforts — turning scattered observations into
            evidence-led decisions.
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Button to="/explore" size="lg">
              Explore Ocean Data
              <ArrowUpRight className="h-4 w-4" />
            </Button>
            <Button
              to="/intelligence"
              variant="outline"
              size="lg"
              className="border-navy-600 bg-navy-900/60 text-white hover:border-cyan-400 hover:bg-navy-800 hover:text-white"
            >
              View Intelligence
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>

          {/* Trust line */}
          <div className="mt-10 flex items-center gap-3 text-xs text-ocean-400">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-ocean-700">
              <Waves className="h-3.5 w-3.5 text-cyan-400" />
            </span>
            Built for evidence-led environmental decisions
          </div>
        </div>

        {/* Right: visualization */}
        <HeroVisualization />
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-navy-950 to-transparent" />
    </section>
  );
}

function HeroVisualization() {
  const [records, setRecords] = useState<PollutionObservation[]>([]);
  const [hotspotStats, setHotspotStats] = useState<HotspotStats | null>(null);

  useEffect(() => {
    Promise.all([oceanWatchApi.getObservations({ limit: 8 }), oceanWatchApi.getHotspotStats()])
      .then(([observationResponse, stats]) => { setRecords(observationResponse.data); setHotspotStats(stats); })
      .catch(() => { setRecords([]); setHotspotStats(null); });
  }, []);

  const maxMeasurement = Math.max(...records.map((record) => record.measurement), 0);
  const observations = records.map((record) => ({
    record,
    x: Math.min(90, Math.max(10, ((record.longitude + 180) / 360) * 100)),
    y: Math.min(85, Math.max(10, ((90 - record.latitude) / 180) * 100)),
    r: 3 + (maxMeasurement ? (record.measurement / maxMeasurement) * 5 : 0),
  }));

  const intensityColor: Record<string, string> = {
    high: '#22d3ee',
    med: '#2dd4bf',
    low: '#5a9db1',
  };

  return (
    <div className="relative mx-auto w-full max-w-lg animate-fade-in lg:ml-auto">
      <div className="relative aspect-[1.1] overflow-hidden rounded-2xl border border-ocean-700/60 bg-navy-900/80 shadow-glow">
        {/* Grid background */}
        <div className="absolute inset-0 grid-pattern opacity-[0.12]" />

        {/* Abstract ocean landmasses */}
        <div className="absolute left-[10%] top-[12%] h-[30%] w-[34%] rotate-[8deg] rounded-[45%_55%_40%_60%] bg-ocean-800/50" />
        <div className="absolute left-[40%] top-[38%] h-[40%] w-[36%] -rotate-[4deg] rounded-[60%_40%_55%_45%] bg-ocean-800/60" />
        <div className="absolute right-[6%] top-[8%] h-[22%] w-[14%] rotate-45 rounded-[50%_60%_40%_50%] bg-ocean-800/40" />

        {/* Current flow lines */}
        <svg
          className="absolute inset-0 h-full w-full opacity-25"
          viewBox="0 0 500 460"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            d="M0 320 C 100 280, 120 380, 200 310 S 330 220, 500 280"
            fill="none"
            stroke="#22d3ee"
            strokeWidth="1"
            strokeDasharray="4 8"
          />
          <path
            d="M0 160 C 100 220, 180 110, 270 180 S 390 140, 500 80"
            fill="none"
            stroke="#2dd4bf"
            strokeWidth="1"
            strokeDasharray="3 9"
          />
          <path
            d="M60 30 C 150 120, 200 70, 260 150 S 370 320, 440 380"
            fill="none"
            stroke="#8abfcd"
            strokeWidth="1"
            strokeDasharray="2 7"
          />
        </svg>

        {/* Hotspot cluster highlight (DBSCAN concept) */}
        <div className="absolute left-[44%] top-[18%] h-[28%] w-[30%] rounded-full border border-cyan-400/20 bg-cyan-400/[0.06]" />
        <div className="absolute left-[24%] top-[52%] h-[24%] w-[26%] rounded-full border border-teal-400/20 bg-teal-400/[0.06]" />

        {/* Observation points */}
        {observations.map((obs) => (
          <div
            key={obs.record.unique_id}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${obs.x}%`, top: `${obs.y}%` }}
          >
            <div
              className="absolute -inset-2 animate-pulse-slow rounded-full opacity-20"
              style={{ backgroundColor: obs.record.measurement === maxMeasurement ? intensityColor.high : intensityColor.med }}
            />
            <div
              className="relative rounded-full border-2 border-navy-950"
              style={{
                width: obs.r * 2,
                height: obs.r * 2,
                backgroundColor: obs.record.measurement === maxMeasurement ? intensityColor.high : intensityColor.med,
              }}
            />
          </div>
        ))}

        {/* Top-left label */}
        <div className="absolute left-4 top-4 flex items-center gap-2 rounded-lg border border-ocean-700/60 bg-navy-950/70 px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-ocean-300 backdrop-blur-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
          Observation Layer
        </div>

        {/* Bottom data bar */}
          <div className="absolute bottom-0 left-0 right-0 border-t border-ocean-700/50 bg-navy-950/70 px-4 py-3 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-sm font-medium text-white">
                {records[0] ? `${records[0].latitude.toFixed(2)}° · ${records[0].longitude.toFixed(2)}°` : 'No observation selected'}
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wider text-ocean-400">
                Selected coordinate
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="font-mono text-sm font-medium text-cyan-300">
                  {hotspotStats ? `${hotspotStats.total_clusters} clusters` : 'Unavailable'}
                </p>
                <p className="mt-0.5 text-[10px] text-ocean-400">
                  Priority signal
                </p>
              </div>
              <div className="h-8 w-px bg-ocean-700/60" />
              <div className="text-right">
                <p className="font-mono text-sm font-medium text-teal-300">
                  {records[0] ? records[0].measurement.toFixed(2) : '—'}
                </p>
                <p className="mt-0.5 text-[10px] text-ocean-400">
                  Confidence
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating side card — model status */}
      <div className="absolute -bottom-4 -left-3 hidden rounded-xl border border-ocean-700/70 bg-navy-900 px-4 py-3 shadow-xl sm:block">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/15">
            <Radar className="h-4 w-4 text-teal-400" />
          </div>
          <div>
            <p className="font-mono text-sm text-white">3 modules active</p>
            <p className="text-[10px] text-ocean-400">Intelligence pipeline</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 2. WHY OCEANWATCH                                                   */
/* ------------------------------------------------------------------ */

function WhyOceanWatchSection() {
  const reasons = [
    {
      icon: Eye,
      title: 'See what scattered surveys miss',
      text: 'Pollution is geographically distributed and difficult to monitor. OceanWatch brings fragmented observations into one coherent view.',
    },
    {
      icon: Layers3,
      title: 'Connect data to decisions',
      text: 'The platform links raw marine data to spatial analysis, predictive modelling, and cleanup prioritization — without hiding the reasoning.',
    },
    {
      icon: ShieldCheck,
      title: 'Built for transparency',
      text: 'Every recommendation is traceable. Teams can understand why a zone was flagged and what evidence drove its priority score.',
    },
  ];

  return (
    <section className="border-b border-ocean-200 bg-white">
      <div className="container-page py-20 lg:py-28">
        <SectionHeader
          eyebrow="Why OceanWatch"
          title="Environmental intelligence, not just another dashboard."
          description="OceanWatch is built to close the gap between marine pollution data and the decisions that follow — making the signal visible, the reasoning clear, and the next step obvious."
        />
        <div className="mt-14 grid gap-10 lg:grid-cols-3 lg:gap-8">
          {reasons.map((reason) => {
            const Icon = reason.icon;
            return (
              <div key={reason.title} className="group">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-ocean-200 bg-ocean-50 text-ocean-700 transition-colors group-hover:border-cyan-300 group-hover:bg-cyan-50 group-hover:text-cyan-600">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-6 text-lg font-bold text-navy-950">
                  {reason.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ocean-600">
                  {reason.text}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* 3. CAPABILITIES                                                     */
/* ------------------------------------------------------------------ */

function CapabilitiesSection() {
  return (
    <section className="bg-ocean-50">
      <div className="container-page py-20 lg:py-28">
        <SectionHeader
          eyebrow="Intelligence capabilities"
          title="Three modules. One connected intelligence layer."
          description="Each capability addresses a distinct stage of the pollution response — from detecting where problems concentrate, to forecasting what comes next, to deciding where to act."
        />
        <div className="mt-14 space-y-6">
          <CapabilityRow
            index="01"
            icon={ScanSearch}
            title="DBSCAN Hotspot Detection"
            model="Density-based spatial clustering"
            description="Identifies where marine plastic pollution concentrates by grouping geographically proximate observations into meaningful clusters — revealing hotspot zones that individual data points alone cannot show."
            path="/hotspots"
            visual={<DbscanVisual />}
          />
          <CapabilityRow
            index="02"
            icon={TrendingUp}
            title="XGBoost Pollution Forecasting"
            model="Gradient-boosted regression"
            description="Predicts future pollution concentration by learning from historical observations and environmental signals — helping teams anticipate trends rather than only react to them."
            path="/forecast"
            visual={<XgboostVisual />}
          />
          <CapabilityRow
            index="03"
            icon={Target}
            title="Cleanup Priority Engine"
            model="Transparent weighted scoring"
            description="Converts intelligence into a defensible action sequence by scoring locations against transparent, weighted criteria — so teams know not just what matters, but what to do first."
            path="/priority"
            visual={<PriorityVisual />}
          />
        </div>
      </div>
    </section>
  );
}

function CapabilityRow({
  index,
  icon: Icon,
  title,
  model,
  description,
  path,
  visual,
}: {
  index: string;
  icon: typeof ScanSearch;
  title: string;
  model: string;
  description: string;
  path: string;
  visual: React.ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="grid lg:grid-cols-[1.1fr_0.9fr]">
        {/* Text side */}
        <CardBody className="flex flex-col justify-center p-7 lg:p-10">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-navy-900 text-cyan-400">
              <Icon className="h-5 w-5" />
            </div>
            <span className="font-mono text-xs uppercase tracking-wider text-ocean-500">
              {index} / capability
            </span>
          </div>
          <h3 className="mt-6 text-2xl font-bold text-navy-950">{title}</h3>
          <p className="mt-2 text-sm font-medium text-cyan-700">{model}</p>
          <p className="mt-4 text-sm leading-relaxed text-ocean-600">
            {description}
          </p>
          <div className="mt-7">
            <Button to={path} variant="ghost" className="px-0 hover:bg-transparent">
              Explore
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Button>
          </div>
        </CardBody>
        {/* Visual side */}
        <div className="relative flex items-center justify-center border-t border-ocean-100 bg-gradient-to-br from-ocean-50 to-white p-7 lg:border-l lg:border-t-0 lg:p-10">
          {visual}
        </div>
      </div>
    </Card>
  );
}

function DbscanVisual() {
  const clusters = [
    { cx: 30, cy: 35, points: [[28, 32], [33, 38], [26, 40], [34, 30], [30, 44]] },
    { cx: 70, cy: 55, points: [[68, 52], [74, 58], [66, 60], [72, 50], [70, 62]] },
    { cx: 50, cy: 75, points: [[48, 72], [54, 78], [46, 80], [52, 70]] },
  ];
  return (
    <div className="relative h-56 w-full max-w-sm">
      <div className="absolute inset-0 dot-pattern rounded-xl" />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {clusters.map((cluster, ci) => (
          <g key={ci}>
            <circle
              cx={cluster.cx}
              cy={cluster.cy}
              r={14}
              fill={ci === 0 ? '#22d3ee' : ci === 1 ? '#2dd4bf' : '#3d829a'}
              fillOpacity={0.08}
              stroke={ci === 0 ? '#22d3ee' : ci === 1 ? '#2dd4bf' : '#3d829a'}
              strokeWidth={0.5}
              strokeDasharray="2 2"
            />
            {cluster.points.map(([px, py], pi) => (
              <circle
                key={pi}
                cx={px}
                cy={py}
                r={1.8}
                fill={ci === 0 ? '#0891b2' : ci === 1 ? '#0d9488' : '#316a80'}
              />
            ))}
          </g>
        ))}
        {/* noise point */}
        <circle cx={15} cy={70} r={1.5} fill="#8abfcd" opacity={0.5} />
        <circle cx={85} cy={20} r={1.5} fill="#8abfcd" opacity={0.5} />
      </svg>
      <div className="absolute bottom-2 right-2 rounded-md bg-white/80 px-2 py-1 text-[10px] font-medium text-ocean-600 backdrop-blur-sm">
        3 clusters · 2 noise points
      </div>
    </div>
  );
}

function XgboostVisual() {
  return (
    <div className="relative h-56 w-full max-w-sm rounded-xl border border-ocean-100 bg-white p-4">
      <div className="flex items-center justify-between text-[10px] text-ocean-500">
        <span>Pollution concentration</span>
        <span>Forecast horizon</span>
      </div>
      <svg className="mt-2 h-[80%] w-full" viewBox="0 0 300 140" preserveAspectRatio="none">
        {/* grid */}
        {[0, 35, 70, 105].map((y) => (
          <line key={y} x1={0} y1={y} x2={300} y2={y} stroke="#dbecf2" strokeWidth={0.5} />
        ))}
        {/* observed */}
        <path
          d="M0 100 L20 90 L40 95 L60 75 L80 82 L100 65 L120 70 L140 55"
          fill="none"
          stroke="#316a80"
          strokeWidth={2}
        />
        {/* forecast */}
        <path
          d="M140 55 L160 48 L180 52 L200 38 L220 42 L240 28 L260 32 L280 20 L300 15"
          fill="none"
          stroke="#14b8a6"
          strokeWidth={2}
          strokeDasharray="4 3"
        />
        {/* confidence band */}
        <path
          d="M140 55 L160 42 L180 50 L200 30 L220 38 L240 18 L260 26 L280 10 L300 5 L300 25 L280 30 L260 38 L240 38 L220 46 L200 46 L180 54 L160 54 L140 55"
          fill="#14b8a6"
          fillOpacity={0.1}
          stroke="none"
        />
        {/* divider */}
        <line x1={140} y1={0} x2={140} y2={140} stroke="#8abfcd" strokeWidth={0.5} strokeDasharray="3 3" />
      </svg>
      <div className="mt-1 flex items-center gap-4 text-[10px] text-ocean-500">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-4 rounded-full bg-ocean-700" /> Observed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-4 rounded-full bg-teal-500" /> Forecast
        </span>
      </div>
    </div>
  );
}

function PriorityVisual() {
  const rows = [
    { name: 'Zone A · Northern coast', score: 92, color: 'bg-cyan-500' },
    { name: 'Zone B · Western shelf', score: 78, color: 'bg-teal-500' },
    { name: 'Zone C · Southern current', score: 61, color: 'bg-ocean-500' },
    { name: 'Zone D · Eastern nearshore', score: 44, color: 'bg-ocean-400' },
  ];
  return (
    <div className="h-56 w-full max-w-sm space-y-3">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-ocean-500">
        <span>Priority ranking</span>
        <span>Score</span>
      </div>
      {rows.map((row, i) => (
        <div key={i}>
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="font-medium text-navy-800">{row.name}</span>
            <span className="font-mono text-ocean-600">{row.score}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-ocean-100">
            <div
              className={cn('h-full rounded-full', row.color)}
              style={{ width: `${row.score}%` }}
            />
          </div>
        </div>
      ))}
      <p className="pt-1 text-[10px] text-ocean-400">
        Weighted score · pollution density, accessibility, impact, feasibility
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 4. WORKFLOW                                                         */
/* ------------------------------------------------------------------ */

function WorkflowSection() {
  const steps = [
    { icon: Database, title: 'Data', text: 'Marine observations collected' },
    { icon: Layers3, title: 'Processing', text: 'Cleaned and structured' },
    { icon: Sparkles, title: 'ML Analysis', text: 'Detect and predict' },
    { icon: BarChart3, title: 'Intelligence', text: 'Signal surfaced' },
    { icon: ShieldCheck, title: 'Action', text: 'Prioritized response' },
  ];

  return (
    <section className="overflow-hidden border-b border-ocean-200 bg-white">
      <div className="container-page py-20 lg:py-28">
        <SectionHeader
          align="center"
          eyebrow="The intelligence loop"
          title="How OceanWatch works"
          description="A connected workflow that keeps the evidence visible at every stage — from raw marine data to a prioritized cleanup decision."
        />

        <div className="relative mt-16">
          {/* Connecting line — desktop */}
          <div className="absolute left-[10%] right-[10%] top-10 hidden h-px bg-ocean-200 lg:block" />

          <div className="relative grid gap-8 sm:grid-cols-2 lg:grid-cols-5 lg:gap-4">
            {steps.map((step, index) => {
              const Icon = step.icon;
              return (
                <div key={step.title} className="group text-center">
                  <div className="relative mx-auto flex h-20 w-20 items-center justify-center rounded-2xl border border-ocean-200 bg-white shadow-card transition-all duration-300 group-hover:-translate-y-1 group-hover:border-cyan-300 group-hover:shadow-glow">
                    <div className="absolute inset-2 rounded-xl bg-ocean-50 transition-colors group-hover:bg-cyan-50" />
                    <Icon className="relative h-6 w-6 text-ocean-600 transition-colors group-hover:text-cyan-600" />
                    <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-navy-900 font-mono text-[10px] text-cyan-300">
                      {index + 1}
                    </span>
                  </div>
                  <h3 className="mt-5 text-sm font-bold text-navy-950">
                    {step.title}
                  </h3>
                  <p className="mt-1 text-xs text-ocean-500">{step.text}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* 5. IMPACT                                                           */
/* ------------------------------------------------------------------ */

function ImpactSection() {
  const areas = [
    {
      icon: Radar,
      title: 'Marine monitoring',
      text: 'Bring fragmented observation sources into a single, structured view of the marine environment.',
    },
    {
      icon: Eye,
      title: 'Pollution understanding',
      text: 'Move beyond raw counts to understand where pollution concentrates and how it spreads.',
    },
    {
      icon: Gauge,
      title: 'Decision support',
      text: 'Give teams transparent, evidence-backed recommendations they can defend and act on.',
    },
    {
      icon: Route,
      title: 'Resource prioritization',
      text: 'Direct limited cleanup resources to where they will have the greatest measurable impact.',
    },
  ];

  return (
    <section className="bg-navy-900 text-white">
      <div className="container-page py-20 lg:py-28">
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-400">
            <span className="h-px w-6 bg-cyan-400" />
            Designed for impact
          </div>
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            From observation to a healthier ocean.
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-ocean-300">
            OceanWatch is designed around the real-world needs of teams
            responsible for marine environmental protection — at every stage of
            the response.
          </p>
        </div>

        <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-navy-700 bg-navy-700 sm:grid-cols-2 lg:grid-cols-4">
          {areas.map((area) => {
            const Icon = area.icon;
            return (
              <div key={area.title} className="bg-navy-900 p-7">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-navy-700 bg-navy-800 text-cyan-400">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-6 text-base font-bold text-white">
                  {area.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-ocean-400">
                  {area.text}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* 6. FINAL CTA                                                        */
/* ------------------------------------------------------------------ */

function FinalCtaSection() {
  return (
    <section className="relative overflow-hidden bg-navy-950 text-white">
      <div className="absolute inset-0 grid-pattern opacity-[0.06]" />
      <div className="absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-500/[0.05] blur-3xl" />

      <div className="container-page relative py-20 text-center lg:py-24">
        <div className="mx-auto max-w-2xl">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-500/25 bg-cyan-500/10">
            <MapIcon className="h-6 w-6 text-cyan-400" />
          </div>
          <h2 className="mt-7 text-3xl font-bold sm:text-4xl">
            Explore the OceanWatch Intelligence Platform
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-ocean-300">
            See how a shared view of marine pollution can help teams move from
            observation to intervention — with clarity at every step.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Button to="/intelligence" size="lg">
              Enter the platform
              <ArrowUpRight className="h-4 w-4" />
            </Button>
            <Button
              to="/about"
              variant="outline"
              size="lg"
              className="border-navy-600 bg-navy-900/60 text-white hover:border-cyan-400 hover:bg-navy-800 hover:text-white"
            >
              About the project
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
