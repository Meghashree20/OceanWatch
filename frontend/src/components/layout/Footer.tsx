import { ArrowUpRight, Mail } from 'lucide-react';
import { Link } from 'react-router-dom';
import { footerNavGroups } from '@/lib/navigation';
import { Logo } from '@/components/layout/Navbar';

export function Footer() {
  return (
    <footer className="border-t border-navy-800 bg-navy-950 text-white">
      <div className="container-page py-16 lg:py-20">
        <div className="grid gap-12 lg:grid-cols-[1.5fr_2fr]">
          {/* Brand + description */}
          <div className="max-w-sm">
            <Logo light />
            <p className="mt-5 text-sm leading-relaxed text-ocean-300">
              An environmental intelligence platform transforming marine
              pollution data into clear, actionable decisions for a cleaner
              ocean.
            </p>
            <Link
              to="/about"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-cyan-400 transition-colors hover:text-cyan-300"
            >
              Learn about the project
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>

          {/* Nav groups */}
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {footerNavGroups.map((group) => (
              <div key={group.label}>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-ocean-400">
                  {group.label}
                </h3>
                <ul className="mt-4 space-y-3">
                  {group.items.map((item) => (
                    <li key={item.path}>
                      <Link
                        to={item.path}
                        className="text-sm text-ocean-200 transition-colors hover:text-white"
                      >
                        {item.shortLabel}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-14 flex flex-col gap-4 border-t border-navy-800 pt-6 text-xs text-ocean-400 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {new Date().getFullYear()} OceanWatch. Built for a healthier
            ocean.
          </p>
          <div className="flex items-center gap-5">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
              System concept preview
            </span>
            <a
              href="mailto:hello@oceanwatch.example"
              className="inline-flex items-center gap-1.5 transition-colors hover:text-white"
            >
              <Mail className="h-3.5 w-3.5" />
              Contact
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
