import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { PageShell } from '@/components/layout/PageShell';
import { HomePage } from '@/pages/HomePage';
import { HotspotsPage } from '@/pages/HotspotsPage';
import { ForecastPage } from '@/pages/ForecastPage';
import { PriorityPage } from '@/pages/PriorityPage';
import { DataExplorerPage } from '@/pages/DataExplorerPage';
import { IntelligencePage } from '@/pages/IntelligencePage';
import { PlatformPage, type PlatformPageConfig } from '@/pages/PlatformPage';

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
      <PageShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/hotspots" element={<HotspotsPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/priority" element={<PriorityPage />} />
          <Route path="/data" element={<DataExplorerPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          {Object.entries(pageConfigs)
            .filter(([slug]) => slug !== 'hotspots' && slug !== 'forecast' && slug !== 'priority' && slug !== 'data' && slug !== 'intelligence')
            .map(([slug, config]) => (
              <Route key={slug} path={`/${slug}`} element={<PlatformPage config={config} />} />
            ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </PageShell>
    </BrowserRouter>
  );
}

export default App;
