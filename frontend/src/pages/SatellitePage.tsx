import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, FileImage, Image as ImageIcon, LoaderCircle, Satellite, Upload, Waves } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageShell';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { oceanWatchApi, type SatelliteAnalysis, type SatelliteCatalogItem } from '@/lib/api/client';

const ACCEPTED_EXTENSIONS = ['.tif', '.tiff'];

function isGeoTiff(file: File) {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension));
}

function imageDataUrl(base64: string, type: 'png' = 'png') {
  return `data:image/${type};base64,${base64}`;
}

export function SatellitePage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [catalog, setCatalog] = useState<SatelliteCatalogItem[]>([]);
  const [analysis, setAnalysis] = useState<SatelliteAnalysis | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    oceanWatchApi.getSatelliteCatalog()
      .then((items) => { if (active) setCatalog(items); })
      .catch(() => null)
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, []);

  const analyzeFile = (file: File) => {
    if (!isGeoTiff(file)) {
      setError('Please choose an 11-band GeoTIFF file with a .tif or .tiff extension.');
      return;
    }
    if (file.size === 0) {
      setError('The selected GeoTIFF file is empty.');
      return;
    }
    setSelectedFileName(file.name);
    setAnalysis(null);
    setError(null);
    setLoading(true);
    oceanWatchApi.analyzeSatellite(file)
      .then(setAnalysis)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  };

  const analyzeCatalogItem = (item: SatelliteCatalogItem) => {
    setSelectedFileName(item.sample_file);
    setAnalysis(null);
    setError(null);
    setLoading(true);
    oceanWatchApi.analyzeRegisteredSatellite(item.id)
      .then(setAnalysis)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <PageHeader
        title="Satellite Debris Analysis"
        description="Run the MARIDA U-Net segmentation model on an 11-band Sentinel-2 GeoTIFF and inspect the returned debris mask."
        eyebrow="Remote sensing"
      >
        <Badge variant="cyan" icon={<span className="h-1.5 w-1.5 rounded-full bg-cyan-500" />}>U-Net segmentation</Badge>
      </PageHeader>

      <div className="container-page py-10 lg:py-14">
        <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700"><Upload className="h-4 w-4" /></div>
                <h2 className="text-base font-bold text-navy-950">Analyze GeoTIFF</h2>
              </div>
              <p className="mt-2 text-sm leading-5 text-ocean-500">Upload an 11-band Sentinel-2 L2A GeoTIFF. The backend validates the raster before running inference.</p>
            </CardHeader>
            <CardBody>
              <input
                ref={fileInputRef}
                type="file"
                accept=".tif,.tiff,image/tiff"
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) analyzeFile(file);
                  event.target.value = '';
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-ocean-200 bg-ocean-50 px-5 py-10 text-center transition-colors hover:border-cyan-400 hover:bg-cyan-50"
              >
                <FileImage className="h-8 w-8 text-cyan-600" />
                <span className="mt-3 text-sm font-semibold text-navy-900">Choose a GeoTIFF file</span>
                <span className="mt-1 text-xs text-ocean-500">.tif or .tiff · exactly 11 spectral bands</span>
              </button>
              {selectedFileName && <p className="mt-3 truncate text-xs text-ocean-500">Selected: <span className="font-medium text-navy-800">{selectedFileName}</span></p>}

              <div className="mt-6 border-t border-ocean-100 pt-5">
                <div className="flex items-center gap-2">
                  <Satellite className="h-4 w-4 text-cyan-600" />
                  <h3 className="text-sm font-bold text-navy-950">Registered sample sites</h3>
                </div>
                {catalogLoading ? (
                  <p className="mt-3 text-xs text-ocean-500">Loading available samples…</p>
                ) : catalog.length === 0 ? (
                  <p className="mt-3 text-xs text-ocean-500">No registered sample sites are available.</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {catalog.map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-ocean-100 bg-white p-3">
                        <div className="min-w-0">
                          <p className="truncate text-xs font-semibold text-navy-900">{item.name}</p>
                          <p className="mt-0.5 truncate text-[11px] text-ocean-500">{item.description}</p>
                        </div>
                        <Button variant="ghost" size="sm" disabled={!item.has_local_sample || loading} onClick={() => analyzeCatalogItem(item)}>
                          Analyze
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-700"><Waves className="h-4 w-4" /></div>
                  <h2 className="text-base font-bold text-navy-950">Analysis results</h2>
                </div>
                <Badge variant={loading ? 'neutral' : analysis ? 'cyan' : error ? 'error' : 'neutral'}>
                  {loading ? 'Analyzing' : analysis ? 'Complete' : error ? 'Unavailable' : 'Awaiting input'}
                </Badge>
              </div>
            </CardHeader>
            <CardBody>
              {loading ? (
                <div className="flex min-h-[22rem] flex-col items-center justify-center text-center">
                  <LoaderCircle className="h-8 w-8 animate-spin text-cyan-600" />
                  <p className="mt-4 text-sm font-semibold text-navy-900">Running U-Net inference</p>
                  <p className="mt-1 text-xs text-ocean-500">The backend is validating and analyzing the raster.</p>
                </div>
              ) : error ? (
                <div className="flex min-h-[22rem] flex-col items-center justify-center text-center">
                  <AlertCircle className="h-8 w-8 text-red-500" />
                  <p className="mt-4 text-sm font-semibold text-red-800">Satellite analysis failed</p>
                  <p className="mt-1 max-w-md text-xs leading-5 text-red-700">{error}</p>
                </div>
              ) : analysis ? (
                <AnalysisResult analysis={analysis} />
              ) : (
                <div className="flex min-h-[22rem] flex-col items-center justify-center text-center">
                  <ImageIcon className="h-8 w-8 text-ocean-300" />
                  <p className="mt-4 text-sm font-semibold text-navy-800">No analysis selected</p>
                  <p className="mt-1 max-w-md text-xs leading-5 text-ocean-500">Upload a GeoTIFF or choose a registered sample site to view the actual U-Net output.</p>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function AnalysisResult({ analysis }: { analysis: SatelliteAnalysis }) {
  const metadata = analysis.raster_metadata;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Debris pixels" value={analysis.debris_pixel_count.toLocaleString()} />
        <Metric label="Total pixels" value={analysis.total_pixels.toLocaleString()} />
        <Metric label="Debris coverage" value={`${analysis.debris_coverage_percentage.toFixed(4)}%`} />
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-800">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        <span><strong>{analysis.name}</strong> · {analysis.description}</span>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <ImagePanel title="Satellite preview" src={imageDataUrl(analysis.preview_png_base64)} />
        <ImagePanel title="U-Net debris segmentation mask / overlay" src={imageDataUrl(analysis.overlay_png_base64)} overlay />
      </div>
      {metadata && (
        <dl className="grid gap-3 border-t border-ocean-100 pt-4 text-xs sm:grid-cols-3">
          <Metadata label="Raster size" value={`${metadata.width} × ${metadata.height}`} />
          <Metadata label="Bands" value={String(metadata.count)} />
          <Metadata label="CRS" value={metadata.crs ?? 'Not provided'} />
        </dl>
      )}
    </div>
  );
}

function ImagePanel({ title, src, overlay = false }: { title: string; src: string; overlay?: boolean }) {
  return (
    <figure>
      <figcaption className="mb-2 text-xs font-semibold text-navy-800">{title}</figcaption>
      <div className={`flex min-h-48 items-center justify-center overflow-hidden rounded-xl border border-ocean-200 p-2 ${overlay ? 'bg-navy-950' : 'bg-ocean-50'}`}>
        <img src={src} alt={title} className="max-h-72 w-full object-contain" />
      </div>
    </figure>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-ocean-100 bg-ocean-50 p-3">
      <p className="text-[11px] font-medium text-ocean-500">{label}</p>
      <p className="mt-1 font-display text-xl font-bold text-navy-950">{value}</p>
    </div>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-ocean-500">{label}</dt>
      <dd className="mt-1 break-words font-mono text-navy-800">{value}</dd>
    </div>
  );
}
