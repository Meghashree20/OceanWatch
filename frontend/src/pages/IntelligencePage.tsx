import {
  Activity,
  ArrowRight,
  BarChart3,
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  EyeOff,
  Filter,
  Globe2,
  Info,
  Layers,
  MapPin,
  Radar,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Table,
  Target,
  TrendingUp,
  Waves,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import {
  oceanWatchApi,
  type Hotspot,
  type HotspotStats,
  type PollutionObservation,
  type Recommendation,
} from '@/lib/api/client';

// -----------------------------------------------------------------------------
// Shared Filter Definitions & Constants (Verified against MongoDB schema)
// -----------------------------------------------------------------------------
export interface DashboardFilters {
  ocean: string;
  region: string;
  startDate: string;
  endDate: string;
}

const DEFAULT_FILTERS: DashboardFilters = {
  ocean: 'ALL',
  region: 'ALL',
  startDate: '',
  endDate: '',
};

const OCEAN_OPTIONS = [
  'ALL',
  'Pacific Ocean',
  'Atlantic Ocean',
  'Indian Ocean',
  'Arctic Ocean',
  'Southern Ocean',
];

const REGION_OPTIONS = [
  'ALL',
  'Mediterranean Sea',
  'North Sea',
  'Caribbean Sea',
  'Baltic Sea',
  'East China Sea',
  'South China Sea',
  'Bay of Bengal',
  'Arabian Sea',
  'Philippine Sea',
  'Bering Sea',
  'Coral Sea',
  'Tasman Sea',
  'Gulf of America (formerly Gulf of Mexico)',
];

const DATE_PRESETS = [
  { label: 'All Records (2010–2024)', start: '', end: '' },
  { label: '2020–2024', start: '2020-01-01', end: '2024-12-31' },
  { label: '2015–2019', start: '2015-01-01', end: '2019-12-31' },
  { label: '2010–2014', start: '2010-01-01', end: '2014-12-31' },
];

export function IntelligencePage() {
  // Shared Filter State
  const [filters, setFilters] = useState<DashboardFilters>(DEFAULT_FILTERS);

  // Data States
  const [observations, setObservations] = useState<PollutionObservation[]>([]);
  const [filteredCount, setFilteredCount] = useState<number | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [hotspotStats, setHotspotStats] = useState<HotspotStats | null>(null);
  const [totalUnfilteredObs, setTotalUnfilteredObs] = useState<number | null>(null);

  // Status States
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [globalResetKey, setGlobalResetKey] = useState<number>(0);

  // Load Unfiltered Summary Baseline on Mount
  useEffect(() => {
    oceanWatchApi
      .getSummaryStatistics()
      .then((dataStats) => setTotalUnfilteredObs(dataStats.total_observations))
      .catch(() => null);
  }, []);

  // Primary Data Query driving all dashboard components reactively via Shared Filters
  const fetchDashboardData = useCallback((currentFilters: DashboardFilters) => {
    setLoading(true);
    setError(null);

    // Build backend parameters supported by existing FastAPI endpoints
    const obsParams: {
      limit: number;
      ocean?: string;
      region?: string;
      start_date?: string;
      end_date?: string;
    } = {
      limit: 150,
    };

    if (currentFilters.ocean !== 'ALL') obsParams.ocean = currentFilters.ocean;
    if (currentFilters.region !== 'ALL') obsParams.region = currentFilters.region;
    if (currentFilters.startDate) obsParams.start_date = currentFilters.startDate;
    if (currentFilters.endDate) obsParams.end_date = currentFilters.endDate;

    const hotspotParams: {
      limit: number;
      ocean?: string;
      region?: string;
    } = {
      limit: 500,
    };

    if (currentFilters.ocean !== 'ALL') hotspotParams.ocean = currentFilters.ocean;
    if (currentFilters.region !== 'ALL') hotspotParams.region = currentFilters.region;

    Promise.all([
      oceanWatchApi.getObservations(obsParams),
      oceanWatchApi.getHotspots(hotspotParams),
      oceanWatchApi.getHotspotStats().catch(() => null),
      oceanWatchApi.getPriorityResults(100).catch(() => ({ data: [], total: 0 })),
    ])
      .then(([obsResponse, hotspotResponse, statsResponse, recResponse]) => {
        setObservations(obsResponse.data);
        setFilteredCount(obsResponse.total);
        setHotspots(hotspotResponse.data);
        setHotspotStats(statsResponse);

        // Filter recommendations in-memory by ocean/region if specified
        let filteredRecs = recResponse.data;
        if (currentFilters.ocean !== 'ALL') {
          filteredRecs = filteredRecs.filter(
            (r) =>
              (r.cluster?.ocean as string)?.toUpperCase() === currentFilters.ocean.toUpperCase() ||
              (r.cluster?.region as string)?.toUpperCase() === currentFilters.ocean.toUpperCase()
          );
        }
        if (currentFilters.region !== 'ALL') {
          filteredRecs = filteredRecs.filter(
            (r) =>
              (r.cluster?.region as string)?.toUpperCase() === currentFilters.region.toUpperCase()
          );
        }
        setRecommendations(filteredRecs);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Re-fetch whenever shared filter changes
  useEffect(() => {
    fetchDashboardData(filters);
  }, [filters, fetchDashboardData]);

  // Reset Filters Handler
  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setGlobalResetKey((prev) => prev + 1);
  };

  // Active filter count
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.ocean !== 'ALL') count++;
    if (filters.region !== 'ALL') count++;
    if (filters.startDate) count++;
    if (filters.endDate) count++;
    return count;
  }, [filters]);

  // Dynamic KPI calculations from filtered telemetry
  const highestConcentration = useMemo(() => {
    if (!observations.length) return 0;
    return observations.reduce((max, obs) => Math.max(max, obs.measurement), 0);
  }, [observations]);

  const averageConcentration = useMemo(() => {
    if (!observations.length) return 0;
    const sum = observations.reduce((acc, obs) => acc + obs.measurement, 0);
    return sum / observations.length;
  }, [observations]);

  const criticalClusters = useMemo(() => {
    return hotspots.filter((h) => h.severity === 'CRITICAL').length;
  }, [hotspots]);

  const highSeverityClusters = useMemo(() => {
    return hotspots.filter((h) => h.severity === 'HIGH').length;
  }, [hotspots]);

  return (
    <div className="min-h-screen bg-ocean-50/60 pb-16">
      <PageHeader
        title="OceanWatch Intelligence Dashboard"
        description="Unified marine environmental surveillance tracking microplastic pollution trends, high-density cluster hotspots, and transparent cleanup interventions."
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="cyan" icon={<Waves className="h-3.5 w-3.5" />}>
            Standard Unit: pieces/m³
          </Badge>
          <Badge variant="neutral" icon={<Activity className="h-3.5 w-3.5" />}>
            FastAPI · MongoDB Live
          </Badge>
          {activeFilterCount > 0 && (
            <Badge variant="teal" icon={<Filter className="h-3.5 w-3.5" />}>
              {activeFilterCount} active filter{activeFilterCount > 1 ? 's' : ''}
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetFilters}
            className="bg-white/90 shadow-sm"
            title="Reset all filters and view settings"
          >
            <RotateCcw className="h-3.5 w-3.5 text-ocean-600" />
            Reset All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchDashboardData(filters)}
            disabled={loading}
            className="ml-auto bg-white/90 shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Data
          </Button>
        </div>
      </PageHeader>

      <div className="container-page mt-6 space-y-6">
        {/* SHARED FILTER BAR */}
        <SharedDashboardFilterBar
          filters={filters}
          onChange={setFilters}
          onReset={handleResetFilters}
          activeCount={activeFilterCount}
          totalMatchingRecords={filteredCount}
        />

        {error && (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
            <div>
              <p className="font-semibold">Filter query returned an error</p>
              <p className="mt-1 text-xs text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* 1. TOP METRICS KPI CARDS (Drives consistently from shared filtered dataset) */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiMetricCard
            label="Monitored Observations"
            value={filteredCount !== null ? filteredCount.toLocaleString() : '—'}
            unit="matching records"
            detail={
              activeFilterCount > 0 && totalUnfilteredObs !== null
                ? `Filtered from ${totalUnfilteredObs.toLocaleString()} total database records`
                : 'Verified ocean water sampling points'
            }
            icon={Database}
            accent="ocean"
          />
          <KpiMetricCard
            label="Identified Hotspot Clusters"
            value={hotspots.length ? hotspots.length.toLocaleString() : '—'}
            unit="DBSCAN zones"
            detail={`${criticalClusters} critical · ${highSeverityClusters} high severity`}
            icon={Radar}
            accent="cyan"
          />
          <KpiMetricCard
            label="Peak Observed Concentration"
            value={highestConcentration > 0 ? highestConcentration.toFixed(2) : '—'}
            unit="pieces/m³"
            detail={
              observations.length
                ? `Mean density: ${averageConcentration.toFixed(3)} pieces/m³`
                : 'No observations match filter criteria'
            }
            icon={TrendingUp}
            accent="teal"
          />
          <KpiMetricCard
            label="Targeted Priority Locations"
            value={recommendations.length ? recommendations.length.toLocaleString() : '—'}
            unit="action zones"
            detail="Evaluated via multi-factor cleanup scoring"
            icon={Target}
            accent="navy"
          />
        </div>

        {/* 2. PRIMARY POLLUTION TREND CHART */}
        <PrimaryTrendChart
          observations={observations}
          loading={loading}
          resetTrigger={globalResetKey}
          hasActiveFilters={activeFilterCount > 0}
        />

        {/* 3. GEOGRAPHIC POLLUTION HOTSPOT MAP */}
        <GeographicHotspotMap
          hotspots={hotspots}
          observations={observations}
          resetTrigger={globalResetKey}
          selectedOcean={filters.ocean}
        />

        {/* 4. CLEAN RESPONSIVE SECONDARY CHARTS GRID */}
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          <SeverityBreakdownChart
            hotspots={hotspots}
            stats={hotspotStats}
            resetTrigger={globalResetKey}
          />
          <RegionalPollutionChart
            observations={observations}
            hotspots={hotspots}
            resetTrigger={globalResetKey}
          />
          <PriorityActionQueue
            recommendations={recommendations}
            resetTrigger={globalResetKey}
          />
        </div>

        {/* 5. FILTERED OBSERVATIONS EVIDENCE TABLE */}
        <FilteredObservationsTable
          observations={observations}
          totalCount={filteredCount}
          loading={loading}
          onResetFilters={handleResetFilters}
          activeFilterCount={activeFilterCount}
        />
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Shared Dashboard Filter Bar
// -----------------------------------------------------------------------------
function SharedDashboardFilterBar({
  filters,
  onChange,
  onReset,
  activeCount,
  totalMatchingRecords,
}: {
  filters: DashboardFilters;
  onChange: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  onReset: () => void;
  activeCount: number;
  totalMatchingRecords: number | null;
}) {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  const handleOceanChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange((prev) => ({ ...prev, ocean: e.target.value }));
  };

  const handleRegionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange((prev) => ({ ...prev, region: e.target.value }));
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange((prev) => ({ ...prev, startDate: e.target.value }));
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange((prev) => ({ ...prev, endDate: e.target.value }));
  };

  const applyPreset = (start: string, end: string) => {
    onChange((prev) => ({ ...prev, startDate: start, endDate: end }));
  };

  return (
    <Card className="border border-ocean-200/90 shadow-sm transition-all">
      <div className="border-b border-ocean-100 bg-white/95 px-5 py-3.5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700">
              <SlidersHorizontal className="h-4 w-4" />
            </span>
            <span className="text-sm font-bold text-navy-950">Shared Surveillance Filters</span>
            {activeCount > 0 && (
              <span className="rounded-full bg-cyan-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-cyan-800">
                {activeCount} active
              </span>
            )}
            {totalMatchingRecords !== null && (
              <span className="hidden font-mono text-xs text-ocean-500 sm:inline">
                ({totalMatchingRecords.toLocaleString()} matching observation records in MongoDB)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {activeCount > 0 && (
              <button
                type="button"
                onClick={onReset}
                className="flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold text-ocean-600 hover:bg-ocean-100/80 hover:text-navy-950"
              >
                <X className="h-3.5 w-3.5" />
                Clear Filters
              </button>
            )}
            <button
              type="button"
              onClick={() => setCollapsed(!collapsed)}
              className="text-xs font-medium text-ocean-500 hover:text-ocean-700"
            >
              {collapsed ? 'Expand Controls' : 'Minimize'}
            </button>
          </div>
        </div>
      </div>

      {!collapsed && (
        <CardBody className="bg-ocean-50/40 p-5 sm:p-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* 1. Ocean Basin Filter */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ocean-600">
                Ocean Basin
              </label>
              <div className="relative mt-1.5">
                <select
                  value={filters.ocean}
                  onChange={handleOceanChange}
                  className="w-full appearance-none rounded-xl border border-ocean-200 bg-white px-3.5 py-2 pr-9 text-xs font-medium text-navy-950 shadow-xs focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                >
                  <option value="ALL">All Oceans &amp; Basins</option>
                  {OCEAN_OPTIONS.filter((o) => o !== 'ALL').map((ocean) => (
                    <option key={ocean} value={ocean}>
                      {ocean}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ocean-400" />
              </div>
            </div>

            {/* 2. Specific Region Filter */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ocean-600">
                Marine Region / Sea
              </label>
              <div className="relative mt-1.5">
                <select
                  value={filters.region}
                  onChange={handleRegionChange}
                  className="w-full appearance-none rounded-xl border border-ocean-200 bg-white px-3.5 py-2 pr-9 text-xs font-medium text-navy-950 shadow-xs focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                >
                  <option value="ALL">All Marine Regions</option>
                  {REGION_OPTIONS.filter((r) => r !== 'ALL').map((region) => (
                    <option key={region} value={region}>
                      {region}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ocean-400" />
              </div>
            </div>

            {/* 3. Start Date Filter */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ocean-600">
                Sample Start Date (UTC)
              </label>
              <div className="relative mt-1.5">
                <input
                  type="date"
                  min="2010-01-01"
                  max="2024-12-31"
                  value={filters.startDate}
                  onChange={handleStartDateChange}
                  className="w-full rounded-xl border border-ocean-200 bg-white px-3.5 py-2 text-xs font-medium text-navy-950 shadow-xs focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>

            {/* 4. End Date Filter */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ocean-600">
                Sample End Date (UTC)
              </label>
              <div className="relative mt-1.5">
                <input
                  type="date"
                  min="2010-01-01"
                  max="2024-12-31"
                  value={filters.endDate}
                  onChange={handleEndDateChange}
                  className="w-full rounded-xl border border-ocean-200 bg-white px-3.5 py-2 text-xs font-medium text-navy-950 shadow-xs focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>
          </div>

          {/* Quick Date Presets & Capabilities Note */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-ocean-100 pt-3 text-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-semibold text-ocean-600 mr-1">Date Presets:</span>
              {DATE_PRESETS.map((preset) => {
                const isSelected =
                  filters.startDate === preset.start && filters.endDate === preset.end;
                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => applyPreset(preset.start, preset.end)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all ${
                      isSelected
                        ? 'bg-navy-950 text-cyan-300 font-semibold shadow-xs'
                        : 'border border-ocean-200 bg-white text-ocean-700 hover:bg-ocean-100'
                    }`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1 text-[11px] text-ocean-500">
              <Info className="h-3.5 w-3.5 text-ocean-400 shrink-0" />
              <span>
                Region &amp; dates filter live MongoDB observations. Hotspot clustering mirrors detection run bounds.
              </span>
            </div>
          </div>

          {/* Active Filter Chips */}
          {activeCount > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 pt-1">
              <span className="text-[11px] font-semibold text-ocean-500">Active Criteria:</span>
              {filters.ocean !== 'ALL' && (
                <span className="inline-flex items-center gap-1 rounded-md bg-ocean-100 px-2 py-0.5 text-[11px] font-medium text-ocean-800">
                  Ocean: {filters.ocean}
                  <button
                    type="button"
                    onClick={() => onChange((prev) => ({ ...prev, ocean: 'ALL' }))}
                    className="hover:text-red-600"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )}
              {filters.region !== 'ALL' && (
                <span className="inline-flex items-center gap-1 rounded-md bg-ocean-100 px-2 py-0.5 text-[11px] font-medium text-ocean-800">
                  Region: {filters.region}
                  <button
                    type="button"
                    onClick={() => onChange((prev) => ({ ...prev, region: 'ALL' }))}
                    className="hover:text-red-600"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )}
              {filters.startDate && (
                <span className="inline-flex items-center gap-1 rounded-md bg-cyan-100 px-2 py-0.5 text-[11px] font-medium text-cyan-900">
                  From: {filters.startDate}
                  <button
                    type="button"
                    onClick={() => onChange((prev) => ({ ...prev, startDate: '' }))}
                    className="hover:text-red-600"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )}
              {filters.endDate && (
                <span className="inline-flex items-center gap-1 rounded-md bg-cyan-100 px-2 py-0.5 text-[11px] font-medium text-cyan-900">
                  Until: {filters.endDate}
                  <button
                    type="button"
                    onClick={() => onChange((prev) => ({ ...prev, endDate: '' }))}
                    className="hover:text-red-600"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              )}
            </div>
          )}
        </CardBody>
      )}
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Filtered Observations Table (Consistent Telemetry Evidence)
// -----------------------------------------------------------------------------
function FilteredObservationsTable({
  observations,
  totalCount,
  loading,
  onResetFilters,
  activeFilterCount,
}: {
  observations: PollutionObservation[];
  totalCount: number | null;
  loading: boolean;
  onResetFilters: () => void;
  activeFilterCount: number;
}) {
  const [tableSearch, setTableSearch] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const rowsPerPage = 10;

  // Local table search filter
  const displayedRows = useMemo(() => {
    let list = observations;
    if (tableSearch.trim()) {
      const q = tableSearch.toLowerCase();
      list = list.filter(
        (o) =>
          o.unique_id.toLowerCase().includes(q) ||
          (o.ocean && o.ocean.toLowerCase().includes(q)) ||
          (o.region && o.region.toLowerCase().includes(q)) ||
          (o.concentration_class && o.concentration_class.toLowerCase().includes(q))
      );
    }
    return list;
  }, [observations, tableSearch]);

  const totalPages = Math.max(1, Math.ceil(displayedRows.length / rowsPerPage));
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage;
    return displayedRows.slice(start, start + rowsPerPage);
  }, [displayedRows, currentPage]);

  return (
    <Card className="overflow-hidden border border-ocean-200/90 shadow-md">
      <CardHeader className="border-b border-ocean-100 bg-white/95 px-6 py-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                <Table className="h-4 w-4" />
              </span>
              <h2 className="text-lg font-bold text-navy-950">Filtered Marine Observation Records</h2>
              <span className="font-mono text-xs font-semibold text-ocean-600">
                [Showing {displayedRows.length} of {totalCount !== null ? totalCount.toLocaleString() : '—'} matching records]
              </span>
            </div>
            <p className="mt-1 text-xs text-ocean-600">
              Verified ground-truth sampling telemetry retrieved via FastAPI from the NOAA ocean-water dataset.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ocean-400" />
              <input
                type="text"
                placeholder="Search observation ID..."
                value={tableSearch}
                onChange={(e) => {
                  setTableSearch(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-48 rounded-xl border border-ocean-200 bg-ocean-50/70 py-1.5 pl-8 pr-3 text-xs font-medium text-navy-950 placeholder:text-ocean-400 focus:border-cyan-500 focus:bg-white focus:outline-none"
              />
            </div>
          </div>
        </div>
      </CardHeader>

      <CardBody className="p-0">
        {loading && (
          <div className="p-12 text-center text-sm font-medium text-cyan-700">
            <RefreshCw className="mx-auto mb-2 h-5 w-5 animate-spin" />
            Filtering observation records from MongoDB...
          </div>
        )}

        {!loading && displayedRows.length === 0 && (
          <div className="p-12 text-center">
            <Database className="mx-auto h-8 w-8 text-ocean-300" />
            <p className="mt-3 text-sm font-bold text-navy-950">No observation records found</p>
            <p className="mt-1 text-xs text-ocean-500">
              No marine observations match the active shared filter combination.
            </p>
            {activeFilterCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={onResetFilters}
                className="mt-4"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reset Shared Filters
              </Button>
            )}
          </div>
        )}

        {!loading && displayedRows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-xs">
              <thead>
                <tr className="border-b border-ocean-200 bg-ocean-50/70 text-[11px] font-semibold uppercase tracking-wider text-ocean-600">
                  <th className="py-3 pl-6 pr-3">Unique ID</th>
                  <th className="py-3 px-3">Sample Date (UTC)</th>
                  <th className="py-3 px-3">Concentration (pieces/m³)</th>
                  <th className="py-3 px-3">Ocean Basin</th>
                  <th className="py-3 px-3">Region / Sea</th>
                  <th className="py-3 pr-6 pl-3">Geographic Coordinates</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ocean-100 bg-white">
                {paginatedRows.map((obs) => {
                  const dateStr = obs.sample_date
                    ? new Date(obs.sample_date).toLocaleDateString()
                    : 'Unrecorded';
                  const isHigh = obs.measurement > 1.0;

                  return (
                    <tr key={obs.unique_id} className="transition-colors hover:bg-ocean-50/40">
                      <td className="py-3 pl-6 pr-3 font-mono font-medium text-cyan-800">
                        {obs.unique_id}
                      </td>
                      <td className="py-3 px-3 text-ocean-700">{dateStr}</td>
                      <td className="py-3 px-3 font-mono">
                        <span
                          className={`inline-block rounded px-2 py-0.5 font-bold ${
                            isHigh
                              ? 'bg-amber-100 text-amber-900'
                              : 'bg-cyan-50 text-cyan-800'
                          }`}
                        >
                          {obs.measurement.toFixed(4)} pieces/m³
                        </span>
                      </td>
                      <td className="py-3 px-3 text-navy-950 font-medium">{obs.ocean || 'Open Ocean'}</td>
                      <td className="py-3 px-3 text-ocean-600">{obs.region || '—'}</td>
                      <td className="py-3 pr-6 pl-3 font-mono text-[11px] text-ocean-500">
                        {obs.latitude.toFixed(3)}°, {obs.longitude.toFixed(3)}°
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!loading && displayedRows.length > 0 && (
          <div className="flex items-center justify-between border-t border-ocean-100 bg-ocean-50/50 px-6 py-3 text-xs text-ocean-600">
            <span>
              Showing {(currentPage - 1) * rowsPerPage + 1} to{' '}
              {Math.min(currentPage * rowsPerPage, displayedRows.length)} of {displayedRows.length}{' '}
              loaded rows
            </span>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="rounded-md border border-ocean-200 bg-white p-1 text-ocean-600 hover:bg-ocean-100 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-mono font-medium">
                Page {currentPage} of {totalPages}
              </span>
              <button
                type="button"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="rounded-md border border-ocean-200 bg-white p-1 text-ocean-600 hover:bg-ocean-100 disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: KPI Metric Card
// -----------------------------------------------------------------------------
function KpiMetricCard({
  label,
  value,
  unit,
  detail,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string;
  unit: string;
  detail: string;
  icon: typeof Database;
  accent: 'ocean' | 'cyan' | 'teal' | 'navy';
}) {
  const iconBgs = {
    ocean: 'bg-ocean-100 text-ocean-700',
    cyan: 'bg-cyan-100 text-cyan-700',
    teal: 'bg-teal-100 text-teal-700',
    navy: 'bg-navy-100 text-navy-800',
  };

  return (
    <Card className="border border-ocean-200/80 shadow-sm transition-all hover:border-ocean-300 hover:shadow-md">
      <CardBody className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-ocean-500">
              {label}
            </span>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="font-display text-3xl font-bold tracking-tight text-navy-950">
                {value}
              </span>
              <span className="font-mono text-xs font-medium text-ocean-600">{unit}</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ocean-600">{detail}</p>
          </div>
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBgs[accent]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Primary Pollution Trend Chart
// -----------------------------------------------------------------------------
interface HoverPoint {
  x: number;
  y: number;
  obs: PollutionObservation;
  index: number;
}

function PrimaryTrendChart({
  observations,
  loading,
  resetTrigger,
  hasActiveFilters,
}: {
  observations: PollutionObservation[];
  loading: boolean;
  resetTrigger: number;
  hasActiveFilters: boolean;
}) {
  const sortedObs = useMemo(() => {
    return [...observations]
      .filter((obs) => typeof obs.measurement === 'number' && !isNaN(obs.measurement))
      .sort((a, b) => {
        const da = a.sample_date ? new Date(a.sample_date).getTime() : 0;
        const db = b.sample_date ? new Date(b.sample_date).getTime() : 0;
        return da - db;
      });
  }, [observations]);

  // Zoom Window
  const [rangePreset, setRangePreset] = useState<'ALL' | 'LAST_50' | 'LAST_25' | 'PEAKS'>('ALL');
  const [startIndex, setStartIndex] = useState<number>(0);
  const [endIndex, setEndIndex] = useState<number>(Math.max(sortedObs.length - 1, 0));

  // Series Toggles
  const [showTrendLine, setShowTrendLine] = useState<boolean>(true);
  const [showAreaGradient, setShowAreaGradient] = useState<boolean>(true);
  const [showMeanBaseline, setShowMeanBaseline] = useState<boolean>(true);
  const [showPoints, setShowPoints] = useState<boolean>(true);

  // Inspector & Hover
  const [hoveredPoint, setHoveredPoint] = useState<HoverPoint | null>(null);
  const [inspectedObs, setInspectedObs] = useState<PollutionObservation | null>(null);

  useEffect(() => {
    setRangePreset('ALL');
    setStartIndex(0);
    setEndIndex(Math.max(sortedObs.length - 1, 0));
    setHoveredPoint(null);
    setInspectedObs(null);
    setShowTrendLine(true);
    setShowAreaGradient(true);
    setShowMeanBaseline(true);
    setShowPoints(true);
  }, [sortedObs.length, resetTrigger]);

  const handleRangePreset = (preset: 'ALL' | 'LAST_50' | 'LAST_25' | 'PEAKS') => {
    setRangePreset(preset);
    if (!sortedObs.length) return;
    const total = sortedObs.length;

    if (preset === 'ALL') {
      setStartIndex(0);
      setEndIndex(total - 1);
    } else if (preset === 'LAST_50') {
      setStartIndex(Math.floor(total * 0.5));
      setEndIndex(total - 1);
    } else if (preset === 'LAST_25') {
      setStartIndex(Math.floor(total * 0.75));
      setEndIndex(total - 1);
    } else if (preset === 'PEAKS') {
      let maxIdx = 0;
      let maxVal = -1;
      sortedObs.forEach((o, idx) => {
        if (o.measurement > maxVal) {
          maxVal = o.measurement;
          maxIdx = idx;
        }
      });
      const span = Math.max(Math.floor(total * 0.3), 10);
      setStartIndex(Math.max(0, maxIdx - Math.floor(span / 2)));
      setEndIndex(Math.min(total - 1, maxIdx + Math.floor(span / 2)));
    }
  };

  const handleZoomIn = () => {
    const currentSpan = endIndex - startIndex;
    if (currentSpan <= 6) return;
    const delta = Math.max(Math.floor(currentSpan * 0.2), 2);
    setStartIndex((prev) => Math.min(prev + delta, endIndex - 6));
    setEndIndex((prev) => Math.max(prev - delta, startIndex + 6));
    setRangePreset('ALL');
  };

  const handleZoomOut = () => {
    const total = sortedObs.length;
    const currentSpan = endIndex - startIndex;
    const delta = Math.max(Math.floor(currentSpan * 0.25), 3);
    setStartIndex((prev) => Math.max(0, prev - delta));
    setEndIndex((prev) => Math.min(total - 1, prev + delta));
    setRangePreset('ALL');
  };

  const handlePan = (direction: 'LEFT' | 'RIGHT') => {
    const total = sortedObs.length;
    const span = endIndex - startIndex;
    const step = Math.max(Math.floor(span * 0.25), 2);

    if (direction === 'LEFT') {
      const newStart = Math.max(0, startIndex - step);
      setStartIndex(newStart);
      setEndIndex(Math.min(total - 1, newStart + span));
    } else {
      const newEnd = Math.min(total - 1, endIndex + step);
      setEndIndex(newEnd);
      setStartIndex(Math.max(0, newEnd - span));
    }
  };

  const handleReset = () => {
    setRangePreset('ALL');
    setStartIndex(0);
    setEndIndex(Math.max(sortedObs.length - 1, 0));
    setHoveredPoint(null);
    setInspectedObs(null);
    setShowTrendLine(true);
    setShowAreaGradient(true);
    setShowMeanBaseline(true);
    setShowPoints(true);
  };

  const visibleObs = useMemo(() => {
    if (!sortedObs.length) return [];
    const validStart = Math.max(0, Math.min(startIndex, sortedObs.length - 1));
    const validEnd = Math.max(validStart + 1, Math.min(endIndex + 1, sortedObs.length));
    return sortedObs.slice(validStart, validEnd);
  }, [sortedObs, startIndex, endIndex]);

  const svgWidth = 1000;
  const svgHeight = 360;
  const padLeft = 70;
  const padRight = 35;
  const padTop = 30;
  const padBottom = 55;
  const chartWidth = svgWidth - padLeft - padRight;
  const chartHeight = svgHeight - padTop - padBottom;

  const measurements = visibleObs.map((o) => o.measurement);
  const rawMax = measurements.length ? Math.max(...measurements) : 1;
  const maxVal = Math.max(rawMax * 1.15, 0.2);
  const minVal = 0;
  const valRange = maxVal - minVal || 1;

  const points = useMemo(() => {
    if (!visibleObs.length) return [];
    return visibleObs.map((obs, idx) => {
      const x =
        visibleObs.length === 1
          ? padLeft + chartWidth / 2
          : padLeft + (idx / (visibleObs.length - 1)) * chartWidth;
      const y = padTop + chartHeight - ((obs.measurement - minVal) / valRange) * chartHeight;
      return { x, y, obs, index: startIndex + idx };
    });
  }, [visibleObs, chartWidth, chartHeight, padLeft, padTop, minVal, valRange, startIndex]);

  const linePathD = useMemo(() => {
    if (!points.length) return '';
    return points.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '');
  }, [points]);

  const areaPathD = useMemo(() => {
    if (!points.length) return '';
    const bottomY = padTop + chartHeight;
    const firstX = points[0].x.toFixed(1);
    const lastX = points[points.length - 1].x.toFixed(1);
    return `${linePathD} L ${lastX},${bottomY} L ${firstX},${bottomY} Z`;
  }, [linePathD, points, padTop, chartHeight]);

  const yTicks = useMemo(() => {
    const steps = 4;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const val = (maxVal / steps) * i;
      const y = padTop + chartHeight - (val / valRange) * chartHeight;
      return { val, y };
    });
  }, [maxVal, valRange, padTop, chartHeight]);

  const xTicks = useMemo(() => {
    if (points.length < 2) return points;
    const count = Math.min(6, points.length);
    const interval = (points.length - 1) / (count - 1);
    return Array.from({ length: count }, (_, i) => {
      const idx = Math.min(Math.round(i * interval), points.length - 1);
      return points[idx];
    });
  }, [points]);

  const meanVal = measurements.length
    ? measurements.reduce((a, b) => a + b, 0) / measurements.length
    : 0;
  const meanY = padTop + chartHeight - ((meanVal - minVal) / valRange) * chartHeight;

  const dateRangeDisplay = useMemo(() => {
    if (!visibleObs.length) return '—';
    const d0 = visibleObs[0].sample_date;
    const d1 = visibleObs[visibleObs.length - 1].sample_date;
    const firstDate = d0 ? new Date(d0).toLocaleDateString() : 'Initial sample';
    const lastDate = d1 ? new Date(d1).toLocaleDateString() : 'Latest sample';
    return `${firstDate} → ${lastDate}`;
  }, [visibleObs]);

  return (
    <Card className="overflow-hidden border border-ocean-200/90 shadow-md">
      <CardHeader className="border-b border-ocean-100 bg-white/95 px-6 py-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
                  <TrendingUp className="h-4 w-4" />
                </span>
                <h2 className="text-lg font-bold text-navy-950">Primary Marine Pollution Trend</h2>
                <span className="font-mono text-xs font-semibold text-ocean-600">
                  [{visibleObs.length} samples shown]
                </span>
              </div>
              <p className="mt-1 text-xs text-ocean-600">
                Chronological microplastics concentration profile responding to shared region and date filters.
              </p>
            </div>

            {/* Presets and Zoom */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center rounded-lg border border-ocean-200 bg-ocean-50/70 p-1">
                {(['ALL', 'LAST_50', 'LAST_25', 'PEAKS'] as const).map((preset) => {
                  const labels = {
                    ALL: 'Window All',
                    LAST_50: '50% Recent',
                    LAST_25: '25% Recent',
                    PEAKS: 'Peak Spike',
                  };
                  return (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => handleRangePreset(preset)}
                      className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all ${
                        rangePreset === preset
                          ? 'bg-navy-950 text-cyan-300 shadow-xs'
                          : 'text-ocean-700 hover:bg-ocean-100/80 hover:text-navy-950'
                      }`}
                    >
                      {labels[preset]}
                    </button>
                  );
                })}
              </div>

              <div className="flex items-center gap-1 rounded-lg border border-ocean-200 bg-white p-1">
                <button
                  type="button"
                  onClick={() => handlePan('LEFT')}
                  disabled={startIndex === 0}
                  className="rounded p-1 text-ocean-600 hover:bg-ocean-50 disabled:opacity-30"
                  title="Pan left"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleZoomIn}
                  className="rounded p-1 text-ocean-700 hover:bg-cyan-50"
                  title="Zoom in"
                >
                  <ZoomIn className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleZoomOut}
                  disabled={startIndex === 0 && endIndex === sortedObs.length - 1}
                  className="rounded p-1 text-ocean-700 hover:bg-cyan-50 disabled:opacity-30"
                  title="Zoom out"
                >
                  <ZoomOut className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => handlePan('RIGHT')}
                  disabled={endIndex >= sortedObs.length - 1}
                  className="rounded p-1 text-ocean-600 hover:bg-ocean-50 disabled:opacity-30"
                  title="Pan right"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleReset}
                  className="ml-1 rounded px-2 py-1 text-[11px] font-semibold text-ocean-600 hover:bg-ocean-100"
                  title="Reset chart perspective"
                >
                  <RotateCcw className="inline h-3 w-3 mr-1" />
                  Reset
                </button>
              </div>
            </div>
          </div>

          {/* Series Visibility Legend Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ocean-100/80 pt-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-ocean-600">Series:</span>

              <button
                type="button"
                onClick={() => setShowTrendLine(!showTrendLine)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showTrendLine
                    ? 'border-cyan-400 bg-cyan-50/80 text-cyan-900 font-medium'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showTrendLine ? <Eye className="h-3.5 w-3.5 text-cyan-600" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                <span className="h-2 w-2 rounded-full bg-cyan-500" />
                Observed Trend (pieces/m³)
              </button>

              <button
                type="button"
                onClick={() => setShowAreaGradient(!showAreaGradient)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showAreaGradient
                    ? 'border-cyan-300 bg-cyan-50/60 text-cyan-800'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showAreaGradient ? <Eye className="h-3.5 w-3.5 text-cyan-500" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                Area Fill
              </button>

              <button
                type="button"
                onClick={() => setShowMeanBaseline(!showMeanBaseline)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showMeanBaseline
                    ? 'border-teal-400 bg-teal-50/80 text-teal-900 font-medium'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showMeanBaseline ? <Eye className="h-3.5 w-3.5 text-teal-600" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                <span className="h-0.5 w-3 border-t border-dashed border-teal-600" />
                Mean: {meanVal.toFixed(3)} pieces/m³
              </button>

              <button
                type="button"
                onClick={() => setShowPoints(!showPoints)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showPoints
                    ? 'border-ocean-300 bg-ocean-50 text-ocean-800'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showPoints ? <Eye className="h-3.5 w-3.5 text-ocean-600" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                Points
              </button>
            </div>

            <div className="flex items-center gap-1.5 font-mono text-[11px] text-ocean-600">
              <Calendar className="h-3.5 w-3.5 text-ocean-500" />
              <span>{dateRangeDisplay}</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardBody className="relative bg-white p-4 sm:p-6">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-xs">
            <div className="flex items-center gap-2 text-sm font-medium text-cyan-700">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Loading filtered trend telemetry...
            </div>
          </div>
        )}

        {!loading && visibleObs.length === 0 && (
          <div className="flex h-72 flex-col items-center justify-center text-center">
            <Waves className="h-8 w-8 text-ocean-300" />
            <p className="mt-3 text-sm font-bold text-navy-950">No trend data matching filter</p>
            <p className="mt-1 text-xs text-ocean-500 max-w-sm">
              Try widening the date range or selecting another ocean basin in the shared filter bar above.
            </p>
          </div>
        )}

        {visibleObs.length > 0 && (
          <div className="relative w-full">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="h-80 w-full sm:h-96"
              preserveAspectRatio="xMidYMid meet"
              onMouseLeave={() => setHoveredPoint(null)}
            >
              <defs>
                <linearGradient id="primaryTrendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.35" />
                  <stop offset="70%" stopColor="#0891b2" stopOpacity="0.08" />
                  <stop offset="100%" stopColor="#0e7490" stopOpacity="0.0" />
                </linearGradient>

                <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0891b2" floodOpacity="0.3" />
                </filter>
              </defs>

              {/* Y Grid & Ticks */}
              {yTicks.map(({ val, y }, idx) => (
                <g key={`y-${idx}`}>
                  <line
                    x1={padLeft}
                    y1={y}
                    x2={svgWidth - padRight}
                    y2={y}
                    stroke="#e2e8f0"
                    strokeWidth="1"
                    strokeDasharray={idx === 0 ? undefined : '4 4'}
                  />
                  <text
                    x={padLeft - 12}
                    y={y + 4}
                    textAnchor="end"
                    className="font-mono text-[11px] font-medium fill-ocean-500"
                  >
                    {val.toFixed(2)}
                  </text>
                </g>
              ))}

              <text
                x={padLeft - 10}
                y={padTop - 12}
                textAnchor="end"
                className="font-mono text-[10px] font-semibold uppercase tracking-wider fill-ocean-600"
              >
                pieces/m³
              </text>

              {showMeanBaseline && meanVal > 0 && (
                <g>
                  <line
                    x1={padLeft}
                    y1={meanY}
                    x2={svgWidth - padRight}
                    y2={meanY}
                    stroke="#0d9488"
                    strokeWidth="1.5"
                    strokeDasharray="6 4"
                  />
                  <text
                    x={svgWidth - padRight - 6}
                    y={meanY - 6}
                    textAnchor="end"
                    className="font-mono text-[10px] font-semibold fill-teal-700"
                  >
                    Avg {meanVal.toFixed(3)} pieces/m³
                  </text>
                </g>
              )}

              {showAreaGradient && areaPathD && (
                <path d={areaPathD} fill="url(#primaryTrendGradient)" />
              )}

              {showTrendLine && linePathD && (
                <path
                  d={linePathD}
                  fill="none"
                  stroke="#0891b2"
                  strokeWidth="2.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  filter="url(#glowEffect)"
                />
              )}

              <line
                x1={padLeft}
                y1={padTop + chartHeight}
                x2={svgWidth - padRight}
                y2={padTop + chartHeight}
                stroke="#94a3b8"
                strokeWidth="1.25"
              />

              {xTicks.map((p, idx) => {
                const rawDate = p.obs.sample_date ? new Date(p.obs.sample_date) : null;
                const formattedDate = rawDate && !isNaN(rawDate.getTime())
                  ? rawDate.toISOString().slice(0, 10)
                  : `Obs #${p.index + 1}`;

                return (
                  <g key={`x-${idx}`}>
                    <line
                      x1={p.x}
                      y1={padTop + chartHeight}
                      x2={p.x}
                      y2={padTop + chartHeight + 6}
                      stroke="#64748b"
                      strokeWidth="1.2"
                    />
                    <text
                      x={p.x}
                      y={padTop + chartHeight + 22}
                      textAnchor="middle"
                      className="font-mono text-[11px] font-medium fill-ocean-600"
                    >
                      {formattedDate}
                    </text>
                  </g>
                );
              })}

              {points.map((p) => {
                const isHovered = hoveredPoint?.index === p.index;
                const isInspected = inspectedObs?.unique_id === p.obs.unique_id;

                return (
                  <g key={`pt-${p.index}`}>
                    {showPoints && (
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r={isInspected ? 7 : isHovered ? 5.5 : 3}
                        fill={isInspected ? '#f97316' : isHovered ? '#0891b2' : '#0284c7'}
                        stroke="#ffffff"
                        strokeWidth={isInspected ? 2.5 : isHovered ? 2 : 1}
                        className="transition-all duration-150"
                      />
                    )}

                    {(isInspected || isHovered) && (
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r={isInspected ? 13 : 10}
                        fill="none"
                        stroke={isInspected ? '#f97316' : '#06b6d4'}
                        strokeWidth="2"
                        strokeOpacity="0.7"
                        className="animate-ping"
                      />
                    )}

                    <rect
                      x={p.x - 12}
                      y={padTop}
                      width={24}
                      height={chartHeight + 10}
                      fill="transparent"
                      className="cursor-pointer"
                      onMouseEnter={() => setHoveredPoint(p)}
                      onTouchStart={() => setHoveredPoint(p)}
                      onClick={() => setInspectedObs(p.obs)}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Hover Tooltip */}
            {hoveredPoint && (
              <div
                className="pointer-events-none absolute z-20 w-64 rounded-xl border border-ocean-700 bg-navy-950/95 p-3.5 text-white shadow-2xl backdrop-blur-md transition-all duration-75"
                style={{
                  left: `${Math.min(
                    Math.max(12, (hoveredPoint.x / svgWidth) * 100 - 15),
                    72
                  )}%`,
                  top: `${Math.max(
                    8,
                    (hoveredPoint.y / svgHeight) * 100 - 45
                  )}%`,
                }}
              >
                <div className="flex items-center justify-between border-b border-ocean-800 pb-2 text-[11px]">
                  <span className="font-mono font-semibold text-cyan-400">
                    {hoveredPoint.obs.unique_id || `Sample #${hoveredPoint.index + 1}`}
                  </span>
                  <span className="text-ocean-300">
                    {hoveredPoint.obs.sample_date
                      ? new Date(hoveredPoint.obs.sample_date).toLocaleDateString()
                      : 'Date recorded'}
                  </span>
                </div>
                <div className="mt-2.5 space-y-1.5 text-xs">
                  <div className="flex items-baseline justify-between">
                    <span className="text-ocean-300">Microplastics:</span>
                    <span className="font-mono text-sm font-bold text-white">
                      {hoveredPoint.obs.measurement.toFixed(4)}{' '}
                      <span className="text-[10px] text-cyan-300">pieces/m³</span>
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between text-[11px]">
                    <span className="text-ocean-300">Region:</span>
                    <span className="font-medium text-ocean-100">
                      {hoveredPoint.obs.region || hoveredPoint.obs.ocean || 'Open Ocean'}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between text-[11px]">
                    <span className="text-ocean-300">Coordinates:</span>
                    <span className="font-mono text-ocean-200">
                      {hoveredPoint.obs.latitude.toFixed(2)}°, {hoveredPoint.obs.longitude.toFixed(2)}°
                    </span>
                  </div>
                </div>
                <p className="mt-2.5 border-t border-ocean-800/80 pt-1.5 text-[10px] font-medium text-cyan-300">
                  Click point to pin full telemetry record
                </p>
              </div>
            )}
          </div>
        )}

        {/* Inspected Point Drawer */}
        {inspectedObs && (
          <div className="mt-5 rounded-2xl border border-cyan-400/40 bg-navy-950 p-4 text-white shadow-xl animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center justify-between border-b border-ocean-800 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-300 font-mono text-xs font-bold">
                  PIN
                </span>
                <div>
                  <h3 className="text-sm font-bold text-white">
                    Inspected Observation: {inspectedObs.unique_id}
                  </h3>
                  <p className="text-[11px] text-ocean-300">
                    Recorded Date: {inspectedObs.sample_date ? new Date(inspectedObs.sample_date).toLocaleDateString() : 'N/A'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="rounded-lg bg-orange-500/20 px-2.5 py-1 font-mono text-xs font-bold text-orange-300">
                  {inspectedObs.measurement.toFixed(4)} pieces/m³
                </span>
                <button
                  type="button"
                  onClick={() => setInspectedObs(null)}
                  className="rounded-lg p-1 text-ocean-400 hover:bg-ocean-800 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="mt-3.5 grid gap-3 sm:grid-cols-2 md:grid-cols-4 text-xs">
              <div className="rounded-xl border border-ocean-800/80 bg-navy-900/60 p-2.5">
                <span className="text-[10px] text-ocean-400 uppercase">Ocean / Basin</span>
                <p className="mt-1 font-medium text-ocean-100">{inspectedObs.ocean || 'Open Ocean'}</p>
              </div>
              <div className="rounded-xl border border-ocean-800/80 bg-navy-900/60 p-2.5">
                <span className="text-[10px] text-ocean-400 uppercase">Region / Country</span>
                <p className="mt-1 font-medium text-ocean-100">
                  {inspectedObs.region || inspectedObs.country || 'International Waters'}
                </p>
              </div>
              <div className="rounded-xl border border-ocean-800/80 bg-navy-900/60 p-2.5">
                <span className="text-[10px] text-ocean-400 uppercase">Coordinates</span>
                <p className="mt-1 font-mono font-medium text-cyan-300">
                  {inspectedObs.latitude.toFixed(4)}°, {inspectedObs.longitude.toFixed(4)}°
                </p>
              </div>
              <div className="rounded-xl border border-ocean-800/80 bg-navy-900/60 p-2.5">
                <span className="text-[10px] text-ocean-400 uppercase">Sampling Method</span>
                <p className="mt-1 font-medium text-ocean-100">
                  {inspectedObs.sampling_method || inspectedObs.study_type || 'Standard Neuston Net'}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between border-t border-ocean-100 pt-3 text-xs text-ocean-600">
          <div className="flex items-center gap-1.5">
            <Info className="h-3.5 w-3.5 text-ocean-500" />
            <span>Hover to inspect, click any point to pin details, and use the zoom controls to isolate spikes.</span>
          </div>
          <div className="font-mono text-[11px] text-ocean-500">
            Window: {visibleObs.length} points | Total Dataset: {sortedObs.length}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Geographic Hotspot Map (Reflects Shared Ocean Filter & Local Layers)
// -----------------------------------------------------------------------------
function GeographicHotspotMap({
  hotspots,
  observations,
  resetTrigger,
  selectedOcean,
}: {
  hotspots: Hotspot[];
  observations: PollutionObservation[];
  resetTrigger: number;
  selectedOcean: string;
}) {
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [hoveredHotspot, setHoveredHotspot] = useState<Hotspot | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  const [showClusters, setShowClusters] = useState<boolean>(true);
  const [showObsPoints, setShowObsPoints] = useState<boolean>(true);
  const [showGraticule, setShowGraticule] = useState<boolean>(true);
  const [mapZoom, setMapZoom] = useState<number>(1);

  // Sync when shared ocean filter changes
  useEffect(() => {
    if (selectedOcean !== 'ALL') {
      setMapZoom(1.5);
    } else {
      setMapZoom(1);
    }
  }, [selectedOcean]);

  useEffect(() => {
    setSelectedHotspot(null);
    setHoveredHotspot(null);
    setSeverityFilter('ALL');
    setShowClusters(true);
    setShowObsPoints(true);
    setShowGraticule(true);
    setMapZoom(1);
  }, [resetTrigger]);

  const handleResetMap = () => {
    setSelectedHotspot(null);
    setHoveredHotspot(null);
    setSeverityFilter('ALL');
    setShowClusters(true);
    setShowObsPoints(true);
    setShowGraticule(true);
    setMapZoom(1);
  };

  const filteredHotspots = useMemo(() => {
    if (severityFilter === 'ALL') return hotspots;
    return hotspots.filter((h) => h.severity === severityFilter);
  }, [hotspots, severityFilter]);

  const severityColors: Record<
    string,
    { fill: string; stroke: string; glow: string; text: string; badge: string }
  > = {
    CRITICAL: {
      fill: 'rgba(239, 68, 68, 0.45)',
      stroke: '#ef4444',
      glow: '#ef4444',
      text: 'text-red-400',
      badge: 'border-red-500/50 bg-red-950/60 text-red-300',
    },
    HIGH: {
      fill: 'rgba(249, 115, 22, 0.45)',
      stroke: '#f97316',
      glow: '#f97316',
      text: 'text-orange-400',
      badge: 'border-orange-500/50 bg-orange-950/60 text-orange-300',
    },
    MEDIUM: {
      fill: 'rgba(20, 184, 166, 0.45)',
      stroke: '#14b8a6',
      glow: '#14b8a6',
      text: 'text-teal-400',
      badge: 'border-teal-500/50 bg-teal-950/60 text-teal-300',
    },
    LOW: {
      fill: 'rgba(6, 182, 212, 0.4)',
      stroke: '#06b6d4',
      glow: '#06b6d4',
      text: 'text-cyan-400',
      badge: 'border-cyan-500/50 bg-cyan-950/60 text-cyan-300',
    },
  };

  const baseWidth = 1000;
  const baseHeight = 500;
  const lonToX = (lon: number) => ((lon + 180) / 360) * baseWidth;
  const latToY = (lat: number) => ((90 - lat) / 180) * baseHeight;

  // Adaptive viewBox based on zoom and ocean filter
  const viewBox = useMemo(() => {
    if (mapZoom === 1 && selectedOcean === 'ALL') {
      return `0 0 ${baseWidth} ${baseHeight}`;
    }
    const w = baseWidth / mapZoom;
    const h = baseHeight / mapZoom;
    let cx = baseWidth / 2;
    let cy = baseHeight / 2;

    if (selectedOcean.includes('Pacific')) {
      cx = 280;
    } else if (selectedOcean.includes('Atlantic')) {
      cx = 400;
    } else if (selectedOcean.includes('Indian')) {
      cx = 680;
    } else if (selectedOcean.includes('Arctic')) {
      cy = 100;
    } else if (selectedOcean.includes('Southern')) {
      cy = 420;
    }

    const x = Math.max(0, Math.min(baseWidth - w, cx - w / 2));
    const y = Math.max(0, Math.min(baseHeight - h, cy - h / 2));
    return `${x} ${y} ${w} ${h}`;
  }, [mapZoom, selectedOcean]);

  return (
    <Card className="overflow-hidden border border-ocean-200/90 shadow-md">
      <CardHeader className="border-b border-ocean-100 bg-white/95 px-6 py-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-700">
                  <Globe2 className="h-4 w-4" />
                </span>
                <h2 className="text-lg font-bold text-navy-950">Global Geographic Pollution Map</h2>
                <span className="font-mono text-xs font-semibold text-ocean-600">
                  [{filteredHotspots.length} clusters in scope]
                </span>
              </div>
              <p className="mt-1 text-xs text-ocean-600">
                Spatial clustering (DBSCAN) showing clusters and observation markers filtered by shared scope.
              </p>
            </div>

            {/* Map Zoom Controls */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 rounded-lg border border-ocean-200 bg-white p-1">
                <button
                  type="button"
                  onClick={() => setMapZoom((z) => Math.min(2.5, z + 0.5))}
                  disabled={mapZoom >= 2.5}
                  className="rounded p-1 text-ocean-700 hover:bg-cyan-50 disabled:opacity-30"
                  title="Zoom in"
                >
                  <ZoomIn className="h-4 w-4" />
                </button>
                <span className="font-mono text-xs font-semibold text-navy-950 px-1">
                  {mapZoom.toFixed(1)}x
                </span>
                <button
                  type="button"
                  onClick={() => setMapZoom((z) => Math.max(1, z - 0.5))}
                  disabled={mapZoom <= 1}
                  className="rounded p-1 text-ocean-700 hover:bg-cyan-50 disabled:opacity-30"
                  title="Zoom out"
                >
                  <ZoomOut className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleResetMap}
                  className="ml-1 rounded px-2 py-1 text-[11px] font-semibold text-ocean-600 hover:bg-ocean-100"
                  title="Reset map view"
                >
                  <RotateCcw className="inline h-3 w-3 mr-1" />
                  Reset
                </button>
              </div>
            </div>
          </div>

          {/* Severity & Layer Toggles */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ocean-100/80 pt-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-ocean-600">Severity:</span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                <button
                  key={sev}
                  type="button"
                  onClick={() => setSeverityFilter(sev)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
                    severityFilter === sev
                      ? 'bg-navy-900 text-cyan-300 shadow-sm'
                      : 'border border-ocean-200 bg-white text-ocean-700 hover:bg-ocean-100'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-ocean-600">Layers:</span>
              <button
                type="button"
                onClick={() => setShowClusters(!showClusters)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showClusters
                    ? 'border-cyan-400 bg-cyan-50/80 text-cyan-900 font-medium'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showClusters ? <Eye className="h-3.5 w-3.5 text-cyan-600" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                Clusters
              </button>

              <button
                type="button"
                onClick={() => setShowObsPoints(!showObsPoints)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showObsPoints
                    ? 'border-cyan-300 bg-cyan-50/60 text-cyan-800'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showObsPoints ? <Eye className="h-3.5 w-3.5 text-cyan-500" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                Observations
              </button>

              <button
                type="button"
                onClick={() => setShowGraticule(!showGraticule)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                  showGraticule
                    ? 'border-ocean-300 bg-ocean-50 text-ocean-800'
                    : 'border-ocean-200 bg-white text-ocean-400 line-through'
                }`}
              >
                {showGraticule ? <Eye className="h-3.5 w-3.5 text-ocean-600" /> : <EyeOff className="h-3.5 w-3.5 text-ocean-400" />}
                Grid
              </button>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardBody className="relative bg-[#071724] p-0">
        <div className="relative h-[440px] w-full overflow-hidden sm:h-[480px] xl:h-[530px]">
          <svg
            viewBox={viewBox}
            className="h-full w-full select-none transition-all duration-300 ease-out"
            preserveAspectRatio="xMidYMid meet"
            onMouseLeave={() => setHoveredHotspot(null)}
          >
            <defs>
              <radialGradient id="bathymetry" cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="#0c2336" />
                <stop offset="100%" stopColor="#05121e" />
              </radialGradient>
            </defs>

            <rect width={baseWidth} height={baseHeight} fill="url(#bathymetry)" />

            {showGraticule &&
              [-60, -30, 0, 30, 60].map((lat) => (
                <g key={`lat-${lat}`}>
                  <line
                    x1={0}
                    y1={latToY(lat)}
                    x2={baseWidth}
                    y2={latToY(lat)}
                    stroke={lat === 0 ? '#0e7490' : '#1e3a52'}
                    strokeWidth={lat === 0 ? '1.5' : '0.8'}
                    strokeDasharray={lat === 0 ? '6 4' : '3 3'}
                    opacity={lat === 0 ? 0.7 : 0.4}
                  />
                  <text
                    x={12}
                    y={latToY(lat) - 4}
                    className="font-mono text-[9px] fill-ocean-400 opacity-60"
                  >
                    {lat > 0 ? `${lat}°N` : lat < 0 ? `${Math.abs(lat)}°S` : 'Equator 0°'}
                  </text>
                </g>
              ))}

            {showGraticule &&
              [-120, -60, 0, 60, 120].map((lon) => (
                <g key={`lon-${lon}`}>
                  <line
                    x1={lonToX(lon)}
                    y1={0}
                    x2={lonToX(lon)}
                    y2={baseHeight}
                    stroke={lon === 0 ? '#0e7490' : '#1e3a52'}
                    strokeWidth={lon === 0 ? '1.5' : '0.8'}
                    strokeDasharray={lon === 0 ? '6 4' : '3 3'}
                    opacity={lon === 0 ? 0.4 : 0.4}
                  />
                  <text
                    x={lonToX(lon) + 4}
                    y={baseHeight - 8}
                    className="font-mono text-[9px] fill-ocean-400 opacity-60"
                  >
                    {lon > 0 ? `${lon}°E` : lon < 0 ? `${Math.abs(lon)}°W` : 'Prime Meridian 0°'}
                  </text>
                </g>
              ))}

            <g fill="#142c42" stroke="#1f4666" strokeWidth="0.8" opacity="0.65">
              <path d="M 120 70 Q 180 55 240 75 Q 260 120 220 180 Q 180 200 150 160 Q 110 130 120 70 Z" />
              <path d="M 220 210 Q 280 230 260 330 Q 230 420 210 390 Q 190 300 220 210 Z" />
              <path d="M 460 70 Q 640 40 820 90 Q 780 180 680 190 Q 560 160 480 120 Z" />
              <path d="M 460 160 Q 550 160 550 260 Q 510 370 470 340 Q 430 250 460 160 Z" />
              <path d="M 760 280 Q 840 280 840 360 Q 770 380 750 330 Z" />
            </g>

            {showObsPoints &&
              observations.map((obs, idx) => (
                <circle
                  key={`obs-${idx}`}
                  cx={lonToX(obs.longitude)}
                  cy={latToY(obs.latitude)}
                  r={1.75}
                  fill="#38bdf8"
                  opacity={0.45}
                />
              ))}

            {showClusters &&
              filteredHotspots.map((hotspot) => {
                const cx = lonToX(hotspot.centroid.longitude);
                const cy = latToY(hotspot.centroid.latitude);
                const isSelected = selectedHotspot?.cluster_id === hotspot.cluster_id;
                const isHovered = hoveredHotspot?.cluster_id === hotspot.cluster_id;
                const style = severityColors[hotspot.severity] ?? severityColors.LOW;

                const radius = Math.min(Math.max(Math.sqrt(hotspot.observation_count) * 2.8, 9), 28);

                return (
                  <g
                    key={`cluster-${hotspot.cluster_id}`}
                    className="cursor-pointer transition-transform duration-150"
                    onMouseEnter={() => setHoveredHotspot(hotspot)}
                    onClick={() => setSelectedHotspot(hotspot)}
                  >
                    {(hotspot.severity === 'CRITICAL' || isSelected || isHovered) && (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={radius + (isSelected ? 9 : 6)}
                        fill="none"
                        stroke={style.stroke}
                        strokeWidth={isSelected ? '2.5' : '1.5'}
                        strokeDasharray="4 2"
                        opacity={isSelected ? 0.95 : 0.65}
                        className="animate-spin-slow"
                      />
                    )}

                    <circle
                      cx={cx}
                      cy={cy}
                      r={radius}
                      fill={style.fill}
                      stroke={style.stroke}
                      strokeWidth={isSelected ? '2.75' : isHovered ? '2.25' : '1.75'}
                    />

                    <text
                      x={cx}
                      y={cy + 3.5}
                      textAnchor="middle"
                      className="font-mono text-[10px] font-bold fill-white pointer-events-none drop-shadow"
                    >
                      {hotspot.cluster_id}
                    </text>
                  </g>
                );
              })}
          </svg>

          {hoveredHotspot && !selectedHotspot && (
            <div
              className="pointer-events-none absolute z-20 w-60 rounded-xl border border-ocean-700 bg-navy-950/95 p-3 text-white shadow-xl backdrop-blur-md transition-all duration-75"
              style={{
                left: `${Math.min(
                  Math.max(10, (lonToX(hoveredHotspot.centroid.longitude) / baseWidth) * 100 - 15),
                  72
                )}%`,
                top: `${Math.max(
                  8,
                  (latToY(hoveredHotspot.centroid.latitude) / baseHeight) * 100 - 32
                )}%`,
              }}
            >
              <div className="flex items-center justify-between border-b border-ocean-800 pb-1.5 text-[11px]">
                <span className="font-display font-bold text-cyan-300">
                  Cluster #{hoveredHotspot.cluster_id}
                </span>
                <span className={`font-mono font-bold text-[10px] ${severityColors[hoveredHotspot.severity]?.text}`}>
                  {hoveredHotspot.severity}
                </span>
              </div>
              <div className="mt-1.5 space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-ocean-300">Mean:</span>
                  <span className="font-mono font-bold text-white">
                    {hoveredHotspot.average_pollution.toFixed(3)} pieces/m³
                  </span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-ocean-300">Observations:</span>
                  <span className="font-mono text-ocean-100">{hoveredHotspot.observation_count} points</span>
                </div>
              </div>
            </div>
          )}

          {selectedHotspot && (
            <div className="absolute bottom-4 right-4 z-20 w-84 rounded-2xl border border-cyan-500/40 bg-navy-950/95 p-4 text-white shadow-2xl backdrop-blur-lg">
              <div className="flex items-center justify-between border-b border-ocean-800 pb-2.5">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-cyan-400" />
                  <span className="font-display font-bold">
                    Cluster #{selectedHotspot.cluster_id}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-bold ${
                      severityColors[selectedHotspot.severity]?.badge ?? ''
                    }`}
                  >
                    {selectedHotspot.severity}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedHotspot(null)}
                    className="rounded p-1 text-ocean-400 hover:text-white"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              <div className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-ocean-300">Dominant Region:</span>
                  <span className="font-medium text-ocean-100">
                    {selectedHotspot.region || selectedHotspot.ocean || 'Open Ocean'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-300">Mean Concentration:</span>
                  <span className="font-mono font-bold text-cyan-300">
                    {selectedHotspot.average_pollution.toFixed(4)} pieces/m³
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-300">Max Measurement:</span>
                  <span className="font-mono text-ocean-100">
                    {selectedHotspot.maximum_pollution.toFixed(4)} pieces/m³
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-300">Observation Samples:</span>
                  <span className="font-mono text-ocean-100">
                    {selectedHotspot.observation_count} points
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-300">Centroid Coordinates:</span>
                  <span className="font-mono text-[11px] text-ocean-200">
                    {selectedHotspot.centroid.latitude.toFixed(2)}°,{' '}
                    {selectedHotspot.centroid.longitude.toFixed(2)}°
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="absolute bottom-4 left-4 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-ocean-700/60 bg-navy-950/85 px-4 py-2 text-[11px] text-ocean-200 backdrop-blur-md">
            <span className="font-semibold text-white">Cluster Severity:</span>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
              <span>Critical</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-orange-500" />
              <span>High</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-teal-500" />
              <span>Medium</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-500" />
              <span>Low</span>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Secondary Chart 1 - Hotspot Severity Breakdown
// -----------------------------------------------------------------------------
function SeverityBreakdownChart({
  hotspots,
  stats,
  resetTrigger,
}: {
  hotspots: Hotspot[];
  stats: HotspotStats | null;
  resetTrigger: number;
}) {
  const [selectedSev, setSelectedSev] = useState<string | null>(null);

  useEffect(() => {
    setSelectedSev(null);
  }, [resetTrigger]);

  const counts = useMemo(() => {
    const raw = {
      CRITICAL: hotspots.filter((h) => h.severity === 'CRITICAL').length,
      HIGH: hotspots.filter((h) => h.severity === 'HIGH').length,
      MEDIUM: hotspots.filter((h) => h.severity === 'MEDIUM').length,
      LOW: hotspots.filter((h) => h.severity === 'LOW').length,
    };
    const total = Object.values(raw).reduce((a, b) => a + b, 0) || 1;
    return {
      CRITICAL: { count: raw.CRITICAL, pct: (raw.CRITICAL / total) * 100 },
      HIGH: { count: raw.HIGH, pct: (raw.HIGH / total) * 100 },
      MEDIUM: { count: raw.MEDIUM, pct: (raw.MEDIUM / total) * 100 },
      LOW: { count: raw.LOW, pct: (raw.LOW / total) * 100 },
      total,
    };
  }, [hotspots]);

  const severityConfigs = [
    { key: 'CRITICAL', label: 'Critical Severity', color: 'bg-red-500', barBg: 'bg-red-100', text: 'text-red-700' },
    { key: 'HIGH', label: 'High Severity', color: 'bg-orange-500', barBg: 'bg-orange-100', text: 'text-orange-700' },
    { key: 'MEDIUM', label: 'Medium Severity', color: 'bg-teal-500', barBg: 'bg-teal-100', text: 'text-teal-700' },
    { key: 'LOW', label: 'Low Severity', color: 'bg-cyan-500', barBg: 'bg-cyan-100', text: 'text-cyan-700' },
  ];

  return (
    <Card className="flex flex-col border border-ocean-200/80 shadow-sm">
      <CardHeader className="border-b border-ocean-100 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-100 text-orange-700">
              <BarChart3 className="h-4 w-4" />
            </span>
            <h3 className="text-base font-bold text-navy-950">Cluster Severity Profile</h3>
          </div>
          {selectedSev && (
            <button
              type="button"
              onClick={() => setSelectedSev(null)}
              className="text-[11px] font-semibold text-ocean-600 hover:text-navy-950"
            >
              Clear Filter
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-ocean-600">
          Distribution across DBSCAN risk thresholds ({counts.total} active in filter).
        </p>
      </CardHeader>

      <CardBody className="flex flex-1 flex-col justify-between p-5">
        <div className="space-y-4">
          {severityConfigs.map(({ key, label, color, barBg, text }) => {
            const data = counts[key as keyof typeof counts] as { count: number; pct: number };
            const isSelected = selectedSev === key;

            return (
              <div
                key={key}
                onClick={() => setSelectedSev(isSelected ? null : key)}
                className={`cursor-pointer rounded-xl p-2 transition-all ${
                  isSelected ? 'bg-ocean-100/70 ring-1 ring-cyan-500' : 'hover:bg-ocean-50/60'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 font-medium text-navy-900">
                    <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
                    {label}
                  </div>
                  <div className="flex items-center gap-2 font-mono">
                    <span className={`font-bold ${text}`}>{data.count} clusters</span>
                    <span className="text-ocean-500">({data.pct.toFixed(1)}%)</span>
                  </div>
                </div>
                <div className={`mt-2 h-2.5 w-full overflow-hidden rounded-full ${barBg}`}>
                  <div
                    className={`h-full rounded-full ${color} transition-all duration-500`}
                    style={{ width: `${Math.max(data.pct, 3)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 rounded-xl border border-ocean-100 bg-ocean-50/70 p-3.5 text-xs text-ocean-700">
          <div className="flex items-center justify-between">
            <span className="font-medium text-navy-900">Clustering Parameters:</span>
            <span className="font-mono text-ocean-600">eps: 150 km · min_samples: 10</span>
          </div>
          <p className="mt-1 text-[11px] text-ocean-500">
            Clusters represent localized microplastic concentrations exceeding background ocean levels.
          </p>
        </div>
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Secondary Chart 2 - Regional Pollution Comparison
// -----------------------------------------------------------------------------
function RegionalPollutionChart({
  observations,
  hotspots,
  resetTrigger,
}: {
  observations: PollutionObservation[];
  hotspots: Hotspot[];
  resetTrigger: number;
}) {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

  useEffect(() => {
    setSelectedRegion(null);
  }, [resetTrigger]);

  const regionAverages = useMemo(() => {
    const map: Record<string, { sum: number; count: number; max: number }> = {};

    observations.forEach((obs) => {
      const reg = obs.ocean || obs.region;
      if (!reg) return;
      if (!map[reg]) map[reg] = { sum: 0, count: 0, max: 0 };
      map[reg].sum += obs.measurement;
      map[reg].count += 1;
      map[reg].max = Math.max(map[reg].max, obs.measurement);
    });

    if (Object.keys(map).length === 0) {
      hotspots.forEach((h) => {
        const reg = h.ocean || h.region;
        if (!reg) return;
        if (!map[reg]) map[reg] = { sum: 0, count: 0, max: 0 };
        map[reg].sum += h.average_pollution;
        map[reg].count += 1;
        map[reg].max = Math.max(map[reg].max, h.maximum_pollution);
      });
    }

    const items = Object.entries(map).map(([region, { sum, count, max }]) => ({
      region,
      avg: sum / (count || 1),
      max,
      count,
    }));

    return items.sort((a, b) => b.avg - a.avg).slice(0, 5);
  }, [observations, hotspots]);

  const maxAvg = regionAverages.length ? Math.max(...regionAverages.map((r) => r.avg)) : 1;

  return (
    <Card className="flex flex-col border border-ocean-200/80 shadow-sm">
      <CardHeader className="border-b border-ocean-100 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-100 text-teal-700">
              <Waves className="h-4 w-4" />
            </span>
            <h3 className="text-base font-bold text-navy-950">Basin Density Comparison</h3>
          </div>
          {selectedRegion && (
            <button
              type="button"
              onClick={() => setSelectedRegion(null)}
              className="text-[11px] font-semibold text-ocean-600 hover:text-navy-950"
            >
              Reset
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-ocean-600">
          Ranked average concentration across active basins (pieces/m³). Tap row to inspect.
        </p>
      </CardHeader>

      <CardBody className="flex flex-1 flex-col justify-between p-5">
        <div className="space-y-3.5">
          {regionAverages.map(({ region, avg, max, count }) => {
            const pct = Math.min((avg / (maxAvg || 1)) * 100, 100);
            const isSelected = selectedRegion === region;

            return (
              <div
                key={region}
                onClick={() => setSelectedRegion(isSelected ? null : region)}
                className={`cursor-pointer rounded-xl p-2 transition-all ${
                  isSelected ? 'bg-teal-50 ring-1 ring-teal-400' : 'hover:bg-ocean-50/60'
                }`}
              >
                <div className="flex items-baseline justify-between text-xs">
                  <span className="max-w-[180px] truncate font-medium text-navy-900" title={region}>
                    {region}
                  </span>
                  <span className="font-mono font-bold text-teal-700">
                    {avg.toFixed(3)} <span className="text-[10px] text-ocean-500">pieces/m³</span>
                  </span>
                </div>
                <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-ocean-100">
                  <div
                    className="h-full rounded-full bg-teal-500 transition-all duration-500"
                    style={{ width: `${Math.max(pct, 5)}%` }}
                  />
                </div>
                {isSelected ? (
                  <div className="mt-2 flex items-center justify-between text-[11px] text-teal-900 bg-teal-100/60 rounded px-2 py-1">
                    <span>Peak: {max.toFixed(3)} pieces/m³</span>
                    <span className="font-mono">{count} samples</span>
                  </div>
                ) : (
                  <div className="mt-0.5 text-right font-mono text-[10px] text-ocean-400">
                    {count} sampling records
                  </div>
                )}
              </div>
            );
          })}

          {!regionAverages.length && (
            <p className="py-8 text-center text-xs text-ocean-500">
              No regional observation telemetry available for current filter.
            </p>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-ocean-100 pt-3 text-xs text-ocean-500">
          <span>Benchmark Unit: pieces/m³</span>
          <Button to="/data" variant="ghost" size="sm" className="px-0 text-cyan-700 hover:bg-transparent">
            Data Explorer <ArrowRight className="h-3 w-3" />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

// -----------------------------------------------------------------------------
// Component: Secondary Chart 3 - Cleanup Priority Action Queue
// -----------------------------------------------------------------------------
function PriorityActionQueue({
  recommendations,
  resetTrigger,
}: {
  recommendations: Recommendation[];
  resetTrigger: number;
}) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  useEffect(() => {
    setSelectedIdx(null);
  }, [resetTrigger]);

  const topPriorities = useMemo(() => {
    return [...recommendations]
      .sort((a, b) => (b.priority_score ?? 0) - (a.priority_score ?? 0))
      .slice(0, 4);
  }, [recommendations]);

  return (
    <Card className="flex flex-col border border-ocean-200/80 shadow-sm">
      <CardHeader className="border-b border-ocean-100 pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
              <Target className="h-4 w-4" />
            </span>
            <h3 className="text-base font-bold text-navy-950">Cleanup Priority Queue</h3>
          </div>
          <Badge variant="neutral">Score 0–100</Badge>
        </div>
        <p className="mt-1 text-xs text-ocean-600">
          Ranked recovery zones matching filtered scope. Click card to inspect action.
        </p>
      </CardHeader>

      <CardBody className="flex flex-1 flex-col justify-between p-5">
        <div className="space-y-3">
          {topPriorities.map((item, idx) => {
            const rawClusterId = item.cluster?.cluster_id ?? item.hotspot?.cluster_id ?? idx + 1;
            const clusterId = typeof rawClusterId === 'number' || typeof rawClusterId === 'string'
              ? String(rawClusterId)
              : String(idx + 1);
            const region = (item.cluster?.region ?? item.cluster?.ocean ?? 'Coastal Sector') as string;
            const score = typeof item.priority_score === 'number' ? item.priority_score.toFixed(1) : '—';
            const isCritical = item.priority_level === 'CRITICAL';
            const isSelected = selectedIdx === idx;

            return (
              <div
                key={`prio-${idx}`}
                onClick={() => setSelectedIdx(isSelected ? null : idx)}
                className={`cursor-pointer rounded-xl border p-3 shadow-xs transition-all ${
                  isSelected
                    ? 'border-cyan-400 bg-cyan-50/70 ring-1 ring-cyan-300'
                    : 'border-ocean-100 bg-white hover:border-ocean-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-navy-950 font-mono text-xs font-bold text-cyan-300">
                      #{idx + 1}
                    </span>
                    <div>
                      <p className="text-xs font-bold text-navy-950">Cluster {clusterId}</p>
                      <p className="text-[11px] text-ocean-500">{region}</p>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="flex items-baseline justify-end gap-1.5">
                      <span className="font-mono text-sm font-bold text-navy-950">{score}</span>
                      <span className="font-mono text-[10px] text-ocean-500">/ 100</span>
                    </div>
                    <span
                      className={`inline-block rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                        isCritical
                          ? 'bg-red-100 text-red-700'
                          : 'bg-orange-100 text-orange-700'
                      }`}
                    >
                      {item.priority_level || 'EVALUATED'}
                    </span>
                  </div>
                </div>

                {isSelected && (
                  <div className="mt-3 border-t border-cyan-200/80 pt-2 text-[11px] text-ocean-700">
                    <p className="font-semibold text-navy-950">Action Guidance:</p>
                    <p className="mt-0.5">{item.recommended_action || item.recommendation || 'Targeted barrier deployment recommended.'}</p>
                  </div>
                )}
              </div>
            );
          })}

          {!topPriorities.length && (
            <div className="rounded-xl border border-dashed border-ocean-200 bg-ocean-50/50 p-6 text-center text-xs text-ocean-500">
              No priority recommendations in the selected regional scope.
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-ocean-100 pt-3 text-xs">
          <span className="text-ocean-500">Weighted evaluation model</span>
          <Button to="/priority" variant="ghost" size="sm" className="px-0 text-cyan-700 hover:bg-transparent">
            Full Decision Queue <ArrowRight className="h-3 w-3" />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
