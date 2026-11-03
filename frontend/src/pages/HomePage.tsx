import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Compass,
  Eye,
  Leaf,
  Waves,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';

export function HomePage() {
  return (
    <main>
      <HeroSection />
      <AboutSection />
      <MissionSection />
      <WhySection />
      <FinalCtaSection />
    </main>
  );
}

function HeroSection() {
  return (
    <section className="relative isolate min-h-[min(760px,calc(100vh-4rem))] overflow-hidden bg-navy-950 text-white">
      <img
        src="https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=2200&q=85"
        alt=""
        className="absolute inset-0 -z-20 h-full w-full object-cover opacity-45"
      />
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-navy-950 via-navy-950/85 to-navy-950/20" />
      <div className="absolute inset-0 -z-10 bg-gradient-to-t from-navy-950 via-transparent to-navy-950/30" />
      <div className="absolute inset-0 -z-10 grid-pattern opacity-[0.08]" />

      <div className="container-page flex min-h-[min(760px,calc(100vh-4rem))] items-center py-24 lg:py-32">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200 backdrop-blur-sm">
            <Waves className="h-4 w-4" />
            Ocean intelligence, made actionable
          </div>
          <h1 className="mt-8 max-w-3xl text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
            See the ocean clearly.{' '}
            <span className="text-cyan-300">Act with confidence.</span>
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-relaxed text-ocean-100 sm:text-xl">
            OceanWatch brings the signals of a changing ocean into one clear,
            decision-ready workspace for the people working to protect it.
          </p>
          <div className="mt-10 flex flex-col gap-3 sm:flex-row">
            <Button to="/signup" size="lg">
              Get started
              <ArrowUpRight className="h-4 w-4" />
            </Button>
            <Button
              to="/login"
              variant="outline"
              size="lg"
              className="border-white/30 bg-white/10 text-white hover:border-cyan-300 hover:bg-white/20 hover:text-white"
            >
              Sign in
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-8 text-sm text-ocean-200">
            Built for clearer decisions and healthier coastlines.
          </p>
        </div>
      </div>
    </section>
  );
}

function AboutSection() {
  return (
    <section className="bg-white py-24 lg:py-32">
      <div className="container-page grid items-center gap-14 lg:grid-cols-[0.85fr_1.15fr] lg:gap-24">
        <div className="relative overflow-hidden rounded-3xl bg-ocean-100 p-8 sm:p-12">
          <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-300/30 blur-2xl" />
          <div className="relative">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-950 text-cyan-300 shadow-glow">
              <Eye className="h-7 w-7" />
            </div>
            <p className="mt-20 max-w-xs text-3xl font-bold leading-tight text-navy-950">
              A clearer view of what is happening at sea.
            </p>
            <div className="mt-10 h-px bg-ocean-300" />
            <p className="mt-4 text-sm leading-relaxed text-ocean-700">
              From scattered observations to a shared picture your team can act on.
            </p>
          </div>
        </div>
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-600">
            About OceanWatch
          </p>
          <h2 className="mt-4 text-4xl font-bold leading-tight text-navy-950 sm:text-5xl">
            Environmental intelligence for the decisions that matter.
          </h2>
          <p className="mt-6 text-lg leading-relaxed text-ocean-600">
            OceanWatch helps environmental teams understand marine pollution
            with less noise and more context. It connects the information
            behind a changing coastline to the decisions that shape its future.
          </p>
          <p className="mt-5 text-base leading-relaxed text-ocean-600">
            The result is a focused workspace for exploring conditions,
            spotting change, and moving from awareness to meaningful action.
          </p>
        </div>
      </div>
    </section>
  );
}

function MissionSection() {
  return (
    <section className="relative overflow-hidden bg-ocean-50 py-24 lg:py-32">
      <div className="absolute right-0 top-0 h-full w-1/3 bg-gradient-to-l from-cyan-100/40 to-transparent" />
      <div className="container-page relative grid gap-12 lg:grid-cols-[1fr_1fr] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-600">
            Our mission
          </p>
          <h2 className="mt-4 max-w-xl text-4xl font-bold leading-tight text-navy-950 sm:text-5xl">
            Make ocean protection more informed, connected, and possible.
          </h2>
        </div>
        <div className="max-w-xl lg:pb-2">
          <p className="text-lg leading-relaxed text-ocean-700">
            We believe the people caring for our oceans deserve tools that
            respect the complexity of the environment without making action
            feel complicated.
          </p>
          <p className="mt-5 text-lg leading-relaxed text-ocean-700">
            OceanWatch exists to turn better understanding into better choices
            for communities, coastlines, and the life they sustain.
          </p>
        </div>
      </div>
    </section>
  );
}

function WhySection() {
  const points = [
    {
      icon: Compass,
      title: 'Find the signal',
      description: 'Bring the most important changes into focus instead of searching through disconnected information.',
    },
    {
      icon: CheckCircle2,
      title: 'Move with clarity',
      description: 'Give teams a shared, intuitive view that helps them decide what deserves attention next.',
    },
    {
      icon: Leaf,
      title: 'Protect what matters',
      description: 'Support practical environmental work with insight designed for real-world impact.',
    },
  ];

  return (
    <section className="bg-white py-24 lg:py-32">
      <div className="container-page">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-600">
            Why OceanWatch
          </p>
          <h2 className="mt-4 text-4xl font-bold leading-tight text-navy-950 sm:text-5xl">
            Better visibility creates better environmental decisions.
          </h2>
        </div>
        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {points.map(({ icon: Icon, title, description }) => (
            <div key={title} className="rounded-2xl border border-ocean-200 bg-ocean-50/60 p-7 transition-transform duration-300 hover:-translate-y-1">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-100 text-cyan-700">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-7 text-xl font-bold text-navy-950">{title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ocean-600">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCtaSection() {
  return (
    <section className="relative overflow-hidden bg-navy-950 py-24 text-white lg:py-32">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(34,211,238,0.2),transparent_35%)]" />
      <div className="container-page relative text-center">
        <Waves className="mx-auto h-8 w-8 text-cyan-300" />
        <h2 className="mx-auto mt-6 max-w-2xl text-4xl font-bold leading-tight sm:text-5xl">
          Ready to see the ocean differently?
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-lg text-ocean-200">
          Step into a clearer way to understand marine conditions and support
          the work of protecting them.
        </p>
        <div className="mt-9">
          <Button to="/signup" size="lg">
            Access OceanWatch
            <ArrowUpRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </section>
  );
}
