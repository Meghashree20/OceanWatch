import { type ReactNode, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { PublicNavbar, Breadcrumbs } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { breadcrumbLabels } from '@/lib/navigation';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/authContext';
import {
  ChevronLeft,
  ChevronRight,
  Compass,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  Satellite,
  Target,
  TrendingUp,
  Waves,
  X,
} from 'lucide-react';

interface PageShellProps {
  children?: ReactNode;
  className?: string;
}

export function PublicLayout({ className }: PageShellProps) {
  const isLandingPage = useLocation().pathname === '/';

  return (
    <div className={cn('flex min-h-screen flex-col', className)}>
      <PublicNavbar />
      <main className="flex-1">
        <RouteTransition><Outlet /></RouteTransition>
      </main>
      {!isLandingPage && <Footer />}
    </div>
  );
}

export function DashboardLayout({ className }: PageShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className={cn('flex h-screen overflow-hidden bg-ocean-50', className)}>
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden h-screen flex-col border-r border-white/10 bg-slate-950/95 text-slate-200 shadow-2xl shadow-slate-950/30 backdrop-blur-xl lg:flex',
          collapsed ? 'w-24' : 'w-72'
        )}
      >
        <DashboardSidebarContent collapsed={collapsed} onToggleCollapse={() => setCollapsed((value) => !value)} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 -translate-x-full flex-col border-r border-white/10 bg-slate-950/95 text-slate-200 shadow-2xl shadow-slate-950/30 backdrop-blur-xl transition-transform duration-300 lg:hidden',
          mobileOpen && 'translate-x-0'
        )}
      >
        <DashboardSidebarContent collapsed={false} onToggleCollapse={() => setMobileOpen(false)} mobile />
      </aside>

      <div className={cn('flex min-w-0 flex-1 flex-col', collapsed ? 'lg:ml-24' : 'lg:ml-72')}>
        <header className="flex h-16 items-center justify-between border-b border-ocean-200 bg-white/80 px-4 backdrop-blur-sm lg:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-ocean-200 bg-white text-ocean-700 transition-colors hover:bg-ocean-50"
            aria-label="Open dashboard navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-600">
              <Waves className="h-4 w-4" />
            </div>
            <div className="text-sm font-semibold text-navy-900">OceanWatch</div>
          </div>
        </header>

        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <RouteTransition><Outlet /></RouteTransition>
        </main>
      </div>
    </div>
  );
}

function DashboardSidebarContent({
  collapsed,
  mobile = false,
  onToggleCollapse,
}: {
  collapsed: boolean;
  mobile?: boolean;
  onToggleCollapse: () => void;
}) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { label: 'Intelligence Dashboard', path: '/intelligence', icon: LayoutDashboard },
    { label: 'Explore Module', path: '/explore', icon: Compass },
    { label: 'Hotspots Module', path: '/hotspots', icon: MapPin },
    { label: 'Forecast Module', path: '/forecast', icon: TrendingUp },
    { label: 'Priority Module', path: '/priority', icon: Target },
    { label: 'Satellite Module', path: '/satellite', icon: Satellite },
  ];

  const handleLogout = async () => {
    navigate('/', { replace: true });
    await logout();
  };

  const initials = (user?.full_name ?? 'OceanWatch')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('') || 'OW';

  return (
    <>
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-4">
        <div className="flex min-w-0 items-center gap-3 overflow-hidden">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400/30 to-teal-400/20 text-cyan-300 ring-1 ring-white/10">
            <Waves className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="min-w-0 overflow-hidden">
              <div className="truncate text-base font-semibold text-white">OceanWatch</div>
              <div className="truncate text-xs text-slate-300">Marine Pollution Intelligence</div>
            </div>
          )}
        </div>

        {mobile ? (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-200 transition-colors hover:bg-white/10 lg:hidden"
            aria-label="Close navigation"
            title="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-200 transition-colors hover:bg-white/10 lg:inline-flex"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        )}
      </div>

      <nav className="mt-6 min-h-0 flex-1 space-y-1.5 overflow-y-auto px-3" aria-label="Dashboard navigation">
        {navItems.map(({ label, path, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end
            title={collapsed ? label : undefined}
            className={({ isActive }) => cn(
              'group flex items-center gap-3 overflow-hidden rounded-2xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
              isActive
                ? 'bg-gradient-to-r from-cyan-500/20 to-teal-500/10 text-white shadow-inner shadow-cyan-500/10 ring-1 ring-cyan-400/30'
                : 'text-slate-300 hover:bg-white/5 hover:text-white',
              collapsed && 'justify-center px-2'
            )}
          >
            <span className={cn(
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-current transition-colors',
              location.pathname === path ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-300 group-hover:text-white'
            )}>
              <Icon className="h-4 w-4" />
            </span>
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className={cn('flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3', collapsed && 'justify-center p-2')}>
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-teal-500/10 text-sm font-semibold text-cyan-200 ring-1 ring-cyan-300/20">
            {initials}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="truncate text-sm font-semibold text-white">{user?.full_name ?? 'OceanWatch user'}</div>
              <div className="truncate text-xs text-slate-300">{user?.email ?? 'marine.intelligence@oceanwatch.ai'}</div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => void handleLogout()}
          className={cn(
            'mt-3 flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:bg-red-500/10 hover:text-white',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'Log out' : undefined}
        >
          <LogOut className="h-4 w-4" />
          {!collapsed && <span>Log out</span>}
        </button>
      </div>
    </>
  );
}

export function AuthPageLayout({ className }: PageShellProps) {
  return (
    <div className={cn('flex min-h-screen flex-col', className)}>
      <main className="flex-1">
        <RouteTransition><Outlet /></RouteTransition>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Route transition — subtle fade on path change                       */
/* ------------------------------------------------------------------ */

function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(false);
    const t = requestAnimationFrame(() => {
      setVisible(true);
    });
    return () => cancelAnimationFrame(t);
  }, [location.pathname]);

  return (
    <div
      className={cn(
        'transition-opacity duration-300 ease-out',
        visible ? 'opacity-100' : 'opacity-0'
      )}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* PageHeader — shared header for internal pages                       */
/* ------------------------------------------------------------------ */

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
}

export function PageHeader({
  eyebrow = 'OceanWatch platform',
  title,
  description,
  children,
}: PageHeaderProps) {
  const location = useLocation();
  const path = location.pathname;
  const currentLabel = breadcrumbLabels[path] ?? title;

  return (
    <section className="relative overflow-hidden border-b border-ocean-200 bg-white">
      <div className="absolute inset-0 dot-pattern opacity-50" />
      <div className="container-page relative py-14 lg:py-20">
        <Breadcrumbs currentLabel={currentLabel} />
        <div className="mt-7 max-w-3xl">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-600">
            <span className="h-px w-6 bg-cyan-400" />
            {eyebrow}
          </div>
          <h1 className="text-4xl font-bold text-navy-950 sm:text-5xl">
            {title}
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-ocean-600">
            {description}
          </p>
          {children && <div className="mt-7">{children}</div>}
        </div>
      </div>
    </section>
  );
}
