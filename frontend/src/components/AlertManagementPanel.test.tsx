import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  user: { is_admin: true },
  api: {
    updatePollutionAlert: vi.fn(),
    previewOrganizationNotifications: vi.fn(),
    getAlertNotifications: vi.fn(),
    sendOrganizationNotification: vi.fn(),
    acknowledgeOrganizationNotification: vi.fn(),
    getOrganizations: vi.fn(),
    createOrganization: vi.fn(),
    verifyOrganization: vi.fn(),
  },
}));

vi.mock('@/lib/authContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/client', () => ({ oceanWatchApi: mocks.api }));

import { AlertManagementPanel, OrganizationDirectoryPanel } from './AlertManagementPanel';

const alert = {
  alert_id: 'alert-1',
  location: { latitude: 10.5, longitude: 20.5, cell_size_degrees: 1 },
  source: 'observed NOAA microplastic measurements',
  risk_level: 'HIGH' as const,
  triggering_evidence: {
    change_types: ['newly_high_risk'],
    comparison: {
      recent_mean_pieces_m3: 12,
      previous_mean_pieces_m3: 1,
      absolute_change_pieces_m3: 11,
      relative_change: 11,
      previous_risk_level: 'MEDIUM' as const,
    },
    evidence: {
      recent_observation_count: 4,
      recent_sampling_site_count: 2,
      previous_observation_count: 3,
      previous_sampling_site_count: 2,
      recent_period: { start: '2024-01-01', end: '2024-03-31' },
      previous_period: { start: '2023-10-01', end: '2024-01-01' },
      frequency_adjustment: 'mean of per-site means',
      data_quality: 'moderate' as const,
      baseline_available: true,
      adjacent_previous_high_risk_cell: false,
    },
  },
  status: 'ACTIVE' as const,
  created_at: '2024-03-31T00:00:00Z',
  last_updated_at: '2024-03-31T00:00:00Z',
  responsible_user_id: null,
  status_history: [{
    status: 'ACTIVE' as const,
    changed_at: '2024-03-31T00:00:00Z',
    changed_by: 'system',
    reason: 'Configured observed threshold reached.',
  }],
};

const suggestion = {
  organization_id: 'org-1',
  name: 'Verified Response Group',
  contact_email: 'response@example.org',
  delivery_recipient_email: 'oceanwatch-test@example.com',
  test_mode: true,
  areas_served: ['Bay A'],
  subject: 'OceanWatch HIGH observed pollution warning',
  body: 'Observed assessment details',
};

describe('AlertManagementPanel', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.user.is_admin = true;
    mocks.api.updatePollutionAlert.mockResolvedValue({ ...alert, status: 'ACKNOWLEDGED' });
    mocks.api.previewOrganizationNotifications.mockResolvedValue({ data: [suggestion], total: 1 });
    mocks.api.getAlertNotifications.mockResolvedValue({ data: [], total: 0 });
    mocks.api.sendOrganizationNotification.mockResolvedValue({
      notification_id: 'notification-1',
      recipient_email: suggestion.contact_email,
      delivery_status: 'SENT',
    });
    mocks.api.getOrganizations.mockResolvedValue({ data: [] });
    mocks.api.createOrganization.mockResolvedValue({ organization_id: 'org-1' });
    mocks.api.verifyOrganization.mockResolvedValue({});
  });

  it('updates alert status and explicitly previews then approves organization email', async () => {
    const onRefresh = vi.fn();
    render(<AlertManagementPanel alerts={[alert]} onRefresh={onRefresh} />);

    fireEvent.change(screen.getByRole('combobox', { name: /Update status/ }), {
      target: { value: 'ACKNOWLEDGED' },
    });
    await waitFor(() => expect(mocks.api.updatePollutionAlert).toHaveBeenCalledWith('alert-1', 'ACKNOWLEDGED'));
    expect(onRefresh).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Review organizations/ }));
    expect(await screen.findByText(/Verified Response Group/)).toBeTruthy();
    expect(mocks.api.sendOrganizationNotification).not.toHaveBeenCalled();
    expect(await screen.findByText(/approval sends only to oceanwatch-test@example.com, not response@example.org/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Approve & send test email/ }));
    await waitFor(() => expect(mocks.api.sendOrganizationNotification).toHaveBeenCalledWith('alert-1', 'org-1'));
  });

  it('prevents approval when test mode has no controlled recipient', async () => {
    mocks.api.previewOrganizationNotifications.mockResolvedValue({
      data: [{ ...suggestion, delivery_recipient_email: null }],
      total: 1,
    });
    render(<AlertManagementPanel alerts={[alert]} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Review organizations/ }));

    const sendButton = await screen.findByRole('button', { name: /Approve & send test email/ });
    expect(sendButton).toHaveProperty('disabled', true);
    expect(screen.getByText(/no test recipient is configured/)).toBeTruthy();
  });

  it('does not expose external email approval to non-administrators', async () => {
    mocks.user.is_admin = false;
    render(<AlertManagementPanel alerts={[alert]} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Review organizations/ }));

    expect(await screen.findByText(/An administrator must approve external email delivery/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Approve & send email/ })).toBeNull();
  });
});

describe('OrganizationDirectoryPanel', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.user.is_admin = true;
    mocks.api.getOrganizations.mockResolvedValue({ data: [] });
    mocks.api.createOrganization.mockResolvedValue({ organization_id: 'org-1' });
  });

  it('registers user-provided organization data without marking it verified', async () => {
    render(<OrganizationDirectoryPanel />);
    fireEvent.change(screen.getByLabelText('Organization name'), { target: { value: 'Response Org' } });
    fireEvent.change(screen.getByLabelText('Contact email'), { target: { value: 'team@example.org' } });
    fireEvent.change(screen.getByLabelText(/GeoJSON Polygon service area/), {
      target: { value: '{"type":"Polygon","coordinates":[[[1,1],[2,1],[2,2],[1,1]]]}' },
    });
    fireEvent.change(screen.getByLabelText(/Areas served/), { target: { value: 'Bay A, Bay B' } });
    fireEvent.click(screen.getByRole('button', { name: 'Register organization' }));

    await waitFor(() => expect(mocks.api.createOrganization).toHaveBeenCalledWith({
      name: 'Response Org',
      contact_email: 'team@example.org',
      service_area: { type: 'Polygon', coordinates: [[[1, 1], [2, 1], [2, 2], [1, 1]]] },
      areas_served: ['Bay A', 'Bay B'],
      email_notifications_enabled: true,
      acknowledgment_required: true,
    }));
    expect(await screen.findByRole('status')).toBeTruthy();
  });
});
