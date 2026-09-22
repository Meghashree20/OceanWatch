import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  ArrowUpRight,
  ChevronDown,
  Menu,
  Waves,
  X,
} from 'lucide-react';
import {
  breadcrumbLabels,
  mobileNavGroups,
  platformNavItems,
  type NavItem,
} from '@/lib/navigation';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="group inline-flex items-center gap-2.5" aria-label="OceanWatch home">
      <span
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-lg transition-transform duration-300 group-hover:scale-105 group-hover:-rotate-6',
          light ? 'bg-white/10 ring-1 ring-white/15' : 'bg-navy-900 ring-1 ring-navy-800'
        )}
      >
        <Waves className="h-5 w-5 text-cyan-400" strokeWidth={2.5} />
      </span>
      <span
        className={cn(
          'font-display text-lg font-bold tracking-tight',
          light ? 'text-white' : 'text-navy-950'
        )}
      >
        Ocean<span className="text-cyan-500">Watch</span>
      </span>
    </Link>
  );
}

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Lock body scroll when mobile menu open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 transition-all duration-300',
        scrolled
          ? 'border-b border-ocean-200/80 bg-ocean-50/95 shadow-sm backdrop-blur-xl'
          : 'border-b border-transparent bg-ocean-50/80 backdrop-blur-md'
      )}
    >
      <div className="container-page flex h-16 items-center justify-between">
        <Logo />

        {/* Desktop nav */}
        <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Primary navigation">
          <NavLink to="/" end className={navLinkClass}>
            Home
          </NavLink>

          {/* Platform dropdown */}
          <PlatformDropdown />

          {/* Direct secondary links */}
          <NavLink to="/data" className={navLinkClass}>
            Data
          </NavLink>
          <NavLink to="/models" className={navLinkClass}>
            Models
          </NavLink>
          <NavLink to="/about" className={navLinkClass}>
            About
          </NavLink>
        </nav>

        {/* CTA + mobile toggle */}
        <div className="flex items-center gap-2">
          <Button to="/intelligence" size="sm" className="hidden sm:inline-flex">
            Explore Intelligence
            <ArrowUpRight className="h-4 w-4" />
          </Button>
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            className="rounded-lg p-2 text-navy-800 transition-colors hover:bg-ocean-100 lg:hidden"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {mobileOpen && <MobileNav />}
    </header>
  );
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    'relative rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'text-navy-950'
      : 'text-ocean-700 hover:bg-ocean-100/70 hover:text-navy-950'
  );
}

/* ------------------------------------------------------------------ */
/* Platform dropdown                                                   */
/* ------------------------------------------------------------------ */

function PlatformDropdown() {
  const [open, setOpen] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const location = useLocation();

  // Check if any platform item is active
  const isPlatformActive = platformNavItems.some(
    (item) => location.pathname === item.path
  );

  const handleEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setOpen(true);
  };

  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isPlatformActive
            ? 'text-navy-950'
            : 'text-ocean-700 hover:bg-ocean-100/70 hover:text-navy-950'
        )}
        aria-haspopup="true"
        aria-expanded={open}
      >
        Platform
        <ChevronDown
          className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')}
        />
      </button>

      {open && (
        <>
          {/* Invisible bridge to prevent gap flicker */}
          <div className="absolute right-0 top-full h-3 w-full" />
          <div className="absolute right-0 top-full w-80 pt-1">
            <div className="overflow-hidden rounded-xl border border-ocean-200 bg-white shadow-card-hover">
              <div className="border-b border-ocean-100 px-4 py-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-ocean-500">
                  Intelligence modules
                </p>
              </div>
              <div className="p-2">
                {platformNavItems.map((item) => {
                  const Icon = item.icon;
                  const active = location.pathname === item.path;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setOpen(false)}
                      className={cn(
                        'flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors',
                        active ? 'bg-ocean-50' : 'hover:bg-ocean-50'
                      )}
                    >
                      <span
                        className={cn(
                          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg',
                          active
                            ? 'bg-cyan-100 text-cyan-700'
                            : 'bg-ocean-100 text-ocean-600'
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold text-navy-900">
                          {item.shortLabel}
                        </span>
                        <span className="mt-0.5 block text-xs text-ocean-500">
                          {item.description}
                        </span>
                      </span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Mobile nav                                                          */
/* ------------------------------------------------------------------ */

function MobileNav() {
  const location = useLocation();

  return (
    <div
      id="mobile-nav"
      className="fixed inset-x-0 top-16 bottom-0 z-40 overflow-y-auto bg-ocean-50 lg:hidden"
    >
      <nav className="container-page py-6" aria-label="Mobile navigation">
        {mobileNavGroups.map((group) => (
          <div key={group.label} className="mb-6">
            <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-ocean-500">
              {group.label}
            </p>
            <div className="overflow-hidden rounded-xl border border-ocean-200 bg-white">
              {group.items.map((item, index) => (
                <MobileNavLink
                  key={item.path}
                  item={item}
                  active={location.pathname === item.path}
                  isFirst={index === 0}
                />
              ))}
            </div>
          </div>
        ))}

        <div className="mt-4">
          <Button to="/intelligence" size="lg" className="w-full">
            Explore Intelligence
            <ArrowUpRight className="h-4 w-4" />
          </Button>
        </div>
      </nav>
    </div>
  );
}

function MobileNavLink({
  item,
  active,
  isFirst,
}: {
  item: NavItem;
  active: boolean;
  isFirst: boolean;
}) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.path}
      end={item.path === '/'}
      className={cn(
        'flex items-center gap-3 px-4 py-3.5 transition-colors',
        active ? 'bg-cyan-50' : 'hover:bg-ocean-50',
        !isFirst && 'border-t border-ocean-100'
      )}
    >
      <span
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
          active ? 'bg-cyan-100 text-cyan-700' : 'bg-ocean-100 text-ocean-600'
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="flex-1">
        <span
          className={cn(
            'block text-sm font-semibold',
            active ? 'text-cyan-800' : 'text-navy-900'
          )}
        >
          {item.shortLabel}
        </span>
        <span className="mt-0.5 block text-xs text-ocean-500">
          {item.description}
        </span>
      </span>
      {active && <span className="h-2 w-2 rounded-full bg-cyan-500" />}
    </NavLink>
  );
}

/* ------------------------------------------------------------------ */
/* Breadcrumbs                                                         */
/* ------------------------------------------------------------------ */

export function Breadcrumbs({ currentLabel }: { currentLabel?: string }) {
  const location = useLocation();
  const path = location.pathname;

  if (path === '/') return null;

  const label = currentLabel ?? breadcrumbLabels[path] ?? '';

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs font-medium text-ocean-500">
      <Link to="/" className="transition-colors hover:text-cyan-600">
        Home
      </Link>
      <ChevronDown className="h-3 w-3 -rotate-90 text-ocean-400" />
      <span className="text-ocean-700">{label}</span>
    </nav>
  );
}
