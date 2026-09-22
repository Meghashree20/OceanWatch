import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type BadgeVariant = 'cyan' | 'teal' | 'navy' | 'success' | 'warning' | 'error' | 'neutral';

const variantClasses: Record<BadgeVariant, string> = {
  cyan: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  teal: 'bg-teal-100 text-teal-800 border-teal-200',
  navy: 'bg-navy-100 text-navy-800 border-navy-200',
  success: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  warning: 'bg-amber-100 text-amber-800 border-amber-200',
  error: 'bg-red-100 text-red-800 border-red-200',
  neutral: 'bg-ocean-100 text-ocean-700 border-ocean-200',
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
  icon?: ReactNode;
}

export function Badge({ variant = 'cyan', children, className, icon }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
        variantClasses[variant],
        className
      )}
    >
      {icon}
      {children}
    </span>
  );
}
