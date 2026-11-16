import { useCallback, useEffect, useState } from 'react';
import { BellRing, Check, ChevronDown, Mail, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/lib/authContext';
import {
  oceanWatchApi,
  type AlertStatus,
  type EnvironmentalOrganization,
  type NotificationSuggestion,
  type OrganizationNotification,
  type PollutionAlert,
} from '@/lib/api/client';

const transitions: Record<AlertStatus, AlertStatus[]> = {
  ACTIVE: ['ACKNOWLEDGED', 'UNDER_INVESTIGATION', 'RESOLVED', 'CLOSED'],
  ACKNOWLEDGED: ['UNDER_INVESTIGATION', 'RESOLVED', 'CLOSED'],
  UNDER_INVESTIGATION: ['ACKNOWLEDGED', 'RESOLVED', 'CLOSED'],
  RESOLVED: ['CLOSED'],
  CLOSED: [],
};

const riskVariant = {
  LOW: 'cyan',
  MEDIUM: 'teal',
  HIGH: 'warning',
  CRITICAL: 'error',
} as const;

const statusLabels: Record<AlertStatus, string> = {
  ACTIVE: 'Active',
  ACKNOWLEDGED: 'Acknowledged',
  UNDER_INVESTIGATION: 'Under Investigation',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

export function AlertManagementPanel({
  alerts,
  onRefresh,
}: {
  alerts: PollutionAlert[];
  onRefresh: () => void;
}) {
  const { user } = useAuth();
  const [busyAlert, setBusyAlert] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, NotificationSuggestion[]>>({});
  const [notifications, setNotifications] = useState<Record<string, OrganizationNotification[]>>({});

  const updateStatus = async (alert: PollutionAlert, status: AlertStatus) => {
    setError(null);
    setBusyAlert(alert.alert_id);
    try {
      await oceanWatchApi.updatePollutionAlert(alert.alert_id, status);
      onRefresh();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusyAlert(null);
    }
  };

  const reviewOrganizations = async (alertId: string) => {
    setError(null);
    setBusyAlert(alertId);
    try {
      const [matchResult, notificationResult] = await Promise.all([
        oceanWatchApi.previewOrganizationNotifications(alertId),
        oceanWatchApi.getAlertNotifications(alertId),
      ]);
      setMatches((current) => ({ ...current, [alertId]: matchResult.data }));
      setNotifications((current) => ({ ...current, [alertId]: notificationResult.data }));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusyAlert(null);
    }
  };

  const approveAndSend = async (alertId: string, organizationId: string) => {
    setError(null);
    setBusyAlert(alertId);
    try {
      await oceanWatchApi.sendOrganizationNotification(alertId, organizationId);
      await reviewOrganizations(alertId);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusyAlert(null);
    }
  };

  const acknowledge = async (notificationId: string, alertId: string) => {
    setError(null);
    try {
      await oceanWatchApi.acknowledgeOrganizationNotification(notificationId);
      await reviewOrganizations(alertId);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  return (
    <Card className="overflow-hidden border border-ocean-200 shadow-md">
      <CardHeader className="border-b border-ocean-100 bg-white px-6 py-5">
        <div className="flex items-center gap-2">
          <BellRing className="h-5 w-5 text-orange-600" />
          <h2 className="text-lg font-bold text-navy-950">Alert management</h2>
          <Badge variant="navy">{alerts.filter((alert) => ['ACTIVE', 'ACKNOWLEDGED', 'UNDER_INVESTIGATION'].includes(alert.status)).length} open</Badge>
        </div>
        <p className="mt-1 text-xs text-ocean-600">
          Warnings are created from measured high-risk cells. A missing baseline does not close an alert; only a comparable measured decrease can resolve it.
        </p>
      </CardHeader>
      <CardBody className="space-y-4">
        {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
        {!alerts.length && <p className="text-sm text-ocean-600">No alerts have been generated from the available measured assessments.</p>}
        {alerts.map((alert) => (
          <article key={alert.alert_id} className="rounded-xl border border-ocean-100 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={riskVariant[alert.risk_level]}>{alert.risk_level}</Badge>
                  <Badge variant={alert.status === 'ACTIVE' ? 'warning' : 'neutral'}>{statusLabels[alert.status]}</Badge>
                  <span className="font-mono text-xs text-ocean-600">
                    {alert.location.latitude.toFixed(2)}, {alert.location.longitude.toFixed(2)}°
                  </span>
                </div>
                <p className="mt-2 text-sm font-semibold text-navy-950">
                  {alert.triggering_evidence.comparison.recent_mean_pieces_m3.toFixed(3)} pieces/m³ · {alert.source}
                </p>
                <p className="mt-1 text-xs text-ocean-600">
                  {alert.triggering_evidence.evidence.recent_observation_count} recent observations
                  {alert.triggering_evidence.evidence.baseline_available
                    ? ` · prior mean ${alert.triggering_evidence.comparison.previous_mean_pieces_m3?.toFixed(3)} pieces/m³`
                    : ' · no comparable baseline'}
                  {alert.triggering_evidence.change_types.length
                    ? ` · ${alert.triggering_evidence.change_types.join(', ').replace(/_/g, ' ')}`
                    : ''}
                </p>
                <p className="mt-1 text-[11px] text-ocean-500">
                  Created {new Date(alert.created_at).toLocaleString()} · updated {new Date(alert.last_updated_at).toLocaleString()}
                  {alert.responsible_user_id ? ` · assigned to ${alert.responsible_user_id}` : ''}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {transitions[alert.status].length > 0 && (
                  <label className="relative">
                    <span className="sr-only">Update alert status</span>
                    <select
                      aria-label={`Update status for alert ${alert.alert_id}`}
                      value=""
                      disabled={busyAlert === alert.alert_id}
                      onChange={(event) => {
                        if (event.target.value) void updateStatus(alert, event.target.value as AlertStatus);
                      }}
                      className="appearance-none rounded-lg border border-ocean-200 bg-white py-2 pl-3 pr-8 text-xs text-navy-900"
                    >
                      <option value="">Update status</option>
                      {transitions[alert.status].map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2 top-2.5 h-3.5 w-3.5 text-ocean-500" />
                  </label>
                )}
                <Button variant="outline" size="sm" onClick={() => void reviewOrganizations(alert.alert_id)} disabled={busyAlert === alert.alert_id}>
                  <Mail className="h-3.5 w-3.5" />
                  Review organizations
                </Button>
              </div>
            </div>
            <details className="mt-3 border-t border-ocean-100 pt-3">
              <summary className="cursor-pointer text-xs font-semibold text-ocean-700">Status history ({alert.status_history.length})</summary>
              <ol className="mt-2 space-y-1">
                {alert.status_history.map((item, index) => (
                  <li key={`${item.changed_at}-${index}`} className="text-[11px] text-ocean-600">
                    {new Date(item.changed_at).toLocaleString()} · {statusLabels[item.status]} · {item.reason}
                  </li>
                ))}
              </ol>
            </details>
            {matches[alert.alert_id] && (
              <div className="mt-3 space-y-3 border-t border-ocean-100 pt-3">
                <h3 className="text-sm font-semibold text-navy-950">Verified organizations serving this affected area</h3>
                {!matches[alert.alert_id].length && <p className="text-xs text-ocean-600">No verified, notification-enabled organizations currently intersect this alert area.</p>}
                {matches[alert.alert_id].map((organization) => (
                  <NotificationPreview
                    key={organization.organization_id}
                    organization={organization}
                    isAdmin={Boolean(user?.is_admin)}
                    busy={busyAlert === alert.alert_id}
                    onApprove={() => void approveAndSend(alert.alert_id, organization.organization_id)}
                  />
                ))}
                {(notifications[alert.alert_id] ?? []).map((notification) => (
                  <div key={notification.notification_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-ocean-50 px-3 py-2 text-xs">
                    <span>
                      {notification.test_mode ? 'TEST ONLY · ' : ''}
                      {notification.recipient_email}
                      {notification.intended_recipient_email
                        ? ` (intended: ${notification.intended_recipient_email})`
                        : ''}
                      {' · '}{notification.delivery_status}
                    </span>
                    {user?.is_admin && notification.delivery_status === 'SENT' && (
                      <Button variant="outline" size="sm" onClick={() => void acknowledge(notification.notification_id, alert.alert_id)}>
                        <Check className="h-3.5 w-3.5" /> Record acknowledgment
                      </Button>
                    )}
                    {notification.acknowledged_at && <span>Acknowledged {new Date(notification.acknowledged_at).toLocaleString()}</span>}
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
      </CardBody>
    </Card>
  );
}

function NotificationPreview({
  organization,
  isAdmin,
  busy,
  onApprove,
}: {
  organization: NotificationSuggestion;
  isAdmin: boolean;
  busy: boolean;
  onApprove: () => void;
}) {
  return (
    <details className="rounded-lg border border-ocean-100 bg-ocean-50/60 p-3">
      <summary className="cursor-pointer text-xs font-semibold text-navy-900">
        <ShieldCheck className="mr-1 inline h-3.5 w-3.5 text-emerald-700" />
        {organization.name} · {organization.contact_email}
      </summary>
      <div className="mt-3 rounded-lg bg-white p-3 text-xs">
        <p className="font-semibold">{organization.subject}</p>
        <pre className="mt-2 whitespace-pre-wrap font-sans leading-relaxed text-ocean-700">{organization.body}</pre>
        <p className="mt-2 rounded-md bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900">
          {organization.test_mode
            ? organization.delivery_recipient_email
              ? `SMTP test mode: approval sends only to ${organization.delivery_recipient_email}, not ${organization.contact_email}.`
              : 'SMTP test mode is enabled, but no test recipient is configured; sending is unavailable.'
            : `Approval sends to the organization address: ${organization.delivery_recipient_email ?? organization.contact_email}.`}
        </p>
        {isAdmin && (
          <Button
            variant="primary"
            size="sm"
            className="mt-3"
            disabled={busy || (organization.test_mode && !organization.delivery_recipient_email)}
            onClick={onApprove}
          >
            {organization.test_mode ? 'Approve & send test email' : 'Approve & send email'}
          </Button>
        )}
        {!isAdmin && <p className="mt-3 text-[11px] text-ocean-500">An administrator must approve external email delivery.</p>}
      </div>
    </details>
  );
}

export function OrganizationDirectoryPanel() {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState<EnvironmentalOrganization[]>([]);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [area, setArea] = useState('');
  const [areasServed, setAreasServed] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const result = await oceanWatchApi.getOrganizations(Boolean(user?.is_admin));
    setOrganizations(result.data);
  }, [user?.is_admin]);

  useEffect(() => {
    if (user?.is_admin) void reload().catch((requestError: Error) => setError(requestError.message));
  }, [reload, user?.is_admin]);

  if (!user?.is_admin) return null;

  const register = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    let serviceArea: Record<string, unknown>;
    try {
      serviceArea = JSON.parse(area) as Record<string, unknown>;
    } catch {
      setError('Service area must be valid GeoJSON Polygon JSON.');
      return;
    }
    setLoading(true);
    try {
      await oceanWatchApi.createOrganization({
        name,
        contact_email: email,
        service_area: serviceArea,
        areas_served: areasServed.split(',').map((item) => item.trim()).filter(Boolean),
        email_notifications_enabled: true,
        acknowledgment_required: true,
      });
      setName('');
      setEmail('');
      setArea('');
      setAreasServed('');
      setMessage('Organization registered as unverified. Verify its details and service area before notification matching.');
      await reload();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const setVerification = async (organization: EnvironmentalOrganization, verified: boolean) => {
    setError(null);
    try {
      await oceanWatchApi.verifyOrganization(organization.organization_id, verified);
      await reload();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  return (
    <Card className="border border-ocean-200">
      <CardHeader>
        <h2 className="text-lg font-bold text-navy-950">Environmental organization directory</h2>
        <p className="mt-1 text-xs text-ocean-600">No organizations are preloaded. Admins must register and verify real contact details and service-area geometry.</p>
      </CardHeader>
      <CardBody className="space-y-4">
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="text-sm text-emerald-800">{message}</p>}
        <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => void register(event)}>
          <label className="text-xs font-medium text-ocean-700">Organization name
            <input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-lg border border-ocean-200 px-3 py-2 text-sm" />
          </label>
          <label className="text-xs font-medium text-ocean-700">Contact email
            <input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-lg border border-ocean-200 px-3 py-2 text-sm" />
          </label>
          <label className="text-xs font-medium text-ocean-700 md:col-span-2">GeoJSON Polygon service area
            <textarea required value={area} onChange={(event) => setArea(event.target.value)} rows={3} placeholder='{"type":"Polygon","coordinates":[[[longitude,latitude],...]]}' className="mt-1 w-full rounded-lg border border-ocean-200 px-3 py-2 font-mono text-xs" />
          </label>
          <label className="text-xs font-medium text-ocean-700">Areas served (comma-separated)
            <input value={areasServed} onChange={(event) => setAreasServed(event.target.value)} className="mt-1 w-full rounded-lg border border-ocean-200 px-3 py-2 text-sm" />
          </label>
          <div className="flex items-end">
            <Button type="submit" size="sm" disabled={loading}>{loading ? 'Registering…' : 'Register organization'}</Button>
          </div>
        </form>
        <div className="divide-y divide-ocean-100 border-t border-ocean-100">
          {organizations.map((organization) => (
            <div key={organization.organization_id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-xs">
              <span><strong>{organization.name}</strong> · {organization.contact_email} · {organization.verified ? 'Verified' : 'Unverified'}</span>
              <Button variant="outline" size="sm" onClick={() => void setVerification(organization, !organization.verified)}>
                {organization.verified ? 'Revoke verification' : 'Verify organization'}
              </Button>
            </div>
          ))}
          {!organizations.length && <p className="py-3 text-xs text-ocean-500">No organizations registered.</p>}
        </div>
      </CardBody>
    </Card>
  );
}
