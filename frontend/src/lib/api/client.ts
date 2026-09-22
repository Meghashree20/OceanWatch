export type ApiCapability =
  | 'hotspots'
  | 'observations'
  | 'forecast'
  | 'priority'
  | 'modelMetrics'
  | 'summaryStatistics';

export interface ApiClientConfig {
  baseUrl: string;
  timeoutMs: number;
}

export interface PollutionObservation {
  unique_id: string;
  sample_date: string | null;
  latitude: number;
  longitude: number;
  measurement: number;
  unit: string;
  concentration_class: string | null;
  ocean: string | null;
  region: string | null;
  subregion: string | null;
  country: string | null;
  sampling_method: string | null;
  organization: string | null;
  study_type: string | null;
}

export interface PaginatedObservations {
  data: PollutionObservation[];
  total: number;
  skip: number;
  limit: number;
}

export interface DataStats {
  total_observations: number;
}

export interface Hotspot {
  cluster_id: number;
  hotspot_id: string | null;
  detection_run_id: string | null;
  created_at: string | null;
  dataset_hash: string | null;
  eps_km: number | null;
  min_samples: number | null;
  observation_count: number;
  centroid: { latitude: number; longitude: number };
  centroid_latitude: number | null;
  centroid_longitude: number | null;
  average_pollution: number;
  median_pollution: number | null;
  maximum_pollution: number;
  minimum_pollution: number;
  pollution_std: number;
  date_range: Record<string, string | null>;
  date_start: string | null;
  date_end: string | null;
  region: string | null;
  dominant_region: string | null;
  ocean: string | null;
  severity: string;
  label: string;
}

export interface HotspotList {
  data: Hotspot[];
  total: number;
  skip: number;
  limit: number;
}

export interface HotspotStats {
  total_clusters: number;
  total_observations_in_clusters: number;
  severity_distribution: Record<string, number>;
  last_run_eps_km: number | null;
  last_run_min_samples: number | null;
}

export interface ForecastPoint {
  date: string;
  value: number;
}

export interface Forecast {
  zone: string;
  horizon: number;
  historical_values: ForecastPoint[];
  predicted_values: ForecastPoint[];
  forecast_dates: string[];
  model_metrics: Record<string, unknown>;
  message: string;
}

export interface ForecastMetrics {
  status: string;
  metrics: Record<string, unknown> | null;
  message: string | null;
  aggregation: string | null;
  zones: string[] | null;
  train_rows: number | null;
  validation_rows: number | null;
  test_rows: number | null;
  validation_metrics: Record<string, unknown> | null;
  selected_params: Record<string, unknown> | null;
  periods: Record<string, unknown> | null;
  coverage: Record<string, unknown> | null;
}

export interface Recommendation {
  status: string;
  hotspot: Record<string, unknown>;
  cluster: Record<string, unknown>;
  priority_score: number | null;
  priority_level: string;
  factor_scores: Record<string, Record<string, unknown>>;
  weighted_components: Record<string, number> | null;
  weights: Record<string, number>;
  recommended_action: string;
  recommendation: string;
  contributions: Record<string, number> | null;
  calculation_explanation: string;
  missing_external_factors: string[];
}

export interface RecommendationList {
  data: Recommendation[];
  total: number;
}

export class ApiClientError extends Error {
  readonly status?: number;
  readonly capability?: ApiCapability;

  constructor(message: string, options: { status?: number; capability?: ApiCapability } = {}) {
    super(message);
    this.name = 'ApiClientError';
    this.status = options.status;
    this.capability = options.capability;
  }
}

export class MissingApiEndpointError extends ApiClientError {
  constructor(capability: ApiCapability) {
    super(`OceanWatch endpoint for ${capability} is not available in the current FastAPI contract.`, {
      capability,
    });
    this.name = 'MissingApiEndpointError';
  }
}

const defaultConfig: ApiClientConfig = {
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
  timeoutMs: Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 8000),
};

export class OceanWatchApiClient {
  private readonly config: ApiClientConfig;

  constructor(config: Partial<ApiClientConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
  }

  getConfig() {
    return { ...this.config };
  }

  async requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!this.config.baseUrl) {
      throw new ApiClientError('VITE_API_BASE_URL is not configured.');
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), this.config.timeoutMs);

    try {
      const response = await fetch(`${this.config.baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`, {
        ...init,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          ...init.headers,
        },
      });

      if (!response.ok) {
        throw new ApiClientError(`OceanWatch API request failed with status ${response.status}.`, {
          status: response.status,
        });
      }

      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiClientError('OceanWatch API request timed out.');
      }
      if (error instanceof ApiClientError) {
        throw error;
      }
      throw new ApiClientError('Unable to reach the OceanWatch API.');
    } finally {
      window.clearTimeout(timeout);
    }
  }

  getHotspots(params: { skip?: number; limit?: number; severity?: string; ocean?: string; region?: string } = {}) {
    return this.requestJson<HotspotList>(this.withQuery('/api/hotspots', params), { signal: undefined });
  }

  getObservations(params: {
    skip?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    region?: string;
    ocean?: string;
    concentration_class?: string;
  } = {}) {
    return this.requestJson<PaginatedObservations>(this.withQuery('/api/data', params), { signal: undefined });
  }

  getForecast(zoneId: string, horizon = 3) {
    return this.requestJson<Forecast>(this.withQuery(`/api/forecast/${encodeURIComponent(zoneId)}`, { horizon }), { signal: undefined });
  }

  getPriorityResults(limit = 100) {
    return this.requestJson<RecommendationList>(this.withQuery('/api/recommendations', { limit }), { signal: undefined });
  }

  getModelMetrics() {
    return this.requestJson<ForecastMetrics>('/api/forecast/model-metrics', { signal: undefined });
  }

  getSummaryStatistics() {
    return this.requestJson<DataStats>('/api/data/stats', { signal: undefined });
  }

  getHotspotStats() {
    return this.requestJson<HotspotStats>('/api/hotspots/stats', { signal: undefined });
  }

  private withQuery(path: string, params: Record<string, string | number | undefined>) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value));
    });
    const queryString = query.toString();
    return queryString ? `${path}?${queryString}` : path;
  }
}

export const oceanWatchApi = new OceanWatchApiClient();
