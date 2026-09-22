import { useEffect, useState } from 'react';
import {
  BarChart3,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  CircleHelp,
  Clock3,
  Database,
  Download,
  Eye,
  Filter,
  Layers3,
  ListFilter,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type PollutionObservation } from '@/lib/api/client';

const columns = [
  'Observation ID',
  'Date',
  'Region',
  'Ocean',
  'Marine setting',
  'Concentration',
];

const filterFields = [
  { label: 'Date from', value: '', type: 'date', icon: CalendarDays },
  { label: 'Date to', value: '', type: 'date', icon: CalendarDays },
  { label: 'Region', value: 'All regions', type: 'select', icon: Layers3 },
  { label: 'Ocean', value: 'All oceans', type: 'select', icon: Database },
  { label: 'Marine setting', value: 'All settings', type: 'select', icon: SlidersHorizontal },
  { label: 'Concentration range', value: 'Any concentration', type: 'select', icon: BarChart3 },
];

const visualizations = [
  { title: 'Observations over time', description: 'Temporal record coverage will appear here.', icon: Clock3 },
  { title: 'Concentration distribution', description: 'Distribution will appear here when values are loaded.', icon: BarChart3 },
  { title: 'Region distribution', description: 'Regional coverage will appear here when records are loaded.', icon: Layers3 },
];

