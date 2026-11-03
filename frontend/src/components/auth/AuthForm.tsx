import { Eye, EyeOff, LoaderCircle, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-ocean-50">
      <div className="absolute inset-0 grid-pattern opacity-60" />
      <div className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-cyan-200/30 blur-3xl" />
      <div className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-teal-200/30 blur-3xl" />
      <div className="container-page relative flex min-h-[calc(100vh-4rem)] items-center justify-center py-12">
        <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-ocean-200 bg-white shadow-card-hover lg:grid-cols-[0.85fr_1.15fr]">
          <div className="hidden flex-col justify-between bg-navy-950 p-10 text-white lg:flex">
            <div>
              <div className="flex items-center gap-2 text-cyan-300">
                <Waves className="h-6 w-6" />
                <span className="font-display text-xl font-bold">OceanWatch</span>
              </div>
              <p className="mt-16 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">
                Marine intelligence
              </p>
              <h2 className="mt-4 text-4xl font-bold leading-tight">
                See the ocean clearly. Act with confidence.
              </h2>
            </div>
            <p className="max-w-xs text-sm leading-relaxed text-ocean-200">
              Access validated observations, spatial analysis, forecasts, and cleanup intelligence in one workspace.
            </p>
          </div>
          <div className="p-6 sm:p-10">
            <div className="mb-8 lg:hidden">
              <Link to="/" className="inline-flex items-center gap-2 font-display text-xl font-bold text-navy-950">
                <Waves className="h-6 w-6 text-cyan-500" />
                Ocean<span className="text-cyan-500">Watch</span>
              </Link>
            </div>
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-600">OceanWatch account</p>
            <h1 className="mt-3 text-3xl font-bold text-navy-950">{title}</h1>
            <p className="mt-3 text-sm leading-relaxed text-ocean-600">{description}</p>
            <div className="mt-8">{children}</div>
            <div className="mt-6 border-t border-ocean-100 pt-5 text-center text-sm text-ocean-600">{footer}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AuthInput({
  label,
  error,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-navy-900">{label}</span>
      <input
        {...props}
        className={cn(
          'w-full rounded-xl border bg-white px-4 py-3 text-sm text-navy-950 shadow-sm transition focus:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-100',
          error ? 'border-red-300' : 'border-ocean-200',
          props.className,
        )}
      />
      {error && <span className="mt-1.5 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

export function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const [visible, setVisible] = useState(false);
  const { label, error, ...inputProps } = props;
  return (
    <div className="relative">
      <AuthInput {...inputProps} label={label} error={error} type={visible ? 'text' : 'password'} className="pr-12" />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute right-3 top-9 rounded-lg p-1.5 text-ocean-500 hover:bg-ocean-100 hover:text-navy-800"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export function SubmitButton({ loading, children }: { loading: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-5 py-3.5 text-sm font-bold text-navy-950 transition hover:bg-cyan-400 disabled:pointer-events-none disabled:opacity-60"
    >
      {loading && <LoaderCircle className="h-4 w-4 animate-spin" />}
      {loading ? 'Please wait…' : children}
    </button>
  );
}
