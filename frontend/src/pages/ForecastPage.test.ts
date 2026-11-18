import { describe, expect, it } from 'vitest';
import type { PollutionObservation } from '@/lib/api/client';
import { forecastableObservationZones } from '@/lib/forecastZones';

function observation(region: string, month: number, unit = 'pieces/m3'): PollutionObservation {
  return {
    unique_id: `${region}-${month}`,
    sample_date: `2024-${String(month).padStart(2, '0')}-15T00:00:00Z`,
    latitude: 0,
    longitude: 0,
    measurement: 1,
    unit,
    concentration_class: null,
    ocean: null,
    region,
    subregion: null,
    country: null,
    sampling_method: null,
    organization: null,
    study_type: null,
  };
}

describe('forecastableObservationZones', () => {
  it('returns trained regions with six consecutive months of NOAA-unit observations', () => {
    const observations = [
      ...[1, 2, 3, 4, 5, 6].map((month) => observation('Eligible Sea', month)),
      ...[1, 2, 3, 5, 6, 7].map((month) => observation('Gap Sea', month)),
      ...[1, 2, 3, 4, 5, 6].map((month) => observation('Other Unit Sea', month, 'items/m3')),
    ];

    expect(forecastableObservationZones(observations, ['Eligible Sea', 'Gap Sea', 'Other Unit Sea']))
      .toEqual(['Eligible Sea']);
  });

  it('uses Unknown for missing regions and checks only the latest six months', () => {
    const observations = [
      ...[1, 2, 3, 4, 5, 6, 7].map((month) => observation('Older Gap Sea', month === 7 ? 8 : month)),
      ...[7, 8, 9, 10, 11, 12].map((month) => ({ ...observation('Unused', month), region: null })),
    ];

    expect(forecastableObservationZones(observations)).toEqual(['Unknown']);
  });
});
