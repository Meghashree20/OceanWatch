import { type HTMLAttributes, type ReactNode, forwardRef } from 'react';
import { cn } from '@/lib/utils';

type CardVariant = 'default' | 'elevated' | 'outline' | 'dark';

const variantClasses: Record<CardVariant, string> = {
  default: 'bg-white border border-ocean-200 shadow-card',
  elevated: 'bg-white border border-ocean-200 shadow-card-hover',
  outline: 'bg-white border border-ocean-300',
  dark: 'bg-navy-900 border border-navy-700 text-white shadow-card',
};

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  children: ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { variant = 'default', className, children, ...props },
  ref
) {
  return (
    <div
      ref={ref}
      className={cn('rounded-2xl transition-all duration-200', variantClasses[variant], className)}
      {...props}
    >
      {children}
    </div>
  );
});

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CardHeader({ className, children, ...props }: CardHeaderProps) {
  return (
    <div className={cn('p-6 pb-0', className)} {...props}>
      {children}
    </div>
  );
}

interface CardBodyProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CardBody({ className, children, ...props }: CardBodyProps) {
  return (
    <div className={cn('p-6', className)} {...props}>
      {children}
    </div>
  );
}

interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CardFooter({ className, children, ...props }: CardFooterProps) {
  return (
    <div className={cn('p-6 pt-0', className)} {...props}>
      {children}
    </div>
  );
}
