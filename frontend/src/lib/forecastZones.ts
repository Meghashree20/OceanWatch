import type { PollutionObservation } from '@/lib/api/client';

export function forecastableObservationZones(
  observations: PollutionObservation[],
  trainedZones: string[] = [],
) {
  const trained = new Set(trainedZones);
  const monthsByRegion = new Map<string, Set<number>>();
  observations.forEach((observation) => {
    if (observation.unit.trim().toLowerCase() !== 'pieces/m3' || !observation.sample_date) return;
    const date = new Date(observation.sample_date);
    if (Number.isNaN(date.getTime())) return;
    const region = observation.region ?? 'Unknown';
    if (trained.size && !trained.has(region)) return;
    const months = monthsByRegion.get(region) ?? new Set<number>();
    months.add(date.getUTCFullYear() * 12 + date.getUTCMonth());
    monthsByRegion.set(region, months);
  });

  return [...monthsByRegion.entries()]
    .filter(([, months]) => {
      const ordered = [...months].sort((first, second) => first - second);
      const recent = ordered.slice(-6);
      return recent.length === 6 && recent.slice(1).every((month, index) => month - recent[index] === 1);
    })
    .map(([region]) => region)
    .sort();
}
