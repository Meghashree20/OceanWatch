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
  is_admin: boolean;
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
  nodata: number | null;
  crs: string | null;
  bounds: number[] | null;
  transform: number[] | null;
  band_descriptions: Array<string | null> | null;
  band_scales: number[] | null;
  band_offsets: number[] | null;
  band_dtypes: string[] | null;
  band_units: Array<string | null> | null;
}

export interface SatelliteCatalogItem {
  id: string;
  name: string;
  coordinates: number[];
  description: string;
  sample_file: string;
  has_local_sample: boolean;
  inference_available: boolean;
  validation_status: string;
  unavailability_reason: string | null;
}

export interface SatelliteValidation {
  compatibility_status: 'VERIFIED_COMPATIBLE' | 'DECLARED_UNVERIFIED' | 'INCOMPATIBLE' | 'INVALID';
  validation_warnings: string[];
  validation_errors: string[];
  detected_band_count: number | null;
  verified_band_identities: string[] | null;
  crs: string | null;
  spatial_resolution_m: number | null;
  geographic_bounds: number[] | null;
  reflectance_calibration_status: string;
  source_provenance_status: string;
  invalid_pixel_percentage: number | null;
  inference_permitted: boolean;
  raster_metadata: Record<string, unknown> | null;
  band_statistics: Array<Record<string, number | null>>;
}

export interface SatelliteAnalysis {
  id: string;
  name: string;
  image_name: string;
  coordinates: number[];
  description: string;
  sample_file: string | null;
  debris_pixel_count: number;
  total_pixels: number;
  valid_pixel_count: number;
  confident_pixel_count: number;
  uncertain_pixel_count: number;
  uncertain_pixel_percentage: number;
  excluded_pixel_count: number;
  excluded_pixel_percentage: number;
  confidence_threshold: number;
  average_confidence: number;
  debris_coverage_percentage: number | null;
  predicted_classes: number[];
  class_statistics: Array<{
    class_id: number;
    class_name: string;
    color: string;
    pixel_count: number;
    percentage: number;
  }>;
  preview_png_base64: string;
  segmentation_mask_png_base64: string;
  segmentation_mask_geotiff_base64: string;
  overlay_png_base64: string;
  raster_metadata: SatelliteRasterMetadata | null;
  analysis_reliable: boolean;
  warnings: string[];
  status: string;
}

export interface HotspotStats {
  total_clusters: number;
  total_observations_in_clusters: number;
  severity_distribution: Record<string, number>;
  last_run_eps_km: number | null;
  last_run_min_samples: number | null;
}

export type PollutionRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface PollutionTrend {
  location: {
    latitude: number;
    longitude: number;
    cell_size_degrees: number;
  };
  risk_level: PollutionRiskLevel;
  trend_direction: 'increasing' | 'decreasing' | 'stable' | 'unknown';
  change_types: string[];
  comparison: {
    recent_mean_pieces_m3: number;
    previous_mean_pieces_m3: number | null;
    absolute_change_pieces_m3: number | null;
    relative_change: number | null;
    previous_risk_level: PollutionRiskLevel | null;
  };
  evidence: {
    recent_observation_count: number;
    recent_sampling_site_count: number;
    previous_observation_count: number | null;
    previous_sampling_site_count: number | null;
    recent_period: { start: string; end: string };
    previous_period: { start: string; end: string };
    frequency_adjustment: string;
    data_quality: 'high' | 'moderate' | 'low';
    baseline_available: boolean;
    adjacent_previous_high_risk_cell: boolean;
  };
  source: string;
}

export interface PollutionTrendAssessment {
  status: 'ready' | 'insufficient_data';
  source: string;
  unit: string;
  thresholds?: Record<PollutionRiskLevel, string>;
  windows: {
    previous: { start: string; end: string };
    recent: { start: string; end: string };
    days_per_window: number;
  } | null;
  latest_observation: string | null;
  data_freshness: {
    status: 'fresh' | 'aging' | 'stale' | 'unavailable';
    age_days: number | null;
  };
  coverage: Record<string, number>;
  trends: PollutionTrend[];
  alert_generation?: {
    status: 'refreshed' | 'suppressed_stale_data';
    max_data_age_days: number;
    reason?: string;
  };
  alerts?: PollutionAlertList;
}

