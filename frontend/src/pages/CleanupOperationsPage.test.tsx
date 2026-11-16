import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  user: { is_admin: true },
  api: {
    getCleanupRecommendations: vi.fn(),
    getCleanupOperations: vi.fn(),
    getCleanupOperation: vi.fn(),
    getCleanupAnalytics: vi.fn(),
    getOrganizations: vi.fn(),
    createCleanupOperation: vi.fn(),
    getCleanupAssignmentNotifications: vi.fn(),
  },
}));

vi.mock('@/lib/authContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/client', () => ({ oceanWatchApi: mocks.api }));

import { CleanupOperationsPage } from './CleanupOperationsPage';

const recommendation = {
  recommendation_id: 'a'.repeat(64),
  action_type: 'INSPECTION' as const,
  priority: 'HIGH' as const,
  location: { latitude: 10.5, longitude: 20.5 },
  priority_score: null,
  priority_level: 'UNAVAILABLE',
  recommended_action: 'Inspect the area using current observations.',
  evidence: {
    hotspot: null,
    existing_priority_score: null,
    existing_priority_level: null,
    measured_trend: null,
    active_alert: null,
    data_freshness: { status: 'fresh', age_days: 1 },
  },
  uncertainty: ['Existing priority score is unavailable.'],
};

const operation = {
  operation_id: 'operation-1',
  recommendation_id: recommendation.recommendation_id,
  recommendation_snapshot: recommendation,
  location: recommendation.location,
  alert_id: null,
  assigned_organization_id: null,
  responsible_coordinator_user_id: 'user-1',
  scheduled_at: null,
  status: 'PLANNED' as const,
  completion: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  status_history: [{
    status: 'PLANNED' as const,
    changed_at: '2025-01-01T00:00:00Z',
    changed_by: 'user-1',
    reason: 'Created from recommendation.',
  }],
  audit_history: [],
  evidence: [],
};

describe('CleanupOperationsPage', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.user.is_admin = true;
    mocks.api.getCleanupRecommendations.mockResolvedValue({ data: [recommendation], total: 1 });
    mocks.api.getCleanupOperations.mockResolvedValue({ data: [], total: 0, skip: 0, limit: 100 });
    mocks.api.getCleanupOperation.mockResolvedValue(operation);
    mocks.api.getCleanupAnalytics.mockResolvedValue({
      completed_operations: 0,
      monthly_completed_operations: [],
      quantities_by_unit_and_classification: [],
      interpretation: 'No completed operations have been recorded.',
    });
    mocks.api.getOrganizations.mockResolvedValue({ data: [] });
    mocks.api.getCleanupAssignmentNotifications.mockResolvedValue({
      data: [],
      total: 0,
      test_mode: true,
      delivery_recipient_email: 'oceanwatch-test@example.com',
    });
    mocks.api.createCleanupOperation.mockResolvedValue(operation);
  });

  it('creates an operation from an evidence-backed recommendation', async () => {
    mocks.api.getCleanupOperations
      .mockResolvedValueOnce({ data: [], total: 0, skip: 0, limit: 100 })
      .mockResolvedValue({ data: [operation], total: 1, skip: 0, limit: 100 });

    render(<MemoryRouter><CleanupOperationsPage /></MemoryRouter>);
    expect(await screen.findByText('Inspect the area using current observations.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Create operation/ }));

    await waitFor(() => expect(mocks.api.createCleanupOperation).toHaveBeenCalledWith(recommendation.recommendation_id));
    expect(await screen.findByText('Auditable status history')).toBeTruthy();
    expect(screen.getByText('Operation created from the current recommendation.')).toBeTruthy();
  });

  it('does not expose operation creation to non-administrators', async () => {
    mocks.user.is_admin = false;
    render(<MemoryRouter><CleanupOperationsPage /></MemoryRouter>);

    expect(await screen.findByText('Inspect the area using current observations.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Create operation/ })).toBeNull();
  });

  it('shows the controlled email destination and blocks sending without one', async () => {
    mocks.api.getCleanupOperations.mockResolvedValue({
      data: [{ ...operation, assigned_organization_id: 'org-1', assigned_organization_name: 'Response Group' }],
      total: 1,
      skip: 0,
      limit: 100,
    });
    mocks.api.getCleanupOperation.mockResolvedValue({
      ...operation,
      assigned_organization_id: 'org-1',
      assigned_organization_name: 'Response Group',
    });
    mocks.api.getCleanupAssignmentNotifications.mockResolvedValue({
      data: [],
      total: 0,
      test_mode: true,
      delivery_recipient_email: null,
    });

    render(<MemoryRouter><CleanupOperationsPage /></MemoryRouter>);
    expect(await screen.findByText(/no test recipient is configured/)).toBeTruthy();
    const sendButton = await screen.findByRole('button', { name: /Approve & send test email/ });

    expect(sendButton).toHaveProperty('disabled', true);
  });
});
