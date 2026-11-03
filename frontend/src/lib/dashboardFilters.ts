import { createContext, useContext, type Dispatch, type SetStateAction } from 'react';

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

export const DashboardFiltersContext = createContext<DashboardFiltersContextValue | null>(null);

export function useDashboardFilters() {
  const context = useContext(DashboardFiltersContext);
  if (!context) throw new Error('useDashboardFilters must be used within DashboardFiltersProvider');
  return context;
}
