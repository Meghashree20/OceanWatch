import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Camera, Flag, RefreshCw, ShieldCheck } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/lib/authContext';
import {
  oceanWatchApi,
  type CitizenPollutionReport,
  type CitizenReportStatus,
} from '@/lib/api/client';

const categoryLabels: Record<CitizenPollutionReport['category'], string> = {
  PLASTIC_DEBRIS: 'Plastic debris',
  FISHING_GEAR: 'Fishing gear',
  OIL_OR_CHEMICAL: 'Oil or chemical',
  WILDLIFE_IMPACT: 'Wildlife impact',
  OTHER: 'Other',
};

function localDateTime() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString();
}

export function CitizenReportsPage() {
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_admin);
  const [reports, setReports] = useState<CitizenPollutionReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [category, setCategory] = useState<CitizenPollutionReport['category']>('PLASTIC_DEBRIS');
  const [description, setDescription] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [observedAt, setObservedAt] = useState(localDateTime);
  const [photo, setPhoto] = useState<File | null>(null);
  const [reviewReason, setReviewReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    const response = await oceanWatchApi.getCitizenReports();
    setReports(response.data);
  }, []);

  useEffect(() => {
    void reload()
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [reload]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!photo) {
      setError('Add a JPEG or PNG photograph to submit a report.');
      return;
    }
    if (photo.size > 5 * 1024 * 1024) {
      setError('Photographs must be 5 MB or smaller.');
      return;
    }
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      setError('Enter valid coordinates within latitude -90 to 90 and longitude -180 to 180.');
      return;
    }
    setBusyId('submit');
    setError(null);
    setNotice(null);
    try {
      await oceanWatchApi.submitCitizenReport({
        category,
        description: description.trim(),
        latitude: lat,
        longitude: lon,
        observed_at: new Date(observedAt).toISOString(),
        file: photo,
      });
      setDescription('');
      setPhoto(null);
      setNotice('Report submitted for moderation. It is not a verified pollution observation.');
      await reload();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to submit citizen report.');
    } finally {
      setBusyId(null);
    }
  }

  async function moderate(report: CitizenPollutionReport, status: 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED') {
    setBusyId(report.report_id);
    setError(null);
    setNotice(null);
    try {
      await oceanWatchApi.moderateCitizenReport(
        report.report_id,
        status,
        reviewReason.trim() || `Report marked ${status.toLowerCase().replace(/_/g, ' ')} by an administrator.`,
      );
      setNotice(`Report marked ${status.toLowerCase().replace(/_/g, ' ')}.`);
      await reload();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to moderate citizen report.');
    } finally {
      setBusyId(null);
    }
  }

  async function download(report: CitizenPollutionReport) {
    try {
      const blob = await oceanWatchApi.downloadCitizenReportPhoto(report.report_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `citizen-report-${report.report_id}`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to download report photograph.');
    }
  }

  return (
    <div className="min-h-screen bg-ocean-50/60 pb-16">
      <PageHeader
        title="Citizen Pollution Reports"
        description="Submit and review community reports as evidence pending moderation, separate from measured observations and model training data."
      >
        <Button variant="outline" size="sm" onClick={() => void reload().catch((requestError: Error) => setError(requestError.message))} disabled={loading || busyId !== null}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </PageHeader>
      <main className="container-page space-y-6 py-6">
        <div role="status" aria-live="polite" className="space-y-2">
          {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
          {notice && <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
        </div>
        <Card>
          <CardHeader>
            <h2 className="flex items-center gap-2 text-lg font-bold text-navy-950"><Flag className="h-5 w-5" /> Submit a report</h2>
            <p className="mt-1 text-sm text-ocean-600">Reports require a photograph, location, observation time, category, and description. All reports start pending review.</p>
          </CardHeader>
          <CardBody>
            <form className="grid gap-4 md:grid-cols-2" onSubmit={(event) => void submit(event)}>
              <label className="text-sm font-medium text-navy-800">
                Category
                <select aria-label="Report category" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2" value={category} onChange={(event) => setCategory(event.target.value as CitizenPollutionReport['category'])}>
                  {Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-navy-800">
                Observation time
                <input aria-label="Observation time" required type="datetime-local" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2" value={observedAt} onChange={(event) => setObservedAt(event.target.value)} />
              </label>
              <label className="text-sm font-medium text-navy-800">
                Latitude
                <input aria-label="Latitude" required type="number" min="-90" max="90" step="any" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2" value={latitude} onChange={(event) => setLatitude(event.target.value)} />
              </label>
              <label className="text-sm font-medium text-navy-800">
                Longitude
                <input aria-label="Longitude" required type="number" min="-180" max="180" step="any" className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2" value={longitude} onChange={(event) => setLongitude(event.target.value)} />
              </label>
              <label className="text-sm font-medium text-navy-800 md:col-span-2">
                Description
                <textarea aria-label="Report description" required minLength={10} maxLength={4000} className="mt-1 min-h-24 w-full rounded-lg border border-ocean-300 bg-white p-2" value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
              <label className="text-sm font-medium text-navy-800 md:col-span-2">
                <span className="flex items-center gap-2"><Camera className="h-4 w-4" /> Photograph (JPEG or PNG, max 5 MB)</span>
                <input aria-label="Report photograph" required type="file" accept="image/jpeg,image/png" className="mt-1 block w-full text-sm" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} />
              </label>
              <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 md:col-span-2">
                Citizen reports are not verified pollution measurements and are never automatically added to the observation dataset or model training labels.
              </div>
              <Button className="md:col-span-2 md:justify-self-start" type="submit" disabled={busyId !== null}>Submit for moderation</Button>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-bold text-navy-950">{isAdmin ? 'Reports for moderation' : 'Your reports'}</h2>
          </CardHeader>
          <CardBody className="space-y-3">
            {loading ? <p className="text-sm text-ocean-600">Loading reports…</p> : reports.length === 0 ? (
              <p className="text-sm text-ocean-600">No citizen reports are available.</p>
            ) : reports.map((report) => (
              <ReportCard
                key={report.report_id}
                report={report}
                isAdmin={isAdmin}
                busy={busyId === report.report_id}
                reason={reviewReason}
                onReasonChange={setReviewReason}
                onModerate={(status) => void moderate(report, status)}
                onDownload={() => void download(report)}
              />
            ))}
          </CardBody>
        </Card>
      </main>
    </div>
  );
}

function ReportCard({
  report,
  isAdmin,
  busy,
  reason,
  onReasonChange,
  onModerate,
  onDownload,
}: {
  report: CitizenPollutionReport;
  isAdmin: boolean;
  busy: boolean;
  reason: string;
  onReasonChange: (value: string) => void;
  onModerate: (status: 'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED') => void;
  onDownload: () => void;
}) {
  const nextStatuses: Partial<Record<CitizenReportStatus, Array<'UNDER_REVIEW' | 'VERIFIED' | 'REJECTED'>>> = {
    PENDING: ['UNDER_REVIEW', 'REJECTED'],
    UNDER_REVIEW: ['VERIFIED', 'REJECTED'],
  };
  return (
    <article className="rounded-xl border border-ocean-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={report.status === 'VERIFIED' ? 'teal' : report.status === 'REJECTED' ? 'error' : report.status === 'UNDER_REVIEW' ? 'warning' : 'neutral'}>
          {report.status.replace(/_/g, ' ')}
        </Badge>
        <span className="font-semibold text-navy-900">{categoryLabels[report.category]}</span>
        <span className="text-xs text-ocean-500">{formatDate(report.observed_at)}</span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm text-ocean-800">{report.description}</p>
      <p className="mt-2 text-xs text-ocean-600">
        {report.location.latitude.toFixed(5)}, {report.location.longitude.toFixed(5)}
        {isAdmin && ` · Submitted by ${report.submitted_by}`}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={onDownload}><Camera className="h-3.5 w-3.5" /> View photograph</Button>
      </div>
      {isAdmin && nextStatuses[report.status] && (
        <div className="mt-3 rounded-lg bg-ocean-50 p-3">
          <label className="block text-xs font-medium text-navy-800">
            Moderation reason
            <input aria-label={`Moderation reason ${report.report_id}`} className="mt-1 w-full rounded-lg border border-ocean-300 bg-white p-2" maxLength={500} value={reason} onChange={(event) => onReasonChange(event.target.value)} />
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            {nextStatuses[report.status]?.map((status) => (
              <Button key={status} size="sm" variant={status === 'REJECTED' ? 'outline' : 'secondary'} disabled={busy} onClick={() => onModerate(status)}>
                {status === 'VERIFIED' && <ShieldCheck className="h-3.5 w-3.5" />}
                {status.replace(/_/g, ' ')}
              </Button>
            ))}
          </div>
        </div>
      )}
      <ol className="mt-3 space-y-1 border-l-2 border-cyan-200 pl-3">
        {report.status_history.map((item, index) => (
          <li key={`${item.changed_at}-${index}`} className="text-xs text-ocean-600">
            {item.status.replace(/_/g, ' ')} · {formatDate(item.changed_at)} · {item.reason}
          </li>
        ))}
      </ol>
    </article>
  );
}
