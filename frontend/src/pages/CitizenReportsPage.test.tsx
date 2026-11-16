import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  user: { is_admin: false },
  api: {
    getCitizenReports: vi.fn(),
    submitCitizenReport: vi.fn(),
    moderateCitizenReport: vi.fn(),
    downloadCitizenReportPhoto: vi.fn(),
  },
}));

vi.mock('@/lib/authContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/client', () => ({ oceanWatchApi: mocks.api }));

import { CitizenReportsPage } from './CitizenReportsPage';

const report = {
  report_id: 'report-1',
  category: 'PLASTIC_DEBRIS' as const,
  description: 'Plastic fragments found near the inlet.',
  location: { latitude: 10.5, longitude: 20.5 },
  observed_at: '2025-01-01T10:00:00Z',
  media_id: 'media-1',
  submitted_by: 'user-1',
  status: 'PENDING' as const,
  created_at: '2025-01-01T10:00:00Z',
  updated_at: '2025-01-01T10:00:00Z',
  status_history: [{
    status: 'PENDING' as const,
    changed_at: '2025-01-01T10:00:00Z',
    changed_by: 'user-1',
    reason: 'Awaiting moderation.',
  }],
};

describe('CitizenReportsPage', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.user.is_admin = false;
    mocks.api.getCitizenReports.mockResolvedValue({ data: [], total: 0 });
    mocks.api.submitCitizenReport.mockResolvedValue(report);
    mocks.api.moderateCitizenReport.mockResolvedValue({ ...report, status: 'UNDER_REVIEW' });
  });

  it('submits a photo and observation details without presenting the report as verified', async () => {
    render(<MemoryRouter><CitizenReportsPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Report description'), {
      target: { value: 'Plastic fragments found near the inlet.' },
    });
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '10.5' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '20.5' } });
    fireEvent.change(screen.getByLabelText('Report photograph'), {
      target: { files: [new File(['image'], 'report.png', { type: 'image/png' })] },
    });
    fireEvent.submit(screen.getByRole('button', { name: 'Submit for moderation' }).closest('form')!);

    await waitFor(() => expect(mocks.api.submitCitizenReport).toHaveBeenCalledWith(expect.objectContaining({
      category: 'PLASTIC_DEBRIS',
      description: 'Plastic fragments found near the inlet.',
      latitude: 10.5,
      longitude: 20.5,
      file: expect.any(File),
    })));
    expect(await screen.findByText(/not a verified pollution observation/)).toBeTruthy();
  });

  it('lets administrators move pending reports into review with an audit reason', async () => {
    mocks.user.is_admin = true;
    mocks.api.getCitizenReports.mockResolvedValue({ data: [report], total: 1 });
    render(<MemoryRouter><CitizenReportsPage /></MemoryRouter>);

    fireEvent.change(await screen.findByLabelText('Moderation reason report-1'), {
      target: { value: 'Checking the supplied location and image.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'UNDER REVIEW' }));

    await waitFor(() => expect(mocks.api.moderateCitizenReport).toHaveBeenCalledWith(
      'report-1',
      'UNDER_REVIEW',
      'Checking the supplied location and image.',
    ));
  });
});
