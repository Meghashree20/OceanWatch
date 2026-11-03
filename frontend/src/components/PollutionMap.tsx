import { useEffect } from 'react';
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import type { Hotspot, PollutionObservation } from '@/lib/api/client';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';

const DEFAULT_CENTER: L.LatLngExpression = [20, 0];

function hasValidCoordinates(latitude: number | null | undefined, longitude: number | null | undefined): latitude is number {
  return (
    typeof latitude === 'number'
    && Number.isFinite(latitude)
    && typeof longitude === 'number'
    && Number.isFinite(longitude)
    && latitude >= -90
    && latitude <= 90
    && longitude >= -180
    && longitude <= 180
  );
}

function FitMapToData({
  observations,
  hotspots,
}: {
  observations: PollutionObservation[];
  hotspots: Hotspot[];
}) {
  const map = useMap();

  useEffect(() => {
    const points = [
      ...observations
        .filter((observation) => hasValidCoordinates(observation.latitude, observation.longitude))
        .map((observation) => [observation.latitude, observation.longitude] as L.LatLngTuple),
      ...hotspots
        .filter((hotspot) => hasValidCoordinates(hotspot.centroid.latitude, hotspot.centroid.longitude))
        .map((hotspot) => [hotspot.centroid.latitude, hotspot.centroid.longitude] as L.LatLngTuple),
    ];
    if (points.length === 0) return;
    map.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 8 });
  }, [map, observations, hotspots]);

  return null;
}

function severityColor(severity: string) {
  return {
    CRITICAL: '#ef4444',
    HIGH: '#f97316',
    MEDIUM: '#14b8a6',
    LOW: '#06b6d4',
  }[severity] ?? '#06b6d4';
}

export function PollutionMap({
  observations,
  hotspots,
  selectedHotspotId,
  onSelectHotspot,
}: {
  observations: PollutionObservation[];
  hotspots: Hotspot[];
  selectedHotspotId: string | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
}) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={2}
      minZoom={2}
      scrollWheelZoom
      className="h-full min-h-[30rem] w-full"
      aria-label="Interactive pollution observation and hotspot map"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitMapToData observations={observations} hotspots={hotspots} />
      <MarkerClusterGroup chunkedLoading showCoverageOnHover={false}>
        {observations
          .filter((observation) => hasValidCoordinates(observation.latitude, observation.longitude))
          .map((observation) => (
          <CircleMarker
            key={observation.unique_id}
            center={[observation.latitude, observation.longitude]}
            radius={5}
            pathOptions={{ color: '#0e7490', fillColor: '#22d3ee', fillOpacity: 0.8, weight: 1 }}
          >
            <Popup>
              <strong>Observation {observation.unique_id}</strong>
              <dl className="mt-2 grid grid-cols-[auto_auto] gap-x-3 gap-y-1 text-xs">
                <dt>Coordinates</dt><dd>{observation.latitude.toFixed(5)}, {observation.longitude.toFixed(5)}</dd>
                <dt>Measurement</dt><dd>{observation.measurement} {observation.unit}</dd>
                <dt>Date</dt><dd>{observation.sample_date ?? '—'}</dd>
                <dt>Region</dt><dd>{observation.region ?? '—'}</dd>
              </dl>
            </Popup>
          </CircleMarker>
          ))}
      </MarkerClusterGroup>
      <MarkerClusterGroup chunkedLoading showCoverageOnHover={false}>
        {hotspots
          .filter((hotspot) => hasValidCoordinates(hotspot.centroid.latitude, hotspot.centroid.longitude))
          .map((hotspot) => {
            const color = severityColor(hotspot.severity);
            const isSelected = selectedHotspotId === String(hotspot.cluster_id);
            const dateStart = hotspot.date_start ?? hotspot.date_range.start;
            const dateEnd = hotspot.date_end ?? hotspot.date_range.end;
            return (
              <CircleMarker
                key={`hotspot-${hotspot.cluster_id}`}
                center={[hotspot.centroid.latitude, hotspot.centroid.longitude]}
                radius={isSelected ? 15 : 11}
                pathOptions={{ color, fillColor: color, fillOpacity: 0.35, weight: 3 }}
                eventHandlers={{ click: () => onSelectHotspot(hotspot) }}
              >
                <Popup>
                  <strong>{hotspot.label}</strong>
                  <dl className="mt-2 grid grid-cols-[auto_auto] gap-x-3 gap-y-1 text-xs">
                    <dt>Hotspot ID</dt><dd>{hotspot.hotspot_id ?? `C-${hotspot.cluster_id}`}</dd>
                    <dt>Severity</dt><dd>{hotspot.severity}</dd>
                    <dt>Coordinates</dt><dd>{hotspot.centroid.latitude.toFixed(5)}, {hotspot.centroid.longitude.toFixed(5)}</dd>
                    <dt>Observations</dt><dd>{hotspot.observation_count.toLocaleString()}</dd>
                    <dt>Average</dt><dd>{hotspot.average_pollution} pieces/m³</dd>
                    <dt>Maximum</dt><dd>{hotspot.maximum_pollution} pieces/m³</dd>
                    <dt>Region</dt><dd>{hotspot.region ?? hotspot.dominant_region ?? '—'}</dd>
                    <dt>Ocean</dt><dd>{hotspot.ocean ?? '—'}</dd>
                    <dt>Date range</dt><dd>{dateStart ?? '—'} to {dateEnd ?? '—'}</dd>
                  </dl>
                </Popup>
              </CircleMarker>
            );
          })}
      </MarkerClusterGroup>
    </MapContainer>
  );
}
