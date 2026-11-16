import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { Activity, Camera, Check, ClipboardList, RefreshCw, ShieldCheck, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/lib/authContext';
import {
  oceanWatchApi,
  type CleanupAnalytics,
  type CleanupOperation,
  type CleanupOperationEvidence,
  type CleanupOperationStatus,
  type CleanupRecommendation,
  type EnvironmentalOrganization,
} from '@/lib/api/client';

const transitions: Record<CleanupOperationStatus, CleanupOperationStatus[]> = {
  PLANNED: ['ASSIGNED', 'INSPECTION_SCHEDULED', 'CANCELLED'],
  ASSIGNED: ['PLANNED', 'INSPECTION_SCHEDULED', 'CLEANUP_STARTED', 'CANCELLED'],
  INSPECTION_SCHEDULED: ['ASSIGNED', 'CLEANUP_STARTED', 'CANCELLED'],
  CLEANUP_STARTED: ['CANCELLED'],
  COMPLETED: [],
  CANCELLED: [],
};

const statusLabels: Record<CleanupOperationStatus, string> = {
  PLANNED: 'Planned',
  ASSIGNED: 'Assigned',
  INSPECTION_SCHEDULED: 'Inspection Scheduled',
  CLEANUP_STARTED: 'Cleanup Started',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
};

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleString();
}

