import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AuthPageLayout, DashboardLayout, PublicLayout } from '@/components/layout/PageShell';
import { HomePage } from '@/pages/HomePage';
import { type PlatformPageConfig } from '@/pages/PlatformPage';
import { DashboardFiltersProvider } from '@/lib/DashboardFiltersProvider';
import { AuthProvider } from '@/lib/auth';

const PlatformPage = lazy(() => import('@/pages/PlatformPage').then(({ PlatformPage: page }) => ({ default: page })));
const HotspotsPage = lazy(() => import('@/pages/HotspotsPage').then(({ HotspotsPage: page }) => ({ default: page })));
const ForecastPage = lazy(() => import('@/pages/ForecastPage').then(({ ForecastPage: page }) => ({ default: page })));
const PriorityPage = lazy(() => import('@/pages/PriorityPage').then(({ PriorityPage: page }) => ({ default: page })));
const DataExplorerPage = lazy(() => import('@/pages/DataExplorerPage').then(({ DataExplorerPage: page }) => ({ default: page })));
const IntelligencePage = lazy(() => import('@/pages/IntelligencePage').then(({ IntelligencePage: page }) => ({ default: page })));
const SatellitePage = lazy(() => import('@/pages/SatellitePage').then(({ SatellitePage: page }) => ({ default: page })));
const LoginPage = lazy(() => import('@/pages/LoginPage').then(({ LoginPage: page }) => ({ default: page })));
const SignupPage = lazy(() => import('@/pages/SignupPage').then(({ SignupPage: page }) => ({ default: page })));

const pageConfigs: Record<string, PlatformPageConfig> = {
  explore: {
    title: 'Explore Data',
    description: 'Discover the marine observation data that forms the foundation of OceanWatch environmental intelligence.',
    type: 'explore',
  },
  hotspots: {
    title: 'Pollution Hotspots',
    description: 'Identify where marine plastic pollution concentrates through spatial clustering and geographic analysis.',
    type: 'hotspots',
  },
  forecast: {
    title: 'Pollution Forecast',
    description: 'Look ahead with predictive insights into future pollution concentration and changing marine conditions.',
    type: 'forecast',
  },
  priority: {
    title: 'Cleanup Priority',
    description: 'Translate pollution intelligence into a transparent, evidence-led sequence for cleanup intervention.',
    type: 'priority',
  },
  intelligence: {
    title: 'Ocean Intelligence',
    description: 'Bring hotspot detection, pollution forecasting, and cleanup prioritization together in one decision-ready view.',
    type: 'intelligence',
    badge: 'Unified intelligence layer · concept preview',
  },
  data: {
    title: 'Data Explorer',
    description: 'Inspect the structured observations behind every OceanWatch insight with a workspace designed for clarity.',
    type: 'data',
  },
  models: {
    title: 'Model Insights',
    description: 'Understand the methods, signals, and performance measures behind OceanWatch analysis.',
    type: 'models',
  },
  about: {
    title: 'About OceanWatch',
    description: 'Learn about the vision behind this marine plastic pollution intelligence system and the problem it is designed to address.',
    eyebrow: 'About the project',
    badge: 'Frontend foundation · project preview',
    type: 'about',
  },
};

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <DashboardFiltersProvider>
          <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
            <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/about" element={<PlatformPage config={pageConfigs.about} />} />
              <Route path="/models" element={<PlatformPage config={pageConfigs.models} />} />
            </Route>
            <Route element={<AuthPageLayout />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path="/explore" element={<PlatformPage config={pageConfigs.explore} />} />
                <Route path="/hotspots" element={<HotspotsPage />} />
                <Route path="/forecast" element={<ForecastPage />} />
                <Route path="/priority" element={<PriorityPage />} />
                <Route path="/intelligence" element={<IntelligencePage />} />
                <Route path="/data" element={<DataExplorerPage />} />
                <Route path="/satellite" element={<SatellitePage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </DashboardFiltersProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
