import { useEffect, useState } from 'react';
import {
  Activity,
  CalendarRange,
  CircleDot,
  Crosshair,
  Database,
  Download,
  Filter,
  Gauge,
  Globe2,
  Layers,
  MapPin,
  Maximize2,
  Radio,
  RefreshCw,
  ScatterChart,
  Target,
  Waves,
  X,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { SectionHeader } from '@/components/ui/SectionHeader';
import { PollutionMap } from '@/components/PollutionMap';
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
  // Position on the map placeholder (percentage)
  x: number;
  y: number;
  radius: number;
  color: string;
  ringColor: string;
}

interface ObservationPoint {
  x: number;
  y: number;
  type: 'core' | 'border' | 'noise';
  clusterId?: string;
}

function toClusterData(hotspots: Hotspot[]): ClusterData[] {
  if (hotspots.length === 0) return [];
  const latitudes = hotspots.map((hotspot) => hotspot.centroid.latitude);
  const longitudes = hotspots.map((hotspot) => hotspot.centroid.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const latRange = maxLat - minLat || 1;
  const lonRange = maxLon - minLon || 1;

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
      x: 10 + ((hotspot.centroid.longitude - minLon) / lonRange) * 80,
      y: 88 - ((hotspot.centroid.latitude - minLat) / latRange) * 76,
      radius: 5 + Math.min(5, hotspot.observation_count / 100),
      color,
      ringColor,
    };
  }).sort((left, right) => left.id.localeCompare(right.id, undefined, { numeric: true }));
}

/* ------------------------------------------------------------------ */
/* Main page component                                                  */
/* ------------------------------------------------------------------ */

export function HotspotsPage() {
  const { filters, setFilters, resetFilters } = useDashboardFilters();
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
        {/* Filter panel */}
        <FilterPanel
          filters={filters}
          setFilters={setFilters}
          resetFilters={resetFilters}
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

        {/* DBSCAN explanation */}
        <DbscanExplanation />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Filter panel                                                         */
/* ------------------------------------------------------------------ */

function FilterPanel({
  filters,
  setFilters,
  resetFilters,
  availableRegions,
  availableOceans,
}: {
  filters: DashboardFilters;
  setFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  resetFilters: () => void;
  availableRegions: string[];
  availableOceans: string[];
}) {
  const filtersActive = filters.region !== 'ALL' || filters.ocean !== 'ALL' || Boolean(filters.startDate || filters.endDate);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
              <Filter className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-navy-950">Filters</h3>
          </div>
          {filtersActive && <Button variant="ghost" size="sm" className="px-2" onClick={resetFilters}><RefreshCw className="h-3.5 w-3.5" />Clear shared filters</Button>}
        </div>
      </CardHeader>
      <CardBody>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <FilterField icon={CalendarRange} label="Start date (UTC)">
            <input type="date" max={filters.endDate || undefined} value={filters.startDate} onChange={(event) => setFilters((current) => ({ ...current, startDate: event.target.value }))} className="w-full rounded-lg border border-ocean-200 bg-white px-3 py-2.5 text-sm text-navy-900 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500" />
          </FilterField>
          <FilterField icon={CalendarRange} label="End date (UTC, inclusive)">
            <input type="date" min={filters.startDate || undefined} value={filters.endDate} onChange={(event) => setFilters((current) => ({ ...current, endDate: event.target.value }))} className="w-full rounded-lg border border-ocean-200 bg-white px-3 py-2.5 text-sm text-navy-900 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500" />
          </FilterField>
          <FilterField icon={Globe2} label="Region">
            <select value={filters.region} onChange={(event) => setFilters((current) => ({ ...current, region: event.target.value }))} className="w-full rounded-lg border border-ocean-200 bg-white px-3 py-2.5 text-sm text-navy-900 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"><option value="ALL">All regions</option>{availableRegions.map((region) => <option key={region} value={region}>{region}</option>)}</select>
          </FilterField>
          <FilterField icon={Waves} label="Ocean">
            <select value={filters.ocean} onChange={(event) => setFilters((current) => ({ ...current, ocean: event.target.value }))} className="w-full rounded-lg border border-ocean-200 bg-white px-3 py-2.5 text-sm text-navy-900 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"><option value="ALL">All oceans</option>{availableOceans.map((ocean) => <option key={ocean} value={ocean}>{ocean}</option>)}</select>
          </FilterField>
        </div>
        <p className="mt-3 text-xs leading-5 text-ocean-500">Region and ocean filters are sent to the hotspot-list API. Date values are shared with observation views; hotspot listing currently has no date-filter parameters.</p>
      </CardBody>
    </Card>
  );
}