export function DataExplorerPage() {
  const [columnMenuOpen, setColumnMenuOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState(columns);
  const [observations, setObservations] = useState<PollutionObservation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 25;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    oceanWatchApi.getObservations({ skip: page * pageSize, limit: pageSize })
      .then((response) => {
        if (!active) return;
        setObservations(response.data);
        setTotal(response.total);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [page]);

  const filteredObservations = observations.filter((observation) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return [observation.unique_id, observation.region, observation.ocean, observation.country]
      .some((value) => value?.toLowerCase().includes(query));
  });

  const toggleColumn = (column: string) => {
    setVisibleColumns((current) =>
      current.includes(column) ? current.filter((item) => item !== column) : [...current, column]
    );
  };

  return (
    <div>
      <PageHeader
        title="Data Explorer"
        description="Inspect the structured observations behind every OceanWatch insight with a workspace designed for clarity."
      >
        <div className="flex flex-wrap gap-2">
          <Badge variant="neutral" icon={<Database className="h-3.5 w-3.5" />}>FastAPI-ready workspace</Badge>
          <Badge variant="cyan">{loading ? 'Loading records' : `${total.toLocaleString()} records`}</Badge>
        </div>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <Card className="border-navy-800 bg-navy-950 text-white">
          <CardBody className="p-5 sm:p-6">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300">
                  <Filter className="h-3.5 w-3.5" /> Observation filters
                </div>
                <p className="mt-2 text-sm text-ocean-300">Refine the observation query before records are requested from the API.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 xl:flex-1 xl:pl-8">
                {filterFields.map(({ label, value, type, icon: Icon }) => (
                  <label key={label} className="block">
                    <span className="mb-1.5 block text-[11px] font-medium text-ocean-300">{label}</span>
                    <span className="relative block">
                      <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" />
                      {type === 'date' ? (
                        <input type="date" aria-label={label} className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2.5 pl-9 text-sm text-white outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/30" />
                      ) : (
                        <select defaultValue={value} aria-label={label} className="w-full appearance-none rounded-lg border border-navy-700 bg-navy-900 py-2.5 pl-9 pr-9 text-sm text-white outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/30">
                          <option>{value}</option>
                        </select>
                      )}
                      {type === 'select' && <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" />}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </CardBody>
        </Card>

        <Card className="mt-6">
          <CardBody className="p-5 sm:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative w-full lg:max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ocean-400" />
                <input aria-label="Search observations" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by observation ID or location" className="w-full rounded-lg border border-ocean-200 bg-ocean-50 py-2.5 pl-9 pr-3 text-sm text-navy-950 placeholder:text-ocean-400 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100" />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Button variant="outline" size="sm" onClick={() => setColumnMenuOpen((open) => !open)} aria-expanded={columnMenuOpen}>
                    <Eye className="h-4 w-4" /> Columns <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                  {columnMenuOpen && (
                    <div className="absolute right-0 top-full z-10 mt-2 w-56 rounded-xl border border-ocean-200 bg-white p-2 shadow-card-hover">
                      <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-ocean-500">Visible columns</p>
                      {columns.map((column) => (
                        <button key={column} type="button" onClick={() => toggleColumn(column)} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs text-navy-800 hover:bg-ocean-50">
                          <span className="flex h-4 w-4 items-center justify-center rounded border border-ocean-300 text-cyan-600">{visibleColumns.includes(column) && <Check className="h-3 w-3" />}</span>
                          {column}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <Button variant="outline" size="sm"><ListFilter className="h-4 w-4" /> Sort <ChevronsUpDown className="h-3.5 w-3.5" /></Button>
                <Button variant="ghost" size="sm" disabled><Download className="h-4 w-4" /> Download</Button>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-ocean-100 pt-4 text-xs text-ocean-500">
              <span><strong className="font-semibold text-navy-800">{total.toLocaleString()}</strong> records available</span>
              <span className="inline-flex items-center gap-1.5"><CircleHelp className="h-3.5 w-3.5" /> Search filters the loaded page.</span>
            </div>
          </CardBody>
        </Card>

        <Card className="mt-6">
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-left text-sm">
                <thead>
                  <tr className="border-b border-ocean-200 bg-ocean-50 text-[10px] uppercase tracking-wider text-ocean-500">
                    {columns.filter((column) => visibleColumns.includes(column)).map((column) => (
                      <th key={column} className="whitespace-nowrap px-5 py-4 font-semibold"><button type="button" className="inline-flex items-center gap-1.5 hover:text-navy-800">{column}<ChevronsUpDown className="h-3 w-3" /></button></th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredObservations.map((observation) => (
                    <tr key={observation.unique_id} className="border-b border-ocean-100 last:border-0">
                      {visibleColumns.includes('Observation ID') && <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-navy-800">{observation.unique_id}</td>}
                      {visibleColumns.includes('Date') && <td className="whitespace-nowrap px-5 py-4 text-ocean-600">{observation.sample_date ? new Date(observation.sample_date).toLocaleDateString() : '—'}</td>}
                      {visibleColumns.includes('Region') && <td className="px-5 py-4 text-ocean-600">{observation.region ?? '—'}</td>}
                      {visibleColumns.includes('Ocean') && <td className="px-5 py-4 text-ocean-600">{observation.ocean ?? '—'}</td>}
                      {visibleColumns.includes('Marine setting') && <td className="px-5 py-4 text-ocean-600">{observation.study_type ?? observation.sampling_method ?? '—'}</td>}
                      {visibleColumns.includes('Concentration') && <td className="px-5 py-4 font-mono text-navy-800">{observation.measurement} {observation.unit}</td>}
                    </tr>
                  ))}
                  {!loading && !error && filteredObservations.length === 0 && (
                    <tr><td colSpan={Math.max(visibleColumns.length, 1)} className="px-5 py-16 text-center"><Database className="mx-auto h-5 w-5 text-ocean-400" /><p className="mt-4 text-sm font-semibold text-navy-800">{total === 0 ? 'No observations returned' : 'No loaded records match this search'}</p><p className="mt-1 text-xs text-ocean-500">The backend returned no records for this view.</p></td></tr>
                  )}
                  {error && <tr><td colSpan={Math.max(visibleColumns.length, 1)} className="px-5 py-16 text-center"><p className="text-sm font-semibold text-red-700">Unable to load observations</p><p className="mt-1 text-xs text-red-600">{error}</p></td></tr>}
                  {loading && <tr><td colSpan={Math.max(visibleColumns.length, 1)} className="px-5 py-16 text-center text-sm text-ocean-500">Loading observations...</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col gap-3 border-t border-ocean-100 px-5 py-4 text-xs text-ocean-500 sm:flex-row sm:items-center sm:justify-between">
              <span>Page {total ? page + 1 : 0} of {total ? Math.ceil(total / pageSize) : 0}</span>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" disabled={page === 0 || loading} onClick={() => setPage((current) => current - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
                <span className="px-2 text-ocean-400">{pageSize} per page</span>
                <Button variant="ghost" size="sm" disabled={loading || (page + 1) * pageSize >= total} onClick={() => setPage((current) => current + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          </CardBody>
        </Card>

        <div className="mt-8 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-600">Data pipeline views</p>
            <h2 className="mt-2 text-2xl font-bold text-navy-950">From observation to model input</h2>
          </div>
          <Badge variant="neutral">Schema-ready</Badge>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <DataLayerCard title="Raw observations" description="Source records exactly as received from the observation endpoint." icon={Database} tone="cyan" />
          <DataLayerCard title="Processed observations" description="Validated and normalized records prepared for analysis." icon={Layers3} tone="teal" />
          <DataLayerCard title="ML-ready data" description="Feature-ready data prepared for forecasting and prioritization workflows." icon={SlidersHorizontal} tone="navy" />
        </div>

        <div className="mt-8 grid gap-5 lg:grid-cols-3">
          {visualizations.map(({ title, description, icon: Icon }) => (
            <Card key={title}>
              <CardHeader>
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ocean-100 text-ocean-700"><Icon className="h-4 w-4" /></div>
                  <h2 className="text-sm font-bold text-navy-950">{title}</h2>
                </div>
              </CardHeader>
              <CardBody>
                <div className="relative flex h-44 items-center justify-center overflow-hidden rounded-xl border border-dashed border-ocean-300 bg-ocean-50 dot-pattern">
                  <span className="relative rounded-lg border border-white bg-white/90 px-3 py-2 text-center text-xs font-medium text-ocean-600 shadow-card">Visualization placeholder</span>
                </div>
                <p className="mt-3 text-xs leading-5 text-ocean-500">{description}</p>
              </CardBody>
            </Card>
          ))}
        </div>

        <div className="mt-8 flex items-start gap-3 rounded-xl border border-cyan-200 bg-cyan-50 p-4 text-sm text-cyan-900">
          <InfoIcon />
          <p className="leading-6"><strong className="font-semibold">Integration note:</strong> this interface is prepared for paginated, filterable observation responses from FastAPI. No record counts, distributions, or measurements are estimated in the frontend.</p>
        </div>
      </div>
    </div>
  );
}

function DataLayerCard({ title, description, icon: Icon, tone }: { title: string; description: string; icon: typeof Database; tone: 'cyan' | 'teal' | 'navy' }) {
  const toneClasses = {
    cyan: 'bg-cyan-100 text-cyan-700',
    teal: 'bg-teal-100 text-teal-700',
    navy: 'bg-navy-100 text-navy-700',
  };

  return (
    <Card>
      <CardBody>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${toneClasses[tone]}`}><Icon className="h-4 w-4" /></div>
        <h3 className="mt-5 text-base font-bold text-navy-950">{title}</h3>
        <p className="mt-2 text-sm leading-5 text-ocean-600">{description}</p>
        <div className="mt-5 flex items-center gap-1.5 border-t border-ocean-100 pt-4 text-xs text-ocean-500"><span className="h-1.5 w-1.5 rounded-full bg-ocean-300" /> Data source pending</div>
      </CardBody>
    </Card>
  );
}

function InfoIcon() {
  return <CircleHelp className="mt-0.5 h-5 w-5 shrink-0 text-cyan-700" />;
}