function formatQuantity(value: number, unit: string) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value)} ${unit}`;
}

export function CleanupOperationsPage() {
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_admin);
  const [recommendations, setRecommendations] = useState<CleanupRecommendation[]>([]);
  const [operations, setOperations] = useState<CleanupOperation[]>([]);
  const [analytics, setAnalytics] = useState<CleanupAnalytics | null>(null);
  const [organizations, setOrganizations] = useState<EnvironmentalOrganization[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    const [recommendationResult, operationResult, analyticsResult, organizationResult] = await Promise.all([
      oceanWatchApi.getCleanupRecommendations(),
      oceanWatchApi.getCleanupOperations(),
      oceanWatchApi.getCleanupAnalytics(),
      oceanWatchApi.getOrganizations(),
    ]);
    setRecommendations(recommendationResult.data);
    setOperations(operationResult.data);
    setAnalytics(analyticsResult);
    setOrganizations(organizationResult.data);
    setSelectedId((current) => current && operationResult.data.some((item) => item.operation_id === current)
      ? current
      : operationResult.data[0]?.operation_id ?? null);
  }, []);

  useEffect(() => {
    void reload()
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [reload]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    void oceanWatchApi.getCleanupOperation(selectedId)
      .then((detail) => {
        if (active) {
          setOperations((current) => current.map((operation) => (
            operation.operation_id === selectedId ? detail : operation
          )));
        }
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const selected = useMemo(
    () => operations.find((operation) => operation.operation_id === selectedId) ?? null,
    [operations, selectedId],
  );
  const activeCount = operations.filter((operation) => !['COMPLETED', 'CANCELLED'].includes(operation.status)).length;

  async function runAction<T>(action: () => Promise<T>, message: string): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await action();
      await reload();
      if (selectedId) {
        const detail = await oceanWatchApi.getCleanupOperation(selectedId);
        setOperations((current) => current.map((operation) => operation.operation_id === selectedId ? detail : operation));
      }
      setNotice(message);
      return result;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Cleanup workflow request failed.');
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  const createOperation = async (recommendation: CleanupRecommendation) => {
    const operation = await runAction(
      () => oceanWatchApi.createCleanupOperation(recommendation.recommendation_id),
      'Operation created from the current recommendation.',
    );
    if (operation) setSelectedId(operation.operation_id);
  };

  return (
    <div className="min-h-screen bg-ocean-50/60 pb-16">
      <PageHeader
        title="Cleanup Operations"
        description="Turn observed evidence and existing priority scores into assigned, auditable cleanup response work."
      >
        <Button variant="outline" size="sm" onClick={() => void reload().catch((requestError: Error) => setError(requestError.message))} disabled={loading || busy}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading || busy ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </PageHeader>

      <main className="container-page space-y-6 py-6">
        {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

        <Card>
          <CardBody className="grid gap-3 p-4 sm:grid-cols-3">
            <Metric icon={<Activity className="h-4 w-4" />} label="Active operations" value={String(activeCount)} />
            <Metric icon={<Check className="h-4 w-4" />} label="Completed operations" value={String(analytics?.completed_operations ?? '—')} />
            <Metric icon={<Waves className="h-4 w-4" />} label="Action recommendations" value={String(recommendations.length)} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-navy-950">Response recommendations</h2>
                <p className="mt-1 text-sm text-ocean-600">Recommendations keep existing priority scores separate from measured trends, active alerts, freshness, and uncertainty.</p>
              </div>
              <Badge variant="cyan">Evidence-backed</Badge>
            </div>
          </CardHeader>
          <CardBody>
            {loading ? <p className="text-sm text-ocean-600">Loading evidence…</p> : recommendations.length === 0 ? (
              <p className="rounded-lg bg-ocean-50 p-4 text-sm text-ocean-700">No actionable hotspots, measured trends, or active alerts are currently available.</p>
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                {recommendations.map((recommendation) => (
                  <article key={recommendation.recommendation_id} className="rounded-xl border border-ocean-200 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={recommendation.priority === 'CRITICAL' || recommendation.priority === 'HIGH' ? 'error' : recommendation.priority === 'MEDIUM' ? 'warning' : 'teal'}>
                        {recommendation.priority}
                      </Badge>
                      <span className="text-xs font-semibold uppercase tracking-wide text-ocean-600">
                        {recommendation.action_type.replace(/_/g, ' ')}
                      </span>
                      {recommendation.priority_score !== null && (
                        <span className="ml-auto text-xs text-ocean-600">Existing score {recommendation.priority_score}</span>
                      )}
                    </div>
                    <p className="mt-3 text-sm font-semibold text-navy-900">{recommendation.recommended_action}</p>
                    <p className="mt-1 text-xs text-ocean-600">
                      {recommendation.location.latitude.toFixed(4)}, {recommendation.location.longitude.toFixed(4)}
                      {' · '}Freshness: {recommendation.evidence.data_freshness.status}
                      {recommendation.evidence.measured_trend && ` · Measured risk: ${recommendation.evidence.measured_trend.risk_level}`}
                    </p>
                    {recommendation.evidence.measured_trend && (
                      <p className="mt-1 text-xs text-ocean-600">
                        {recommendation.evidence.measured_trend.evidence.recent_observation_count} measured observations from{' '}
                        {recommendation.evidence.measured_trend.evidence.recent_sampling_site_count} sites
                        {' · '}Trend: {recommendation.evidence.measured_trend.trend_direction}
                        {' · '}Evidence quality: {recommendation.evidence.measured_trend.evidence.data_quality}
                      </p>
                    )}
                    {recommendation.evidence.active_alert && (
                      <p className="mt-1 text-xs font-medium text-red-800">
                        Alert {recommendation.evidence.active_alert.alert_id} · {recommendation.evidence.active_alert.risk_level} · {recommendation.evidence.active_alert.status}
                      </p>
                    )}
                    {recommendation.evidence.hotspot && (
                      <p className="mt-1 text-xs text-ocean-600">
                        Existing hotspot evidence included
                        {recommendation.evidence.existing_priority_level
                          ? ` · Priority level: ${recommendation.evidence.existing_priority_level}`
                          : ' · Existing priority context is unavailable'}
                      </p>
                    )}
                    {recommendation.uncertainty.length > 0 && (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-800">
                        {recommendation.uncertainty.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
                      </ul>
                    )}
                    {isAdmin && (
                      <Button className="mt-3" size="sm" disabled={busy} onClick={() => void createOperation(recommendation)}>
                        <ClipboardList className="h-3.5 w-3.5" /> Create operation
                      </Button>
                    )}
                  </article>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-bold text-navy-950">Operations</h2>
            </CardHeader>
            <CardBody className="space-y-2">
              {operations.length === 0 && <p className="text-sm text-ocean-600">No cleanup operations have been created.</p>}
              {operations.map((operation) => (
                <button
                  type="button"
                  key={operation.operation_id}
                  onClick={() => setSelectedId(operation.operation_id)}
                  aria-pressed={selectedId === operation.operation_id}
                  className={`w-full rounded-xl border p-3 text-left transition ${selectedId === operation.operation_id ? 'border-cyan-500 bg-cyan-50' : 'border-ocean-200 bg-white hover:bg-ocean-50'}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-navy-900">{operation.operation_id.slice(0, 10)}</span>
                    <Badge variant={operation.status === 'COMPLETED' ? 'teal' : operation.status === 'CANCELLED' ? 'neutral' : 'cyan'}>
                      {statusLabels[operation.status]}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-ocean-600">
                    {operation.location.latitude.toFixed(4)}, {operation.location.longitude.toFixed(4)}
                    {' · '}{operation.assigned_organization_name ?? 'Unassigned'}
                  </p>
                </button>
              ))}
            </CardBody>
          </Card>

          {selected ? (
            <OperationDetails
              operation={selected}
              organizations={organizations}
              isAdmin={isAdmin}
              busy={busy}
              onAction={runAction}
              onError={setError}
            />
          ) : (
            <Card><CardBody className="p-8 text-sm text-ocean-600">Select an operation to manage assignment, status, evidence, and completion.</CardBody></Card>
          )}
        </div>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-bold text-navy-950">Historical collection records</h2>
          </CardHeader>
          <CardBody>
            <p className="mb-3 text-xs leading-5 text-ocean-600">{analytics?.interpretation ?? 'No historical cleanup totals are available.'}</p>
            {analytics?.monthly_completed_operations.length ? (
              <div className="mb-4 flex flex-wrap gap-2">
                {analytics.monthly_completed_operations.map((item) => (
                  <div key={item.month} className="rounded-lg border border-ocean-200 bg-white px-3 py-2 text-sm">
                    <span className="font-semibold text-navy-900">{item.month}</span>
                    <span className="ml-2 text-ocean-600">{item.completed_operations} completed</span>
                  </div>
                ))}
              </div>
            ) : null}
            {analytics?.quantities_by_unit_and_classification.length ? (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {analytics.quantities_by_unit_and_classification.map((item) => (
                  <div key={`${item.measurement_unit}-${item.classification}`} className="rounded-lg border border-ocean-200 bg-white p-3">
                    <p className="text-lg font-bold text-navy-950">{formatQuantity(item.total, item.measurement_unit)}</p>
                    <p className="text-xs text-ocean-600">{item.classification.toLowerCase().replace(/_/g, ' ')} quantity</p>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-ocean-600">No measured collection quantities have been recorded.</p>}
          </CardBody>
        </Card>
      </main>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-ocean-50 p-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-100 text-cyan-800">{icon}</span>
      <div><p className="text-xs text-ocean-600">{label}</p><p className="text-xl font-bold text-navy-950">{value}</p></div>
    </div>
  );
}

function OperationDetails({
  operation,
  organizations,
  isAdmin,
  busy,
  onAction,
  onError,
}: {
  operation: CleanupOperation;
  organizations: EnvironmentalOrganization[];
  isAdmin: boolean;
  busy: boolean;
  onAction: (action: () => Promise<unknown>, message: string) => Promise<unknown>;
  onError: (message: string | null) => void;
}) {
  const [organizationId, setOrganizationId] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [transitionReason, setTransitionReason] = useState('');
  const [evidenceType, setEvidenceType] = useState<CleanupOperationEvidence['evidence_type']>('INSPECTION_NOTE');
  const [evidenceNotes, setEvidenceNotes] = useState('');
  const [evidenceFile, setEvidenceFile] = useState<File | undefined>();
  const [completedAt, setCompletedAt] = useState(new Date().toISOString().slice(0, 16));
  const [wasteQuantity, setWasteQuantity] = useState('');
  const [measurementUnit, setMeasurementUnit] = useState('kg');
  const [quantityClass, setQuantityClass] = useState<'ESTIMATED' | 'REPORTED' | 'INDEPENDENTLY_VERIFIED'>('REPORTED');
  const [verificationEvidenceId, setVerificationEvidenceId] = useState('');
  const [verifierName, setVerifierName] = useState('');
  const [verifierOrganization, setVerifierOrganization] = useState('');
  const [reviewReason, setReviewReason] = useState('');
  const [notifications, setNotifications] = useState<Awaited<ReturnType<typeof oceanWatchApi.getCleanupAssignmentNotifications>>['data']>([]);
  const [notificationPolicy, setNotificationPolicy] = useState<{
    test_mode: boolean;
    delivery_recipient_email: string | null;
  } | null>(null);

  useEffect(() => {
    setNotifications([]);
    setNotificationPolicy(null);
    if (isAdmin && operation.assigned_organization_id) {
      void oceanWatchApi.getCleanupAssignmentNotifications(operation.operation_id)
        .then((response) => {
          setNotifications(response.data);
          setNotificationPolicy({
            test_mode: response.test_mode,
            delivery_recipient_email: response.delivery_recipient_email,
          });
        })
        .catch((requestError: Error) => onError(requestError.message));
    } else {
      setNotificationPolicy(null);
    }
  }, [isAdmin, onError, operation.assigned_organization_id, operation.operation_id]);

  const transitionsAvailable = transitions[operation.status];
  const activeStatus = !['COMPLETED', 'CANCELLED'].includes(operation.status);
  const wrap = (action: () => Promise<unknown>, message: string) => onAction(action, message);

  async function transition(status: CleanupOperationStatus) {
    await wrap(
      () => oceanWatchApi.updateCleanupOperationStatus(
        operation.operation_id,
        status,
        transitionReason.trim() || `Status changed to ${statusLabels[status]}.`,
      ),
      `Operation status updated to ${statusLabels[status]}.`,
    );
    setTransitionReason('');
  }

  async function assign() {
    if (!organizationId) {
      onError('Select a verified organization before assigning this operation.');
      return;
    }
    await wrap(
      () => oceanWatchApi.assignCleanupOperation(operation.operation_id, {
        organization_id: organizationId,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
      }),
      'Organization and coordinator assigned.',
    );
  }

  async function submitEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await wrap(
      () => oceanWatchApi.submitCleanupEvidence(
        operation.operation_id,
        evidenceType,
        evidenceNotes || undefined,
        evidenceFile,
      ),
      'Evidence submitted for review.',
    );
    setEvidenceNotes('');
    setEvidenceFile(undefined);
  }

  async function complete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const quantity = wasteQuantity === '' ? undefined : Number(wasteQuantity);
    await wrap(
      () => oceanWatchApi.completeCleanupOperation(operation.operation_id, {
        completed_at: new Date(completedAt).toISOString(),
        ...(quantity === undefined ? {} : {
          waste_quantity: quantity,
          measurement_unit: measurementUnit,
          quantity_classification: quantityClass,
          ...(quantityClass === 'INDEPENDENTLY_VERIFIED' ? {
            verification_evidence_id: verificationEvidenceId,
            verifier_name: verifierName,
            verifier_organization: verifierOrganization,
          } : {}),
        }),
      }),
      'Completion and reported collection details recorded. This does not establish a pollution decrease.',
    );
  }

  async function approveAndSend() {
    await wrap(
      () => oceanWatchApi.sendCleanupAssignmentNotification(operation.operation_id),
      notificationPolicy?.test_mode
        ? `Approved test email sent to ${notificationPolicy.delivery_recipient_email}.`
        : 'Approved assignment email sent.',
    );
    const result = await oceanWatchApi.getCleanupAssignmentNotifications(operation.operation_id);
    setNotifications(result.data);
    setNotificationPolicy({
      test_mode: result.test_mode,
      delivery_recipient_email: result.delivery_recipient_email,
    });
  }

  async function acknowledge(notificationId: string) {
    await wrap(
      () => oceanWatchApi.acknowledgeCleanupAssignment(notificationId),
      'Assignment acknowledgment recorded.',
    );
    const result = await oceanWatchApi.getCleanupAssignmentNotifications(operation.operation_id);
    setNotifications(result.data);
    setNotificationPolicy({
      test_mode: result.test_mode,
      delivery_recipient_email: result.delivery_recipient_email,
    });
  }

  async function download(evidence: CleanupOperationEvidence) {
    if (!evidence.media_id) return;
    try {
      const blob = await oceanWatchApi.downloadCleanupEvidence(evidence.evidence_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `cleanup-evidence-${evidence.evidence_id}`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestError) {
      onError((requestError as Error).message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-navy-950">Operation details</h2>
            <p className="mt-1 font-mono text-xs text-ocean-600">{operation.operation_id}</p>
          </div>
          <Badge variant="cyan">{statusLabels[operation.status]}</Badge>
        </div>
      </CardHeader>
      <CardBody className="space-y-5">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <Detail label="Location" value={`${operation.location.latitude.toFixed(5)}, ${operation.location.longitude.toFixed(5)}`} />
          <Detail label="Recommendation" value={operation.recommendation_snapshot.action_type.replace(/_/g, ' ')} />
          <Detail label="Assigned organization" value={operation.assigned_organization_name ?? 'Not assigned'} />
          <Detail label="Coordinator" value={operation.responsible_coordinator_name ?? operation.responsible_coordinator_user_id ?? 'Not assigned'} />
          <Detail label="Scheduled" value={formatDate(operation.scheduled_at)} />
          <Detail label="Created" value={formatDate(operation.created_at)} />
          {operation.alert_id && <Detail label="Linked alert" value={operation.alert_id} />}
        </dl>

        {isAdmin && activeStatus && (
          <section className="rounded-xl border border-ocean-200 bg-ocean-50 p-4">
            <h3 className="font-semibold text-navy-900">Assign organization and schedule</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-medium text-navy-800">
                Verified organization
                <select aria-label="Verified organization" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
                  <option value="">Select an organization</option>
                  {organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}
                </select>
              </label>
              <label className="text-xs font-medium text-navy-800">
                Scheduled date (optional)
                <input aria-label="Scheduled date" type="datetime-local" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" disabled={busy} onClick={() => void assign()}>Assign &amp; schedule</Button>
              {operation.assigned_organization_id && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || notificationPolicy === null || (notificationPolicy.test_mode && !notificationPolicy.delivery_recipient_email)}
                  onClick={() => void approveAndSend()}
                >
                  <ShieldCheck className="h-3.5 w-3.5" /> Approve &amp; send
                  {notificationPolicy?.test_mode ? ' test email' : ' assignment email'}
                </Button>
              )}
              <Link className="self-center text-xs font-medium text-cyan-800 underline" to="/intelligence">Manage verified organizations</Link>
            </div>
            {operation.assigned_organization_id && notificationPolicy?.test_mode && (
              <p className="mt-2 text-xs text-amber-900">
                {notificationPolicy.delivery_recipient_email
                  ? `SMTP test mode: approval sends only to ${notificationPolicy.delivery_recipient_email}, not to the assigned organization.`
                  : 'SMTP test mode is enabled, but no test recipient is configured; sending is unavailable.'}
              </p>
            )}
            {notifications.map((notification) => (
              <div key={notification.notification_id} className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span>
                  {notification.test_mode ? 'TEST ONLY · ' : ''}
                  {notification.recipient_email}
                  {notification.intended_recipient_email
                    ? ` (intended: ${notification.intended_recipient_email})`
                    : ''}
                  {' · '}{notification.delivery_status}
                </span>
                {notification.delivery_status === 'SENT' && (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => void acknowledge(notification.notification_id)}>
                    Record acknowledgment
                  </Button>
                )}
              </div>
            ))}
          </section>
        )}

        {isAdmin && activeStatus && (
          <section className="rounded-xl border border-ocean-200 p-4">
            <h3 className="font-semibold text-navy-900">Update operation status</h3>
            <label className="mt-2 block text-xs font-medium text-navy-800">
              Audit reason
              <input aria-label="Status reason" className="mt-1 w-full rounded-lg border border-ocean-300 p-2 text-sm" value={transitionReason} maxLength={500} onChange={(event) => setTransitionReason(event.target.value)} />
            </label>
            <div className="mt-3 flex flex-wrap gap-2">
              {transitionsAvailable.map((status) => (
                <Button key={status} size="sm" variant={status === 'CANCELLED' ? 'outline' : 'secondary'} disabled={busy} onClick={() => void transition(status)}>
                  {statusLabels[status]}
                </Button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-ocean-500">Completion is recorded separately with evidence and optional waste quantity classification.</p>
          </section>
        )}

        {isAdmin && activeStatus && (
          <section className="rounded-xl border border-ocean-200 p-4">
            <h3 className="font-semibold text-navy-900">Inspection and cleanup evidence</h3>
            <form className="mt-3 space-y-3" onSubmit={(event) => void submitEvidence(event)}>
              <label className="block text-xs font-medium text-navy-800">
                Evidence type
                <select aria-label="Evidence type" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={evidenceType} onChange={(event) => setEvidenceType(event.target.value as CleanupOperationEvidence['evidence_type'])}>
                  <option value="BEFORE_PHOTO">Before-cleanup photograph</option>
                  <option value="AFTER_PHOTO">After-cleanup photograph</option>
                  <option value="INSPECTION_NOTE">Inspection note</option>
                  <option value="SUPPORTING_EVIDENCE">Supporting evidence image</option>
                </select>
              </label>
              <label className="block text-xs font-medium text-navy-800">
                Notes
                <textarea aria-label="Evidence notes" className="mt-1 min-h-20 w-full rounded-lg border border-ocean-300 p-2 text-sm" maxLength={4000} value={evidenceNotes} onChange={(event) => setEvidenceNotes(event.target.value)} />
              </label>
              {evidenceType !== 'INSPECTION_NOTE' && (
                <label className="block text-xs font-medium text-navy-800">
                  <span className="flex items-center gap-2"><Camera className="h-4 w-4" /> JPEG or PNG image (max 5 MB)</span>
                  <input aria-label="Evidence image" className="mt-1 block w-full text-sm" type="file" accept="image/jpeg,image/png" onChange={(event) => setEvidenceFile(event.target.files?.[0])} />
                </label>
              )}
              <Button size="sm" disabled={busy} type="submit">Submit evidence</Button>
            </form>
          </section>
        )}

        {operation.status === 'CLEANUP_STARTED' && isAdmin && (
          <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h3 className="font-semibold text-navy-900">Record cleanup completion</h3>
            <form className="mt-3 space-y-3" onSubmit={(event) => void complete(event)}>
              <label className="block text-xs font-medium text-navy-800">
                Completion date
                <input aria-label="Completion date" type="datetime-local" required className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={completedAt} onChange={(event) => setCompletedAt(event.target.value)} />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium text-navy-800">
                  Waste quantity (optional)
                  <input aria-label="Waste quantity" type="number" min="0" step="any" className="mt-1 w-full rounded-lg border border-ocean-300 p-2 text-sm" value={wasteQuantity} onChange={(event) => setWasteQuantity(event.target.value)} />
                </label>
                <label className="text-xs font-medium text-navy-800">
                  Measurement unit
                  <select aria-label="Measurement unit" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={measurementUnit} onChange={(event) => setMeasurementUnit(event.target.value)}>
                    {['kg', 'tonnes', 'lb', 'bags', 'items', 'other'].map((unit) => <option key={unit}>{unit}</option>)}
                  </select>
                </label>
              </div>
              {wasteQuantity !== '' && (
                <>
                  <label className="block text-xs font-medium text-navy-800">
                    Quantity classification
                    <select aria-label="Quantity classification" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2 text-sm" value={quantityClass} onChange={(event) => setQuantityClass(event.target.value as typeof quantityClass)}>
                      <option value="ESTIMATED">Estimated</option>
                      <option value="REPORTED">Reported</option>
                      <option value="INDEPENDENTLY_VERIFIED">Independently verified</option>
                    </select>
                  </label>
                  {quantityClass === 'INDEPENDENTLY_VERIFIED' && (
                    <div className="grid gap-3 sm:grid-cols-3">
                      <label className="text-xs font-medium text-navy-800">Evidence ID<input aria-label="Verification evidence ID" className="mt-1 w-full rounded-lg border border-ocean-300 p-2 text-sm" value={verificationEvidenceId} onChange={(event) => setVerificationEvidenceId(event.target.value)} /></label>
                      <label className="text-xs font-medium text-navy-800">Verifier name<input aria-label="Verifier name" className="mt-1 w-full rounded-lg border border-ocean-300 p-2 text-sm" value={verifierName} onChange={(event) => setVerifierName(event.target.value)} /></label>
                      <label className="text-xs font-medium text-navy-800">Verifier organization<input aria-label="Verifier organization" className="mt-1 w-full rounded-lg border border-ocean-300 p-2 text-sm" value={verifierOrganization} onChange={(event) => setVerifierOrganization(event.target.value)} /></label>
                    </div>
                  )}
                </>
              )}
              <p className="text-xs text-emerald-900">A completed operation and a collected-waste quantity do not prove that pollution concentrations decreased.</p>
              <Button size="sm" disabled={busy} type="submit">Record completion</Button>
            </form>
          </section>
        )}

        <section>
          <h3 className="mb-2 font-semibold text-navy-900">Evidence and review history</h3>
          {operation.evidence?.length ? (
            <div className="space-y-2">
              {operation.evidence.map((evidence) => (
                <EvidenceRow
                  key={evidence.evidence_id}
                  evidence={evidence}
                  isAdmin={isAdmin}
                  busy={busy}
                  reviewReason={reviewReason}
                  onReasonChange={setReviewReason}
                  onVerify={(status) => void wrap(
                    () => oceanWatchApi.verifyCleanupEvidence(operation.operation_id, evidence.evidence_id, status, reviewReason || 'Evidence reviewed by an administrator.'),
                    `Evidence ${status.toLowerCase()}.`,
                  )}
                  onDownload={() => void download(evidence)}
                />
              ))}
            </div>
          ) : <p className="text-sm text-ocean-600">No inspection or cleanup evidence submitted.</p>}
        </section>

        <section>
          <h3 className="mb-2 font-semibold text-navy-900">Auditable status history</h3>
          <ol className="space-y-2 border-l-2 border-cyan-200 pl-4">
            {operation.status_history.map((item, index) => (
              <li key={`${item.changed_at}-${index}`} className="text-xs">
                <span className="font-semibold text-navy-900">{statusLabels[item.status]}</span>
                <span className="ml-2 text-ocean-600">{formatDate(item.changed_at)} · {item.changed_by}</span>
                <p className="mt-0.5 text-ocean-700">{item.reason}</p>
              </li>
            ))}
          </ol>
        </section>
      </CardBody>
    </Card>
  );
}

function EvidenceRow({
  evidence,
  isAdmin,
  busy,
  reviewReason,
  onReasonChange,
  onVerify,
  onDownload,
}: {
  evidence: CleanupOperationEvidence;
  isAdmin: boolean;
  busy: boolean;
  reviewReason: string;
  onReasonChange: (value: string) => void;
  onVerify: (status: 'VERIFIED' | 'REJECTED') => void;
  onDownload: () => void;
}) {
  return (
    <div className="rounded-lg border border-ocean-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={evidence.verification_status === 'VERIFIED' ? 'teal' : evidence.verification_status === 'REJECTED' ? 'error' : 'neutral'}>
          {evidence.verification_status}
        </Badge>
        <span className="text-xs font-semibold text-navy-900">{evidence.evidence_type.replace(/_/g, ' ')}</span>
        <span className="text-xs text-ocean-500">{formatDate(evidence.created_at)} · {evidence.submitted_by}</span>
        <span className="font-mono text-[10px] text-ocean-400">{evidence.evidence_id}</span>
        {evidence.media_id && <Button size="sm" variant="outline" onClick={onDownload}>Download image</Button>}
      </div>
      {evidence.notes && <p className="mt-2 whitespace-pre-wrap text-sm text-ocean-700">{evidence.notes}</p>}
      {isAdmin && evidence.verification_status === 'PENDING' && (
        <div className="mt-3 flex flex-wrap gap-2">
          <input aria-label={`Review reason ${evidence.evidence_id}`} className="min-w-48 flex-1 rounded-lg border border-ocean-300 p-2 text-xs" placeholder="Review reason" value={reviewReason} maxLength={500} onChange={(event) => onReasonChange(event.target.value)} />
          <Button size="sm" disabled={busy} onClick={() => onVerify('VERIFIED')}>Verify evidence</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => onVerify('REJECTED')}>Reject evidence</Button>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs text-ocean-500">{label}</dt><dd className="mt-0.5 break-words font-medium text-navy-900">{value}</dd></div>;
}