export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'UNDER_INVESTIGATION' | 'RESOLVED' | 'CLOSED';

export interface PollutionAlert {
  alert_id: string;
  location: { latitude: number; longitude: number; cell_size_degrees: number };
  source: string;
  risk_level: PollutionRiskLevel;
  triggering_evidence: {
    change_types: string[];
    comparison: PollutionTrend['comparison'];
    evidence: PollutionTrend['evidence'];
  };
  status: AlertStatus;
  created_at: string;
  last_updated_at: string;
  responsible_user_id: string | null;
  status_history: Array<{
    status: AlertStatus;
    changed_at: string;
    changed_by: string;
    reason: string;
  }>;
}

export interface PollutionAlertList {
  data: PollutionAlert[];
  total: number;
}

export interface EnvironmentalOrganization {
  organization_id: string;
  name: string;
  contact_email: string;
  service_area: Record<string, unknown>;
  areas_served: string[];
  email_notifications_enabled: boolean;
  acknowledgment_required: boolean;
  verified: boolean;
  created_at: string;
}

export interface NotificationSuggestion {
  organization_id: string;
  name: string;
  contact_email: string;
  delivery_recipient_email: string | null;
  test_mode: boolean;
  areas_served: string[];
  subject: string;
  body: string;
}

export interface OrganizationNotification {
  notification_id: string;
  alert_id: string;
  organization_id: string;
  recipient_email: string;
  intended_recipient_email?: string;
  test_mode?: boolean;
  subject: string;
  delivery_status: 'PENDING' | 'SENT' | 'FAILED' | 'ACKNOWLEDGED';
  created_at: string;
  sent_at?: string;
  acknowledged_at?: string | null;
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
  forecastable_zones?: string[] | null;
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

export interface RecommendationContext {
  ecological_risk: number;
  human_exposure: number;
  cleanup_feasibility: number;
}

export type CleanupOperationStatus =
  | 'PLANNED'
  | 'ASSIGNED'
  | 'INSPECTION_SCHEDULED'
  | 'CLEANUP_STARTED'
  | 'COMPLETED'
  | 'CANCELLED';

export type CleanupActionType = 'INSPECTION' | 'PREVENTIVE_CLEANUP' | 'INCREASED_MONITORING';

export interface CleanupRecommendation {
  recommendation_id: string;
  action_type: CleanupActionType;
  priority: PollutionRiskLevel;
  location: { latitude: number; longitude: number };
  priority_score: number | null;
  priority_level: string;
  recommended_action: string;
  evidence: {
    hotspot: Record<string, unknown> | null;
    existing_priority_score: number | null;
    existing_priority_level: string | null;
    measured_trend: PollutionTrend | null;
    active_alert: {
      alert_id: string;
      risk_level: PollutionRiskLevel;
      status: AlertStatus;
      triggering_evidence?: Record<string, unknown>;
    } | null;
    data_freshness: { status: string; age_days: number | null };
  };
  uncertainty: string[];
}

export interface CleanupOperationEvidence {
  evidence_id: string;
  operation_id: string;
  evidence_type: 'BEFORE_PHOTO' | 'AFTER_PHOTO' | 'INSPECTION_NOTE' | 'SUPPORTING_EVIDENCE';
  notes: string | null;
  media_id: string | null;
  submitted_by: string;
  created_at: string;
  verification_status: 'PENDING' | 'VERIFIED' | 'REJECTED';
  verification_history: Array<{
    status: 'PENDING' | 'VERIFIED' | 'REJECTED';
    changed_at: string;
    changed_by: string;
    reason: string;
  }>;
}

export interface CleanupOperation {
  operation_id: string;
  recommendation_id: string;
  recommendation_snapshot: CleanupRecommendation;
  location: { latitude: number; longitude: number };
  alert_id: string | null;
  assigned_organization_id: string | null;
  assigned_organization_name?: string;
  responsible_coordinator_user_id: string | null;
  responsible_coordinator_name?: string;
  scheduled_at: string | null;
  status: CleanupOperationStatus;
  completion: {
    completed_at: string;
    waste_quantity: number | null;
    measurement_unit: string | null;
    quantity_classification: 'ESTIMATED' | 'REPORTED' | 'INDEPENDENTLY_VERIFIED' | null;
    verification_evidence_id?: string | null;
    verifier_name?: string | null;
    verifier_organization?: string | null;
  } | null;
  created_at: string;
  updated_at: string;
  status_history: Array<{
    status: CleanupOperationStatus;
    changed_at: string;
    changed_by: string;
    reason: string;
  }>;
  audit_history: Array<Record<string, unknown>>;
  evidence?: CleanupOperationEvidence[];
}

export interface CleanupOperationNotification {
  notification_id: string;
  operation_id: string;
  organization_id: string;
  recipient_email: string;
  intended_recipient_email?: string;
  test_mode?: boolean;
  subject: string;
  delivery_status: 'PENDING' | 'SENT' | 'FAILED' | 'ACKNOWLEDGED';
  created_at: string;
  sent_at?: string;
  acknowledged_at?: string | null;
}

export interface CleanupAnalytics {
  completed_operations: number;
  monthly_completed_operations: Array<{ month: string; completed_operations: number }>;
  quantities_by_unit_and_classification: Array<{
    measurement_unit: string;
    classification: 'ESTIMATED' | 'REPORTED' | 'INDEPENDENTLY_VERIFIED';
    total: number;
  }>;
  interpretation: string;
}

export type CitizenReportStatus = 'PENDING' | 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED';

export interface CitizenPollutionReport {
  report_id: string;
  category: 'PLASTIC_DEBRIS' | 'FISHING_GEAR' | 'OIL_OR_CHEMICAL' | 'WILDLIFE_IMPACT' | 'OTHER';
  description: string;
  location: { latitude: number; longitude: number };
  observed_at: string;
  media_id: string;
  submitted_by: string;
  status: CitizenReportStatus;
  created_at: string;
  updated_at: string;
  status_history: Array<{
    status: CitizenReportStatus;
    changed_at: string;
    changed_by: string;
    reason: string;
  }>;
}

const RECOMMENDATION_CONTEXT_KEY = 'oceanwatch.recommendation-context';

export function getSavedRecommendationContext(): RecommendationContext | undefined {
  try {
    const saved = localStorage.getItem(RECOMMENDATION_CONTEXT_KEY);
    if (!saved) return undefined;
    const parsed = JSON.parse(saved) as Partial<RecommendationContext>;
    const fields: (keyof RecommendationContext)[] = ['ecological_risk', 'human_exposure', 'cleanup_feasibility'];
    if (fields.some((field) => typeof parsed[field] !== 'number' || parsed[field]! < 0 || parsed[field]! > 100)) return undefined;
    return parsed as RecommendationContext;
  } catch {
    return undefined;
  }
}

export function saveRecommendationContext(context: RecommendationContext) {
  localStorage.setItem(RECOMMENDATION_CONTEXT_KEY, JSON.stringify(context));
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
          const errorBody = await response.json() as { error?: { message?: string; details?: { validation_errors?: string[] } }; detail?: string };
          detail = errorBody.error?.details?.validation_errors?.join(' ') ?? errorBody.error?.message ?? errorBody.detail ?? detail;
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

  async requestBlob(path: string): Promise<Blob> {
    if (!this.config.baseUrl) {
      throw new ApiClientError('VITE_API_BASE_URL is not configured.');
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), this.config.timeoutMs);
    try {
      const response = await fetch(`${this.config.baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`, {
        credentials: 'include',
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new ApiClientError(`OceanWatch API request failed: status ${response.status}.`, {
          status: response.status,
        });
      }
      return await response.blob();
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiClientError('OceanWatch API request timed out.');
      }
      if (error instanceof ApiClientError) throw error;
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

  getPriorityResults(
    limit = 100,
    context?: RecommendationContext,
  ) {
    return this.requestJson<RecommendationList>(this.withQuery('/api/recommendations', { limit, ...context }), { signal: undefined });
  }

  getCleanupRecommendations(limit = 100, context?: RecommendationContext) {
    return this.requestJson<{ data: CleanupRecommendation[]; total: number }>(
      this.withQuery('/api/cleanup/recommendations', { limit, ...context }),
    );
  }

  getCleanupOperations(status?: CleanupOperationStatus) {
    return this.requestJson<{ data: CleanupOperation[]; total: number; skip: number; limit: number }>(
      this.withQuery('/api/cleanup/operations', { status }),
    );
  }

  createCleanupOperation(recommendationId: string, scheduledAt?: string) {
    return this.requestJson<CleanupOperation>('/api/cleanup/operations', {
      method: 'POST',
      body: JSON.stringify({ recommendation_id: recommendationId, scheduled_at: scheduledAt }),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  getCleanupOperation(operationId: string) {
    return this.requestJson<CleanupOperation>(`/api/cleanup/operations/${encodeURIComponent(operationId)}`);
  }

  assignCleanupOperation(
    operationId: string,
    payload: { organization_id: string; responsible_coordinator_user_id?: string; scheduled_at?: string },
  ) {
    return this.requestJson<CleanupOperation>(`/api/cleanup/operations/${encodeURIComponent(operationId)}/assignment`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  updateCleanupOperationStatus(operationId: string, status: CleanupOperationStatus, reason: string) {
    return this.requestJson<CleanupOperation>(`/api/cleanup/operations/${encodeURIComponent(operationId)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason }),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  submitCleanupEvidence(
    operationId: string,
    evidenceType: CleanupOperationEvidence['evidence_type'],
    notes?: string,
    file?: File,
  ) {
    const body = new FormData();
    body.append('evidence_type', evidenceType);
    if (notes) body.append('notes', notes);
    if (file) body.append('file', file);
    return this.requestJson<CleanupOperationEvidence>(
      `/api/cleanup/operations/${encodeURIComponent(operationId)}/evidence`,
      { method: 'POST', body },
    );
  }

  verifyCleanupEvidence(operationId: string, evidenceId: string, status: 'VERIFIED' | 'REJECTED', reason: string) {
    return this.requestJson<CleanupOperationEvidence>(
      `/api/cleanup/operations/${encodeURIComponent(operationId)}/evidence/${encodeURIComponent(evidenceId)}/verification`,
      {
        method: 'PATCH',
        body: JSON.stringify({ status, reason }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  downloadCleanupEvidence(evidenceId: string) {
    return this.requestBlob(`/api/cleanup/evidence/${encodeURIComponent(evidenceId)}/download`);
  }

  completeCleanupOperation(
    operationId: string,
    payload: {
      completed_at: string;
      waste_quantity?: number;
      measurement_unit?: string;
      quantity_classification?: 'ESTIMATED' | 'REPORTED' | 'INDEPENDENTLY_VERIFIED';
      verification_evidence_id?: string;
      verifier_name?: string;
      verifier_organization?: string;
    },
  ) {
    return this.requestJson<CleanupOperation>(`/api/cleanup/operations/${encodeURIComponent(operationId)}/completion`, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  sendCleanupAssignmentNotification(operationId: string) {
    return this.requestJson<CleanupOperationNotification>(
      `/api/cleanup/operations/${encodeURIComponent(operationId)}/notifications`,
      {
        method: 'POST',
        body: JSON.stringify({ approved: true }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  getCleanupAssignmentNotifications(operationId: string) {
    return this.requestJson<{
      data: CleanupOperationNotification[];
      total: number;
      test_mode: boolean;
      delivery_recipient_email: string | null;
    }>(
      `/api/cleanup/operations/${encodeURIComponent(operationId)}/notifications`,
    );
  }

  acknowledgeCleanupAssignment(notificationId: string) {
    return this.requestJson<CleanupOperationNotification>(
      `/api/cleanup/notifications/${encodeURIComponent(notificationId)}/acknowledge`,
      { method: 'PATCH' },
    );
  }

  getCleanupAnalytics() {
    return this.requestJson<CleanupAnalytics>('/api/cleanup/analytics');
  }

  getCitizenReports() {
    return this.requestJson<{ data: CitizenPollutionReport[]; total: number }>('/api/citizen-reports');
  }

  submitCitizenReport(payload: {
    category: CitizenPollutionReport['category'];
    description: string;
    latitude: number;
    longitude: number;
    observed_at: string;
    file: File;
  }) {
    const body = new FormData();
    body.append('category', payload.category);
    body.append('description', payload.description);
    body.append('latitude', String(payload.latitude));
    body.append('longitude', String(payload.longitude));
    body.append('observed_at', payload.observed_at);
    body.append('file', payload.file);
    return this.requestJson<CitizenPollutionReport>('/api/citizen-reports', { method: 'POST', body });
  }

  moderateCitizenReport(
    reportId: string,
    status: 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED',
    reason: string,
  ) {
    return this.requestJson<CitizenPollutionReport>(
      `/api/citizen-reports/${encodeURIComponent(reportId)}/moderation`,
      {
        method: 'PATCH',
        body: JSON.stringify({ status, reason }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  downloadCitizenReportPhoto(reportId: string) {
    return this.requestBlob(`/api/citizen-reports/${encodeURIComponent(reportId)}/photo`);
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

  analyzeSatellite(file: File, manifestJson?: string, siteId?: string) {
    const body = new FormData();
    body.append('file', file);
    if (manifestJson) body.append('provenance_manifest_json', manifestJson);
    if (siteId) body.append('site_id', siteId);
    return this.requestJson<SatelliteAnalysis>('/api/satellite/analyze', {
      method: 'POST',
      body,
    });
  }

  validateSatellite(file: File, manifestJson?: string, siteId?: string) {
    const body = new FormData();
    body.append('file', file);
    if (manifestJson) body.append('provenance_manifest_json', manifestJson);
    if (siteId) body.append('site_id', siteId);
    return this.requestJson<SatelliteValidation>('/api/satellite/validate', { method: 'POST', body });
  }

  analyzeRegisteredSatellite(hotspotId: string) {
    return this.requestJson<SatelliteAnalysis>(`/api/satellite/hotspots/${encodeURIComponent(hotspotId)}/analyze`, {
      method: 'GET',
    });
  }

  getHotspotStats() {
    return this.requestJson<HotspotStats>('/api/hotspots/stats', { signal: undefined });
  }

  getPollutionTrends(windowDays = 90) {
    return this.requestJson<PollutionTrendAssessment>(
      this.withQuery('/api/intelligence/trends', { window_days: windowDays }),
      { signal: undefined },
    );
  }

  assessPollutionRisk() {
    return this.requestJson<PollutionTrendAssessment>('/api/intelligence/assess', { method: 'POST' });
  }

  getPollutionAlerts(status?: AlertStatus) {
    return this.requestJson<PollutionAlertList>(
      this.withQuery('/api/intelligence/alerts', { status }),
    );
  }

  updatePollutionAlert(alertId: string, status: AlertStatus) {
    return this.requestJson<PollutionAlert>(`/api/intelligence/alerts/${encodeURIComponent(alertId)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  getOrganizations(includeUnverified = false) {
    return this.requestJson<{ data: EnvironmentalOrganization[] }>(
      this.withQuery('/api/intelligence/organizations', { include_unverified: includeUnverified ? 1 : 0 }),
    );
  }

  createOrganization(payload: {
    name: string;
    contact_email: string;
    service_area: Record<string, unknown>;
    areas_served: string[];
    email_notifications_enabled: boolean;
    acknowledgment_required: boolean;
  }) {
    return this.requestJson<EnvironmentalOrganization>('/api/intelligence/organizations', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  verifyOrganization(organizationId: string, verified: boolean) {
    return this.requestJson<EnvironmentalOrganization>(
      `/api/intelligence/organizations/${encodeURIComponent(organizationId)}/verification`,
      {
        method: 'PATCH',
        body: JSON.stringify({ verified }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  previewOrganizationNotifications(alertId: string) {
    return this.requestJson<{ data: NotificationSuggestion[]; total: number }>(
      `/api/intelligence/alerts/${encodeURIComponent(alertId)}/organizations`,
    );
  }

  sendOrganizationNotification(alertId: string, organizationId: string) {
    return this.requestJson<OrganizationNotification>(
      `/api/intelligence/alerts/${encodeURIComponent(alertId)}/notifications`,
      {
        method: 'POST',
        body: JSON.stringify({ organization_id: organizationId, approved: true }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  getAlertNotifications(alertId: string) {
    return this.requestJson<{ data: OrganizationNotification[]; total: number }>(
      `/api/intelligence/alerts/${encodeURIComponent(alertId)}/notifications`,
    );
  }

  acknowledgeOrganizationNotification(notificationId: string) {
    return this.requestJson<OrganizationNotification>(
      `/api/intelligence/notifications/${encodeURIComponent(notificationId)}/acknowledge`,
      {
        method: 'PATCH',
        body: JSON.stringify({ acknowledged: true }),
        headers: { 'Content-Type': 'application/json' },
      },
    );
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
