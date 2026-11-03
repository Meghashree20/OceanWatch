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

export interface AuthUser {
  user_id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthSession {
  user: AuthUser;
  token_type: string;
  expires_in: number;
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

export interface SatelliteRasterMetadata {
  driver: string | null;
  width: number;
  height: number;
  count: number;
  crs: string | null;
  bounds: number[] | null;
}

export interface SatelliteCatalogItem {
  id: string;
  name: string;
  coordinates: number[];
  description: string;
  sample_file: string;
  has_local_sample: boolean;
}

export interface SatelliteAnalysis {
  id: string;
  name: string;
  coordinates: number[];
  description: string;
  sample_file: string | null;
  debris_pixel_count: number;
  total_pixels: number;
  debris_coverage_percentage: number;
  preview_png_base64: string;
  overlay_png_base64: string;
  raster_metadata: SatelliteRasterMetadata | null;
  status: string;
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
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
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
        credentials: 'include',
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          ...init.headers,
        },
      });

      if (!response.ok) {
        let detail = `status ${response.status}`;
        try {
          const errorBody = await response.json() as { error?: { message?: string }; detail?: string };
          detail = errorBody.error?.message ?? errorBody.detail ?? detail;
        } catch {
          // Preserve the status message when the server does not return JSON.
        }
        throw new ApiClientError(`OceanWatch API request failed: ${detail}.`, {
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

  async getAllObservations(params: {
    start_date?: string;
    end_date?: string;
    region?: string;
    ocean?: string;
    concentration_class?: string;
  } = {}): Promise<PaginatedObservations> {
    const limit = 1000;
    const firstPage = await this.getObservations({ ...params, skip: 0, limit });
    if (firstPage.data.length >= firstPage.total) return firstPage;

    const pageCount = Math.ceil(firstPage.total / limit);
    const remainingPages = await Promise.all(
      Array.from({ length: Math.max(0, pageCount - 1) }, (_, index) =>
        this.getObservations({ ...params, skip: (index + 1) * limit, limit }),
      ),
    );
    return {
      data: [firstPage, ...remainingPages].flatMap((page) => page.data),
      total: firstPage.total,
      skip: 0,
      limit: firstPage.total,
    };
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

  getHealth() {
    return this.requestJson<Record<string, unknown>>('/api/health', { signal: undefined });
  }

  signup(payload: { full_name: string; email: string; password: string; password_confirmation: string }) {
    return this.requestJson<AuthUser>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  login(payload: { email: string; password: string }) {
    return this.requestJson<AuthSession>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  logout() {
    return this.requestJson<{ status: string }>('/api/auth/logout', { method: 'POST' });
  }

  getCurrentUser() {
    return this.requestJson<AuthUser>('/api/auth/me');
  }

  getSatelliteCatalog() {
    return this.requestJson<SatelliteCatalogItem[]>('/api/satellite/catalog', { signal: undefined });
  }

  analyzeSatellite(file: File) {
    const body = new FormData();
    body.append('file', file);
    return this.requestJson<SatelliteAnalysis>('/api/satellite/analyze', {
      method: 'POST',
      body,
    });
  }

  analyzeRegisteredSatellite(hotspotId: string) {
    return this.requestJson<SatelliteAnalysis>(`/api/satellite/hotspots/${encodeURIComponent(hotspotId)}/analyze`, {
      method: 'GET',
    });
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
