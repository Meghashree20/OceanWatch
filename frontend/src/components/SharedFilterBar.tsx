import { CalendarRange, Filter, Globe2, RefreshCw, Waves } from 'lucide-react';
import { useState } from 'react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useDashboardFilters } from '@/lib/dashboardFilters';

interface SharedFilterBarProps {
  availableRegions?: string[];
  availableOceans?: string[];
  datePresets?: Array<{ label: string; start: string; end: string }>;
  variant?: 'light' | 'dark';
  title?: string;
  description?: string;
  fields?: {
    region?: boolean;
    ocean?: boolean;
    dates?: boolean;
  };
}

export function SharedFilterBar({
  availableRegions = [],
  availableOceans = [],
  datePresets = [],
  variant = 'light',
  title = 'Shared filters',
  description = 'Filters stay synchronized across dashboard views.',
  fields = { region: true, ocean: true, dates: true },
}: SharedFilterBarProps) {
  const { filters, setFilters, resetFilters } = useDashboardFilters();
  const [dateError, setDateError] = useState<string | null>(null);
  const dark = variant === 'dark';
  const filtersActive = (fields.region && filters.region !== 'ALL') || (fields.ocean && filters.ocean !== 'ALL') || (fields.dates && Boolean(filters.startDate || filters.endDate));
  const labelClass = dark ? 'text-ocean-300' : 'text-ocean-600';
  const inputClass = dark
    ? 'border-navy-700 bg-navy-900 text-white focus:border-cyan-400 focus:ring-cyan-400/30'
    : 'border-ocean-200 bg-white text-navy-900 focus:border-cyan-500 focus:ring-cyan-500';

  const updateDate = (field: 'startDate' | 'endDate', value: string) => {
    const nextStart = field === 'startDate' ? value : filters.startDate;
    const nextEnd = field === 'endDate' ? value : filters.endDate;
    if (nextStart && nextEnd && nextStart > nextEnd) {
      setDateError('Start date must be on or before the end date.');
      return;
    }
    setDateError(null);
    setFilters((current) => ({ ...current, [field]: value }));
  };

  return (
    <Card className={dark ? 'border-navy-800 bg-navy-950 text-white' : undefined}>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${dark ? 'bg-cyan-500/10 text-cyan-300' : 'bg-ocean-100 text-ocean-700'}`}>
              <Filter className="h-4 w-4" />
            </div>
            <h2 className={`text-sm font-bold ${dark ? 'text-white' : 'text-navy-950'}`}>{title}</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={() => { setDateError(null); resetFilters(); }} disabled={!filtersActive} className={dark ? 'text-cyan-300 hover:bg-navy-900' : undefined}>
            <RefreshCw className="h-3.5 w-3.5" /> Reset filters
          </Button>
        </div>
        <p className={`mt-2 text-xs ${labelClass}`}>{description}</p>
      </CardHeader>
      <CardBody>
        <div className={`grid gap-4 sm:grid-cols-2 ${Object.values(fields).filter(Boolean).length === 1 ? 'lg:grid-cols-1' : 'lg:grid-cols-4'}`}>
          {fields.dates && <FilterField icon={CalendarRange} label="Start date (UTC)" labelClass={labelClass}>
            <input type="date" max={filters.endDate || undefined} value={filters.startDate} onChange={(event) => updateDate('startDate', event.target.value)} aria-invalid={Boolean(dateError)} className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 ${inputClass}`} />
          </FilterField>}
          {fields.dates && <FilterField icon={CalendarRange} label="End date (UTC, inclusive)" labelClass={labelClass}>
            <input type="date" min={filters.startDate || undefined} value={filters.endDate} onChange={(event) => updateDate('endDate', event.target.value)} aria-invalid={Boolean(dateError)} className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 ${inputClass}`} />
          </FilterField>}
          {fields.region && <FilterField icon={Globe2} label="Region" labelClass={labelClass}>
            <select value={filters.region} onChange={(event) => setFilters((current) => ({ ...current, region: event.target.value }))} className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 ${inputClass}`}>
              <option value="ALL">All regions</option>
              {availableRegions.map((region) => <option key={region} value={region}>{region}</option>)}
            </select>
          </FilterField>}
          {fields.ocean && <FilterField icon={Waves} label="Ocean" labelClass={labelClass}>
            <select value={filters.ocean} onChange={(event) => setFilters((current) => ({ ...current, ocean: event.target.value }))} className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 ${inputClass}`}>
              <option value="ALL">All oceans</option>
              {availableOceans.map((ocean) => <option key={ocean} value={ocean}>{ocean}</option>)}
            </select>
          </FilterField>}
        </div>
        {dateError && <p role="alert" className="mt-3 text-xs font-medium text-red-600">{dateError}</p>}
        {datePresets.length > 0 && <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-ocean-100 pt-3"><span className={`mr-1 text-xs font-semibold ${labelClass}`}>Date presets:</span>{datePresets.map((preset) => <button key={preset.label} type="button" onClick={() => { setDateError(null); setFilters((current) => ({ ...current, startDate: preset.start, endDate: preset.end })); }} className={`rounded-lg px-2.5 py-1 text-[11px] font-medium ${filters.startDate === preset.start && filters.endDate === preset.end ? 'bg-navy-950 text-cyan-300' : 'border border-ocean-200 bg-white text-ocean-700 hover:bg-ocean-50'}`}>{preset.label}</button>)}</div>}
      </CardBody>
    </Card>
  );
}

function FilterField({
  icon: Icon,
  label,
  labelClass,
  children,
}: {
  icon: typeof Filter;
  label: string;
  labelClass: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className={`mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider ${labelClass}`}>
        <Icon className="h-3.5 w-3.5" /> {label}
      </span>
      {children}
    </label>
  );
}