function FilterField({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof Filter;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ocean-600">
        <Icon className="h-3.5 w-3.5 text-ocean-400" />
        {label}
      </label>
      {children}
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

export function HotspotMap({
  clusters,
  points,
  selectedCluster,
  onSelectCluster,
  loading,
  error,
}: {
  clusters: ClusterData[];
  points: ObservationPoint[];
  selectedCluster: ClusterData | null;
  onSelectCluster: (cluster: ClusterData | null) => void;
  loading: boolean;
  error: string | null;
}) {
  const [hoveredCluster, setHoveredCluster] = useState<ClusterData | null>(null);

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
              <ScatterChart className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-navy-950">Hotspot map</h3>
            <Badge variant="neutral">{loading ? 'Loading' : error ? 'Unavailable' : `${clusters.length} clusters`}</Badge>
          </div>
          <div className="flex items-center gap-1.5">
            {selectedCluster && (
              <Button variant="ghost" size="sm" className="px-2 text-xs" onClick={() => onSelectCluster(null)}>
                Reset
              </Button>
            )}
            <Button variant="ghost" size="sm" className="px-2">
              <Download className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="sm" className="px-2">
              <Maximize2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        <div className="relative aspect-[16/11] w-full overflow-hidden bg-navy-950">
          {/* Grid background */}
          <div className="absolute inset-0 grid-pattern opacity-[0.08]" />

          {/* Abstract ocean landmasses */}
          <div className="absolute left-[8%] top-[10%] h-[28%] w-[30%] rotate-[6deg] rounded-[45%_55%_40%_60%] bg-ocean-800/40" />
          <div className="absolute left-[38%] top-[34%] h-[38%] w-[34%] -rotate-[4deg] rounded-[60%_40%_55%_45%] bg-ocean-800/50" />
          <div className="absolute right-[5%] top-[6%] h-[20%] w-[13%] rotate-45 rounded-[50%_60%_40%_50%] bg-ocean-800/35" />

          {/* Current flow lines */}
          <svg
            className="absolute inset-0 h-full w-full opacity-20"
            viewBox="0 0 500 340"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d="M0 220 C 80 180, 120 260, 200 200 S 320 140, 500 190"
              fill="none"
              stroke="#22d3ee"
              strokeWidth="1"
              strokeDasharray="4 8"
            />
            <path
              d="M0 120 C 100 160, 180 80, 260 130 S 380 100, 500 60"
              fill="none"
              stroke="#2dd4bf"
              strokeWidth="1"
              strokeDasharray="3 9"
            />
          </svg>

          {/* Hotspot region circles */}
          {clusters.map((cluster) => {
            const isSelected = selectedCluster?.id === cluster.id;
            return (
              <button
                key={cluster.id}
                type="button"
                onClick={() => onSelectCluster(isSelected ? null : cluster)}
                onMouseEnter={() => setHoveredCluster(cluster)}
                onMouseLeave={() => setHoveredCluster(null)}
                className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-transform duration-200 hover:scale-105 focus-visible:scale-105"
                style={{
                  left: `${cluster.x}%`,
                  top: `${cluster.y}%`,
                  width: `${cluster.radius * 2}%`,
                  height: `${cluster.radius * 2 * (11 / 16)}%`,
                }}
                aria-label={`Cluster ${cluster.id}: ${cluster.label}`}
              >
                <div
                  className={cn(
                    'h-full w-full rounded-full border-2 transition-all duration-200',
                    isSelected && 'ring-2 ring-cyan-400 ring-offset-2 ring-offset-navy-950'
                  )}
                  style={{
                    backgroundColor: cluster.color,
                    borderColor: cluster.ringColor,
                  }}
                />
                {/* Cluster label */}
                <span
                  className={cn(
                    'absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded-md px-2 py-0.5 font-mono text-[10px] font-medium transition-colors',
                    isSelected
                      ? 'bg-cyan-500 text-navy-950'
                      : 'bg-navy-900/80 text-ocean-300'
                  )}
                >
                  {cluster.id}
                </span>
              </button>
            );
          })}

          {hoveredCluster && (
            <div className="pointer-events-none absolute right-4 top-4 z-10 w-56 rounded-lg border border-cyan-500/40 bg-navy-950/90 p-3 text-xs text-white shadow-xl backdrop-blur-sm">
              <p className="font-semibold text-cyan-300">Cluster {hoveredCluster.id} · {hoveredCluster.label}</p>
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-ocean-200">
                <dt>Observations</dt><dd className="text-right font-mono">{hoveredCluster.observations.toLocaleString()}</dd>
                <dt>Average</dt><dd className="text-right font-mono">{hoveredCluster.avgConcentration.toFixed(3)}</dd>
                <dt>Maximum</dt><dd className="text-right font-mono">{hoveredCluster.maxConcentration.toFixed(3)}</dd>
                <dt>Coordinates</dt><dd className="text-right font-mono">{hoveredCluster.centerLat.toFixed(2)}, {hoveredCluster.centerLon.toFixed(2)}</dd>
              </dl>
            </div>
          )}

          {/* Observation points are not exposed by the hotspot list endpoint. */}
          {points.map((point, i) => {
            const isCore = point.type === 'core';
            const isBorder = point.type === 'border';
            const isNoise = point.type === 'noise';
            const inSelectedCluster =
              selectedCluster && point.clusterId === selectedCluster.id;

            return (
              <div
                key={i}
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
              >
                {isCore && (
                  <div
                    className={cn(
                      'h-2.5 w-2.5 rounded-full border-2 border-navy-950 transition-all duration-200',
                      inSelectedCluster ? 'scale-150 bg-cyan-300 shadow-glow' : 'bg-cyan-400'
                    )}
                  />
                )}
                {isBorder && (
                  <div
                    className={cn(
                      'h-2 w-2 rounded-full border border-navy-950 transition-all duration-200',
                      inSelectedCluster ? 'scale-125 bg-teal-300' : 'bg-teal-400'
                    )}
                  />
                )}
                {isNoise && (
                  <div className="h-1.5 w-1.5 rounded-full border border-ocean-500 bg-ocean-400/50" />
                )}
              </div>
            );
          })}

          {/* Top-left overlay — coordinate readout */}
          <div className="absolute left-4 top-4 flex items-center gap-2 rounded-lg border border-ocean-700/60 bg-navy-950/70 px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-ocean-300 backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
            Observation Layer
          </div>

          {/* Bottom-right overlay — DBSCAN params */}
          <div className="absolute bottom-4 right-4 rounded-lg border border-ocean-700/60 bg-navy-950/70 px-3 py-2 backdrop-blur-sm">
            <p className="font-mono text-[10px] text-ocean-400">eps = 0.5 · minPts = 8</p>
            <p className="mt-0.5 text-[10px] text-ocean-500">Placeholder parameters</p>
          </div>

          {/* Empty state hint when no cluster selected */}
          {!selectedCluster && (
            <div className="pointer-events-none absolute bottom-4 left-4 rounded-lg border border-ocean-700/60 bg-navy-950/70 px-3 py-2 backdrop-blur-sm">
              <p className="flex items-center gap-1.5 text-[10px] text-ocean-300">
                <Crosshair className="h-3 w-3 text-cyan-400" />
                Click a hotspot region to view cluster details
              </p>
            </div>
          )}
          {!loading && !error && clusters.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center"><span className="rounded-lg border border-ocean-700/60 bg-navy-950/80 px-3 py-2 text-xs text-ocean-300">No hotspot clusters returned</span></div>
          )}
          {error && <div className="absolute inset-0 flex items-center justify-center"><span className="max-w-xs rounded-lg border border-red-400/40 bg-navy-950/90 px-3 py-2 text-center text-xs text-red-200">Unable to load hotspot data: {error}</span></div>}
        </div>
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
