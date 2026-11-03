import { type ReactNode, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { DashboardNavbar, PublicNavbar, Breadcrumbs } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { breadcrumbLabels } from '@/lib/navigation';
import { cn } from '@/lib/utils';

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
  return (
    <div className={cn('flex min-h-screen flex-col', className)}>
      <DashboardNavbar />
      <main className="flex-1">
        <RouteTransition><Outlet /></RouteTransition>
      </main>
    </div>
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
