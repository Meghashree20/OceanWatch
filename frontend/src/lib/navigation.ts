import {
  BarChart3,
  Compass,
  Database,
  Flame,
  Home,
  Info,
  LayoutDashboard,
  Target,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  label: string;
  shortLabel: string;
  path: string;
  description: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navItems: NavItem[] = [
  { label: 'Home', shortLabel: 'Home', path: '/', description: 'Overview of the OceanWatch platform', icon: Home },
  { label: 'Explore Data', shortLabel: 'Explore', path: '/explore', description: 'Browse marine pollution datasets', icon: Compass },
  { label: 'Pollution Hotspots', shortLabel: 'Hotspots', path: '/hotspots', description: 'Geographic clustering of pollution zones', icon: Flame },
  { label: 'Pollution Forecast', shortLabel: 'Forecast', path: '/forecast', description: 'Predictive pollution concentration models', icon: TrendingUp },
  { label: 'Cleanup Priority', shortLabel: 'Priority', path: '/priority', description: 'Weighted decision-support scoring', icon: Target },
  { label: 'Ocean Intelligence', shortLabel: 'Intelligence', path: '/intelligence', description: 'Integrated marine intelligence dashboard', icon: LayoutDashboard },
  { label: 'Data Explorer', shortLabel: 'Data', path: '/data', description: 'Query and filter raw observation data', icon: Database },
  { label: 'Model Insights', shortLabel: 'Models', path: '/models', description: 'ML model performance and architecture', icon: BarChart3 },
  { label: 'About OceanWatch', shortLabel: 'About', path: '/about', description: 'About the OceanWatch project', icon: Info },
];

// Desktop nav: Home + Platform dropdown + direct links + CTA
export const directNavItems: NavItem[] = [
  navItems[0], // Home
];

export const platformNavItems: NavItem[] = [
  navItems[1], // Explore
  navItems[2], // Hotspots
  navItems[3], // Forecast
  navItems[4], // Priority
  navItems[5], // Intelligence
];

export const secondaryNavItems: NavItem[] = [
  navItems[6], // Data
  navItems[7], // Models
  navItems[8], // About
];

// Mobile nav groups
export const mobileNavGroups: NavGroup[] = [
  { label: 'Platform', items: [navItems[0], ...platformNavItems] },
  { label: 'Insights', items: [navItems[6], navItems[7]] },
  { label: 'Project', items: [navItems[8]] },
];

export const footerNavGroups: NavGroup[] = [
  {
    label: 'Platform',
    items: platformNavItems,
  },
  {
    label: 'Insights',
    items: [navItems[6], navItems[7]],
  },
  {
    label: 'Project',
    items: [navItems[0], navItems[8]],
  },
];

// Breadcrumb label lookup
export const breadcrumbLabels: Record<string, string> = Object.fromEntries(
  navItems.map((item) => [item.path, item.shortLabel])
);
