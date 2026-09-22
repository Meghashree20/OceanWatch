import { type ButtonHTMLAttributes, type ReactNode, forwardRef } from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { cn } from '@/lib/utils';

type Variant = 'primary' | 'secondary' | 'ghost' | 'outline';
type Size = 'sm' | 'md' | 'lg';

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-cyan-500 text-navy-950 hover:bg-cyan-400 active:bg-cyan-600 shadow-sm font-semibold',
  secondary:
    'bg-navy-800 text-white hover:bg-navy-700 active:bg-navy-900 shadow-sm font-semibold',
  ghost:
    'text-navy-700 hover:bg-ocean-100 active:bg-ocean-200 font-medium',
  outline:
    'border border-ocean-300 text-navy-800 hover:border-cyan-400 hover:text-cyan-700 active:bg-ocean-100 font-semibold bg-white/60 backdrop-blur-sm',
};

const sizeClasses: Record<Size, string> = {
  sm: 'px-3.5 py-2 text-sm rounded-lg gap-1.5',
  md: 'px-5 py-2.5 text-sm rounded-lg gap-2',
  lg: 'px-7 py-3.5 text-base rounded-xl gap-2.5',
};

const baseClasses =
  'inline-flex items-center justify-center transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-ocean-50 disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap';

interface ButtonBaseProps {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  className?: string;
}

type ButtonAsButton = ButtonBaseProps &
  ButtonHTMLAttributes<HTMLButtonElement> & { to?: undefined };

type ButtonAsLink = ButtonBaseProps &
  Omit<LinkProps, 'to'> & { to: string };

export type ButtonProps = ButtonAsButton | ButtonAsLink;

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
  function Button({ variant = 'primary', size = 'md', className, children, ...props }, ref) {
    const classes = cn(baseClasses, variantClasses[variant], sizeClasses[size], className);

    if ('to' in props && props.to !== undefined) {
      const { to, ...linkProps } = props as ButtonAsLink;
      return (
        <Link ref={ref as React.Ref<HTMLAnchorElement>} to={to} className={classes} {...linkProps}>
          {children}
        </Link>
      );
    }

    const buttonProps = props as ButtonHTMLAttributes<HTMLButtonElement>;
    return (
      <button ref={ref as React.Ref<HTMLButtonElement>} className={classes} {...buttonProps}>
        {children}
      </button>
    );
  }
);
