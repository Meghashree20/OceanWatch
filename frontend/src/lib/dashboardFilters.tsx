import { createContext, useContext, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react';

export interface DashboardFilters {
  ocean: string;
  region: string;
  startDate: string;
  endDate: string;
}

export const DEFAULT_DASHBOARD_FILTERS: DashboardFilters = {
  ocean: 'ALL',
  region: 'ALL',
  startDate: '',
  endDate: '',
};

interface DashboardFiltersContextValue {
  filters: DashboardFilters;
  setFilters: Dispatch<SetStateAction<DashboardFilters>>;
  resetFilters: () => void;
}

const DashboardFiltersContext = createContext<DashboardFiltersContextValue | null>(null);

export function DashboardFiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<DashboardFilters>(DEFAULT_DASHBOARD_FILTERS);
  const value = useMemo(() => ({
    filters,
    setFilters,
    resetFilters: () => setFilters(DEFAULT_DASHBOARD_FILTERS),
  }), [filters]);

  return <DashboardFiltersContext.Provider value={value}>{children}</DashboardFiltersContext.Provider>;
}

export function useDashboardFilters() {
  const context = useContext(DashboardFiltersContext);
  if (!context) throw new Error('useDashboardFilters must be used within DashboardFiltersProvider');
  return context;
}
