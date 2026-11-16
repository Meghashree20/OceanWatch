import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const api = vi.hoisted(() => ({
  getSatelliteCatalog: vi.fn(),
  validateSatellite: vi.fn(),
  analyzeSatellite: vi.fn(),
  analyzeRegisteredSatellite: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({ oceanWatchApi: api }));

import { SatellitePage } from './SatellitePage';

const unverifiedResult = {
  compatibility_status: 'DECLARED_UNVERIFIED' as const,
  validation_warnings: [],
  validation_errors: ['Band identities are missing; provenance is not independently verified.'],
  detected_band_count: 11,
  verified_band_identities: null,
  crs: 'EPSG:32616',
  spatial_resolution_m: 10,
  geographic_bounds: [-93, 40, -92.9, 40.1],
  reflectance_calibration_status: 'UNKNOWN',
  source_provenance_status: 'UNVERIFIED',
  invalid_pixel_percentage: 0,
  inference_permitted: false,
  raster_metadata: null,
  band_statistics: [],
};

const verifiedResult = {
  ...unverifiedResult,
  compatibility_status: 'VERIFIED_COMPATIBLE' as const,
  validation_errors: [],
  verified_band_identities: ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12'],
  reflectance_calibration_status: 'VERIFIED_REFLECTANCE_IDENTITY',
  source_provenance_status: 'INDEPENDENTLY_VERIFIED',
  inference_permitted: true,
};

function rasterInput(container: HTMLElement) {
  return container.querySelector('input[type="file"][accept*=".tif"]') as HTMLInputElement;
}

function renderPage() {
  return render(<MemoryRouter><SatellitePage /></MemoryRouter>);
}

describe('SatellitePage validation workflow', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    api.getSatelliteCatalog.mockResolvedValue([]);
    api.analyzeSatellite.mockImplementation(() => new Promise(() => undefined));
  });

  it('shows validation findings and keeps Analyze disabled for unverified inputs', async () => {
    api.validateSatellite.mockResolvedValue(unverifiedResult);
    const user = userEvent.setup();
    const { container } = renderPage();
    const file = new File(['raster bytes'], 'coast.tif', { type: 'image/tiff' });

    await user.upload(rasterInput(container), file);

    expect(await screen.findByText('DECLARED UNVERIFIED')).toBeTruthy();
    expect(screen.getByText(/Band identities are missing/)).toBeTruthy();
    expect(screen.getByText(/identity\/order not verified/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Analyze Satellite Image' }).hasAttribute('disabled')).toBe(true);
    expect(api.validateSatellite).toHaveBeenCalledWith(file, undefined, undefined);
    expect(api.analyzeSatellite).not.toHaveBeenCalled();
  });

  it('enables Analyze only after the server reports verified compatibility', async () => {
    api.validateSatellite.mockResolvedValue(verifiedResult);
    const user = userEvent.setup();
    const { container } = renderPage();
    const file = new File(['raster bytes'], 'verified.tif', { type: 'image/tiff' });

    await user.upload(rasterInput(container), file);

    const analyzeButton = await screen.findByRole('button', { name: 'Analyze Satellite Image' });
    await waitFor(() => expect(analyzeButton.hasAttribute('disabled')).toBe(false));
    await user.click(analyzeButton);
    expect(api.analyzeSatellite).toHaveBeenCalledWith(file, undefined, undefined);
  });

  it('displays backend validation request errors', async () => {
    api.validateSatellite.mockRejectedValue(new Error('Validation service is unavailable.'));
    const user = userEvent.setup();
    const { container } = renderPage();
    const file = new File(['raster bytes'], 'coast.tif', { type: 'image/tiff' });

    await user.upload(rasterInput(container), file);

    expect(await screen.findByText('Validation service is unavailable.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Analyze Satellite Image' }).hasAttribute('disabled')).toBe(true);
  });
});
