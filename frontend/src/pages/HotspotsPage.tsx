import { useEffect, useState } from 'react';
import {
  Activity,
  CalendarRange,
  CircleDot,
  Crosshair,
  Database,
  Gauge,
  Layers,
  MapPin,
  Radio,
  ScatterChart,
  Target,
  X,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { SectionHeader } from '@/components/ui/SectionHeader';
import { PollutionMap } from '@/components/PollutionMap';
import { SharedFilterBar } from '@/components/SharedFilterBar';
import { cn } from '@/lib/utils';
import { oceanWatchApi, type Hotspot, type PollutionObservation } from '@/lib/api/client';
import { useDashboardFilters, type DashboardFilters } from '@/lib/dashboardFilters';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface ClusterData {
  id: string;
  label: string;
  observations: number;
  centerLat: number;
  centerLon: number;
  avgConcentration: number;
  maxConcentration: number;
  dateRange: string;
  color: string;
  ringColor: string;
}

function toClusterData(hotspots: Hotspot[]): ClusterData[] {
  if (hotspots.length === 0) return [];

  return hotspots.map((hotspot) => {
    const severityColor: Record<string, [string, string]> = {
      CRITICAL: ['rgba(248, 113, 113, 0.16)', 'rgba(248, 113, 113, 0.65)'],
      HIGH: ['rgba(251, 146, 60, 0.16)', 'rgba(251, 146, 60, 0.65)'],
      MEDIUM: ['rgba(45, 212, 191, 0.16)', 'rgba(45, 212, 191, 0.65)'],
      LOW: ['rgba(34, 211, 238, 0.16)', 'rgba(34, 211, 238, 0.65)'],
    };
    const [color, ringColor] = severityColor[hotspot.severity] ?? severityColor.LOW;
    const dateStart = hotspot.date_start ?? hotspot.date_range.start;
    const dateEnd = hotspot.date_end ?? hotspot.date_range.end;
    return {
      id: String(hotspot.cluster_id),
      label: hotspot.label,
      observations: hotspot.observation_count,
      centerLat: hotspot.centroid.latitude,
      centerLon: hotspot.centroid.longitude,
      avgConcentration: hotspot.average_pollution,
      maxConcentration: hotspot.maximum_pollution,
      dateRange: dateStart || dateEnd ? `${dateStart ?? '—'} to ${dateEnd ?? '—'}` : '—',
      color,
      ringColor,
    };
  }).sort((left, right) => left.id.localeCompare(right.id, undefined, { numeric: true }));
}

/* ------------------------------------------------------------------ */
/* Main page component                                                  */
/* ------------------------------------------------------------------ */

export function HotspotsPage() {
  const { filters, setFilters } = useDashboardFilters();
  const [selectedCluster, setSelectedCluster] = useState<ClusterData | null>(null);
  const [clusters, setClusters] = useState<ClusterData[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [observations, setObservations] = useState<PollutionObservation[]>([]);
  const [totalClusters, setTotalClusters] = useState(0);
  const [availableRegions, setAvailableRegions] = useState<string[]>([]);
  const [availableOceans, setAvailableOceans] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    oceanWatchApi.getAllObservations({
      region: filters.region !== 'ALL' ? filters.region : undefined,
      ocean: filters.ocean !== 'ALL' ? filters.ocean : undefined,
      start_date: filters.startDate || undefined,
      end_date: filters.endDate || undefined,
    })
      .then(({ data }) => {
        if (!active) return;
        setObservations(data);
        setAvailableRegions([...new Set(data.map((observation) => observation.region).filter((value): value is string => Boolean(value)))].sort());
        setAvailableOceans([...new Set(data.map((observation) => observation.ocean).filter((value): value is string => Boolean(value)))].sort());
      })
      .catch(() => null);
    return () => { active = false; };
  }, [filters.endDate, filters.ocean, filters.region, filters.startDate]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setSelectedCluster(null);
    oceanWatchApi.getHotspots({
      limit: 500,
      region: filters.region !== 'ALL' ? filters.region : undefined,
      ocean: filters.ocean !== 'ALL' ? filters.ocean : undefined,
    })
      .then((hotspotResponse) => {
        if (!active) return;
        setHotspots(hotspotResponse.data);
        setClusters(toClusterData(hotspotResponse.data));
        setTotalClusters(hotspotResponse.total);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters.region, filters.ocean]);

  const largestCluster = clusters.reduce((largest, cluster) => cluster.observations > (largest?.observations ?? 0) ? cluster : largest, null as ClusterData | null);
  const highestConcentration = clusters.reduce((highest, cluster) => Math.max(highest, cluster.maxConcentration), 0);
  const observationsInReturnedClusters = clusters.reduce((total, cluster) => total + cluster.observations, 0);

  return (
    <div>
      <PageHeader
        title="Marine Pollution Hotspots"
        description="Explore geographically clustered marine plastic pollution observations identified using DBSCAN."
        eyebrow="Spatial intelligence"
      >
        <Badge variant="cyan" icon={<span className="h-1.5 w-1.5 rounded-full bg-cyan-500" />}>
          DBSCAN clustering
        </Badge>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <SharedFilterBar
          title="Filters"
          description="Region and ocean filters affect hotspot results. Date values are applied to observation requests only."
          availableRegions={availableRegions}
          availableOceans={availableOceans}
        />
        {(filters.startDate || filters.endDate) && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            This hotspot-list API supports region and ocean filters, but not date bounds. The selected date range is shared with observation views and does not change these hotspot results.
          </div>
        )}

        {/* Summary stats */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SummaryStat
            icon={Database}
            label="Total observations"
            value={loading ? '—' : observationsInReturnedClusters.toLocaleString()}
            sub={loading ? 'Loading hotspot data' : error ? 'Backend unavailable' : 'In returned filtered clusters'}
          />
          <SummaryStat
            icon={Layers}
            label="Detected clusters"
            value={loading ? '—' : totalClusters.toLocaleString()}
            sub={loading ? 'Loading hotspot data' : 'Matching DBSCAN clusters'}
          />
          <SummaryStat
            icon={CircleDot}
            label="Noise percentage"
            value="—"
            sub="Noise points are not returned by the list endpoint"
          />
          <SummaryStat
            icon={Target}
            label="Largest cluster"
            value={largestCluster ? `C-${largestCluster.id} · ${largestCluster.observations} pts` : '—'}
            sub="Largest returned cluster"
          />
          <SummaryStat
            icon={Gauge}
            label="Highest concentration"
            value={highestConcentration ? `${highestConcentration.toFixed(2)} pieces/m³` : '—'}
            sub="Highest returned concentration"
          />
        </div>

        {/* Map + cluster details */}
        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_22rem]">
          <RealHotspotMap
            clusters={clusters}
            hotspots={hotspots}
            observations={observations}
            setFilters={setFilters}
            loading={loading}
            error={error}
            selectedCluster={selectedCluster}
            onSelectCluster={setSelectedCluster}
          />
          <ClusterDetailsPanel cluster={selectedCluster} onClose={() => setSelectedCluster(null)} />
        </div>

        {/* Legend */}
        <MapLegend />

      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Summary stats                                                        */
/* ------------------------------------------------------------------ */

function SummaryStat({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: typeof Database;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <Card>
      <CardBody className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-ocean-500">{label}</p>
            <p className="mt-2.5 font-display text-2xl font-bold text-navy-950">{value}</p>
            <p className="mt-1.5 text-[10px] text-ocean-400">{sub}</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
            <Icon className="h-4 w-4" />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Hotspot map                                                          */
/* ------------------------------------------------------------------ */

function RealHotspotMap({
  clusters,
  hotspots,
  observations,
  setFilters,
  selectedCluster,
  onSelectCluster,
  loading,
  error,
}: {
  clusters: ClusterData[];
  hotspots: Hotspot[];
  observations: PollutionObservation[];
  setFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  selectedCluster: ClusterData | null;
  onSelectCluster: (cluster: ClusterData | null) => void;
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
              <ScatterChart className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-navy-950">Pollution map</h3>
            <Badge variant="neutral">{loading ? 'Loading' : error ? 'Unavailable' : `${observations.length} observations · ${hotspots.length} hotspots`}</Badge>
          </div>
          {selectedCluster && <Button variant="ghost" size="sm" className="px-2 text-xs" onClick={() => onSelectCluster(null)}>Reset</Button>}
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {loading ? (
          <div className="flex min-h-[30rem] items-center justify-center bg-ocean-50 text-sm text-ocean-500">Loading geographic data…</div>
        ) : error ? (
          <div className="flex min-h-[30rem] items-center justify-center bg-ocean-50 px-6 text-center text-sm text-red-700">{error}</div>
        ) : observations.length === 0 && hotspots.length === 0 ? (
          <div className="flex min-h-[30rem] flex-col items-center justify-center bg-ocean-50 px-6 text-center">
            <MapPin className="h-8 w-8 text-ocean-300" />
            <p className="mt-3 text-sm font-semibold text-navy-800">No geographic data available</p>
            <p className="mt-1 max-w-md text-xs text-ocean-500">There are no observations or detected hotspots for the selected filters.</p>
          </div>
        ) : (
          <PollutionMap
            observations={observations}
            hotspots={hotspots}
            selectedHotspotId={selectedCluster?.id ?? null}
            onSelectHotspot={(hotspot) => {
              const cluster = clusters.find((item) => item.id === String(hotspot.cluster_id));
              if (cluster) {
                onSelectCluster(cluster);
                const region = hotspot.region ?? hotspot.dominant_region;
                if (region) setFilters((current) => ({ ...current, region }));
              }
            }}
          />
        )}
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Cluster details panel                                                */
/* ------------------------------------------------------------------ */

function ClusterDetailsPanel({
  cluster,
  onClose,
}: {
  cluster: ClusterData | null;
  onClose: () => void;
}) {
  return (
    <Card className={cn('transition-all duration-300', !cluster && 'opacity-60')}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
              <Radio className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-navy-950">Cluster details</h3>
          </div>
          {cluster && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1 text-ocean-400 transition-colors hover:bg-ocean-100 hover:text-navy-800"
              aria-label="Close cluster details"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {cluster ? (
          <div className="space-y-1">
            {/* Cluster header */}
            <div className="mb-4 flex items-center gap-3 rounded-xl border border-ocean-100 bg-ocean-50 p-4">
              <div
                className="h-10 w-10 shrink-0 rounded-full border-2"
                style={{
                  backgroundColor: cluster.color,
                  borderColor: cluster.ringColor,
                }}
              />
              <div>
                <p className="font-mono text-xs text-cyan-600">{cluster.id}</p>
                <p className="text-sm font-bold text-navy-950">{cluster.label}</p>
              </div>
            </div>

            {/* Detail rows */}
            <DetailRow icon={CircleDot} label="Cluster ID" value={cluster.id} mono />
            <DetailRow icon={Database} label="Observations" value={String(cluster.observations)} mono />
            <DetailRow
              icon={MapPin}
              label="Center latitude"
              value={`${cluster.centerLat.toFixed(2)}°`}
              mono
            />
            <DetailRow
              icon={MapPin}
              label="Center longitude"
              value={`${cluster.centerLon.toFixed(2)}°`}
              mono
            />
            <DetailRow
              icon={Activity}
              label="Avg concentration"
              value={`${cluster.avgConcentration.toFixed(2)} pieces/m³`}
              mono
            />
            <DetailRow
              icon={Gauge}
              label="Max concentration"
              value={`${cluster.maxConcentration.toFixed(1)} pieces/m³`}
              mono
            />
            <DetailRow icon={CalendarRange} label="Date range" value={cluster.dateRange} />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-ocean-200 bg-ocean-50 text-ocean-400">
              <Crosshair className="h-5 w-5" />
            </div>
            <p className="mt-4 text-sm font-medium text-ocean-600">
              No cluster selected
            </p>
            <p className="mt-1.5 max-w-[16rem] text-xs text-ocean-400">
              Click a hotspot region on the map to view its cluster details.
              This panel will display DBSCAN results from the backend once
              connected.
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: typeof Database;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-ocean-100 py-3 last:border-0">
      <span className="flex items-center gap-2 text-xs text-ocean-500">
        <Icon className="h-3.5 w-3.5 text-ocean-400" />
        {label}
      </span>
      <span className={cn('text-sm font-medium text-navy-900', mono && 'font-mono')}>
        {value}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Map legend                                                            */
/* ------------------------------------------------------------------ */

function MapLegend() {
  const items = [
    { label: 'Core point', description: 'Dense observation within a cluster', dot: 'bg-cyan-400 border-navy-950' },
    { label: 'Border point', description: 'Edge of a cluster boundary', dot: 'bg-teal-400 border-navy-950' },
    { label: 'Noise point', description: 'Outlier — not assigned to any cluster', dot: 'bg-ocean-400/50 border-ocean-500' },
    { label: 'Hotspot region', description: 'DBSCAN cluster boundary', dot: 'border-cyan-400 bg-cyan-100/40' },
  ];

  return (
    <div className="mt-4 flex flex-wrap gap-x-6 gap-y-3 rounded-xl border border-ocean-200 bg-white px-5 py-4">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2.5">
          <span className={cn('h-3.5 w-3.5 rounded-full border-2', item.dot)} />
          <div>
            <span className="text-xs font-semibold text-navy-800">{item.label}</span>
            <span className="ml-2 text-xs text-ocean-500">{item.description}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* DBSCAN explanation                                                    */
/* ------------------------------------------------------------------ */

// Methodology remains documented in source while the long explanation is omitted from the main view.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function DbscanExplanation() {
  const concepts = [
    {
      icon: MapPin,
      title: 'Geographic distance',
      text: 'DBSCAN measures the haversine distance between observation coordinates. Points within a threshold radius (eps) of each other are considered neighbours, forming the spatial basis for clustering.',
    },
    {
      icon: Layers,
      title: 'Density-based clustering',
      text: 'Unlike centroid-based methods, DBSCAN groups points by local density. A region is a cluster only if enough observations (minPts) fall within the eps radius — no pre-defined cluster count is needed.',
    },
    {
      icon: CircleDot,
      title: 'Core points',
      text: 'A point with at least minPts neighbours within eps is a core point. These form the dense interior of each cluster and anchor the cluster expansion outward to reachable neighbours.',
    },
    {
      icon: Crosshair,
      title: 'Noise and outliers',
      text: 'Points that do not meet the density threshold and are not reachable from any core point are labelled as noise. These represent isolated observations that do not belong to any identified hotspot.',
    },
  ];

  return (
    <section className="mt-16">
      <SectionHeader
        eyebrow="Methodology"
        title="How DBSCAN identifies hotspots"
        description="DBSCAN (Density-Based Spatial Clustering of Applications with Noise) is the algorithm OceanWatch uses to detect marine pollution hotspots. Here is how it works in the context of geographic pollution observations."
      />
      <div className="mt-10 grid gap-5 sm:grid-cols-2">
        {concepts.map((concept, index) => {
          const Icon = concept.icon;
          return (
            <Card key={concept.title} className="group">
              <CardBody>
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-navy-900 text-cyan-400 transition-colors group-hover:bg-cyan-500 group-hover:text-navy-950">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-ocean-400">
                        Step {index + 1}
                      </span>
                    </div>
                    <h3 className="mt-1 text-base font-bold text-navy-950">
                      {concept.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-ocean-600">
                      {concept.text}
                    </p>
                  </div>
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>

      {/* Parameter note */}
      <div className="mt-6 flex items-start gap-3 rounded-xl border border-ocean-200 bg-ocean-50 p-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
          <Activity className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-semibold text-navy-900">
            Key parameters: eps and minPts
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-ocean-600">
            The <span className="font-mono text-cyan-700">eps</span> parameter
            defines the search radius around each point, while{' '}
            <span className="font-mono text-cyan-700">minPts</span> sets the
            minimum number of observations needed to form a dense region. These
            values control the sensitivity of hotspot detection and will be
            tuned against validated marine datasets when the backend is
            connected.
          </p>
        </div>
      </div>
    </section>
  );
}
