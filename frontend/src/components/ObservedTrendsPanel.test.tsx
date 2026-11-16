import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ObservedTrendsPanel } from './ObservedTrendsPanel';
import type { PollutionTrendAssessment } from '@/lib/api/client';

const assessment: PollutionTrendAssessment = {
  status: 'ready',
  source: 'observed NOAA microplastic measurements',
  unit: 'pieces/m3',
  thresholds: {
    LOW: '< 1',
    MEDIUM: '>= 1 and < 10',
    HIGH: '>= 10 and < 100',
    CRITICAL: '>= 100',
  },
  windows: {
    previous: { start: '2024-01-01T00:00:00Z', end: '2024-03-31T00:00:00Z' },
    recent: { start: '2024-03-31T00:00:00Z', end: '2024-06-29T00:00:00Z' },
    days_per_window: 90,
  },
  latest_observation: '2024-06-29T00:00:00Z',
  data_freshness: { status: 'stale', age_days: 870 },
  coverage: { recent_observations: 3, previous_observations: 0, recent_comparable_cells: 1 },
  trends: [{
    location: { latitude: 10.5, longitude: 20.5, cell_size_degrees: 1 },
    risk_level: 'CRITICAL',
    trend_direction: 'unknown',
    change_types: ['no_comparable_baseline'],
    comparison: {
      recent_mean_pieces_m3: 120,
      previous_mean_pieces_m3: null,
      absolute_change_pieces_m3: null,
      relative_change: null,
      previous_risk_level: null,
    },
    evidence: {
      recent_observation_count: 3,
      recent_sampling_site_count: 1,
      previous_observation_count: null,
      previous_sampling_site_count: null,
      recent_period: { start: '2024-03-31T00:00:00Z', end: '2024-06-29T00:00:00Z' },
      previous_period: { start: '2024-01-01T00:00:00Z', end: '2024-03-31T00:00:00Z' },
      frequency_adjustment: 'mean of per-site means',
      data_quality: 'moderate',
      baseline_available: false,
      adjacent_previous_high_risk_cell: false,
    },
    source: 'observed NOAA microplastic measurements',
  }],
};

describe('ObservedTrendsPanel', () => {
  beforeEach(() => cleanup());

  it('distinguishes measured risk from forecasts and exposes a missing baseline', () => {
    const { container } = render(<ObservedTrendsPanel assessment={assessment} loading={false} error={null} onRefresh={vi.fn()} />);

    expect(screen.getByText('Measured · not a forecast')).toBeTruthy();
    expect(screen.getByText('No comparable baseline')).toBeTruthy();
    expect(container.textContent).toContain('Data freshness:');
    expect(container.textContent).toContain('stale');
    expect(container.textContent).toContain('870 days old');
    expect(screen.getByText(/no comparable baseline/)).toBeTruthy();
  });

  it('requests an explicit assessment refresh', () => {
    const onRefresh = vi.fn();
    render(<ObservedTrendsPanel assessment={assessment} loading={false} error={null} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByRole('button', { name: /Refresh assessment/ }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });
});
