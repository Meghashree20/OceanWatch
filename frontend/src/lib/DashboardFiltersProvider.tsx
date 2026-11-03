import { useMemo, useState, type ReactNode } from 'react';
import { DashboardFiltersContext, DEFAULT_DASHBOARD_FILTERS } from './dashboardFilters';

export function DashboardFiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState(DEFAULT_DASHBOARD_FILTERS);
  const value = useMemo(() => ({
    filters,
    setFilters,
    resetFilters: () => setFilters(DEFAULT_DASHBOARD_FILTERS),
  }), [filters]);

  return <DashboardFiltersContext.Provider value={value}>{children}</DashboardFiltersContext.Provider>;
}
