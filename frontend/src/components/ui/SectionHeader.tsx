import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type Align = 'left' | 'center';

interface SectionHeaderProps {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  align?: Align;
  className?: string;
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  align = 'left',
  className,
}: SectionHeaderProps) {
  return (
    <div
      className={cn(
        'max-w-3xl',
        align === 'center' && 'mx-auto text-center',
        className
      )}
    >
      {eyebrow && (
        <div
          className={cn(
            'mb-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-600',
            align === 'center' && 'justify-center'
          )}
        >
          <span className="h-px w-6 bg-cyan-400" />
          {eyebrow}
        </div>
      )}
      <h2 className="text-3xl font-bold text-navy-950 sm:text-4xl text-balance">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-lg leading-relaxed text-ocean-600 text-balance">
          {description}
        </p>
      )}
    </div>
  );
}
