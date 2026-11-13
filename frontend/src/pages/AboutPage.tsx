import {
  Activity,
  BookOpen,
  Database,
  EyeOff,
  GitBranch,
  Lock,
  Scale,
  ShieldAlert,
  TrendingDown,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Chip } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { cn } from "../lib/cn";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "method", label: "Problem & Method" },
  { id: "data-sources", label: "Data Sources & Licenses" },
  { id: "limitations", label: "Honest Limitations" },
  { id: "ethics", label: "Ethics & Docs" },
] as const;

const PIPELINE_STEPS = [
  "Edge list",
  "Early graph",
  "Features",
  "Model",
  "Probability",
];

function PipelineDiagram() {
  return (
    <div className="overflow-x-auto rounded-xl border border-subtle bg-bg-0/80 p-4">
      <svg
        viewBox="0 0 660 68"
        className="h-16 w-full min-w-[520px]"
        role="img"
        aria-label="Prediction pipeline: Edge list to Early graph to Features to Model to Probability"
      >
        {PIPELINE_STEPS.map((label, idx) => {
          const x = 8 + idx * 134;
          return (
            <g key={label}>
              <rect
                x={x}
                y={14}
                width={106}
                height={38}
                rx={19}
                fill="#121C33"
                stroke={idx === 4 ? "#F59E0B" : idx === 1 ? "#22D3EE" : "rgba(79,140,255,0.45)"}
                strokeWidth={1.25}
              />
              <text
                x={x + 53}
                y={37}
                textAnchor="middle"
                fill="#E6EBFF"
                style={{ fontSize: "11px", fontFamily: "JetBrains Mono Variable" }}
              >
                {label}
              </text>
              {idx < PIPELINE_STEPS.length - 1 && (
                <path
                  d={`M ${x + 110} 33 L ${x + 128} 33 M ${x + 123} 28 L ${x + 129} 33 L ${x + 123} 38`}
                  fill="none"
                  stroke="#4F8CFF"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function AboutPage() {
  const [activeId, setActiveId] = useState<string>("overview");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0.1 }
    );

    for (const sec of SECTIONS) {
      const el = document.getElementById(sec.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  const limitationCards = [
    {
      icon: Database,
      title: "Dataset-bounded evidence",
      body: "Results apply only to the specific public dataset and time period trained on; no cross-platform generalization is claimed.",
    },
    {
      icon: EyeOff,
      title: "Unobserved private channels",
      body: "Direct messages and closed messaging apps (WhatsApp, Telegram) are invisible in public propagation trees.",
    },
    {
      icon: Activity,
      title: "Structure-only ceiling",
      body: "Excluding tweet text, media, seed-account follower counts, and external amplification imposes a natural accuracy ceiling.",
    },
    {
      icon: ShieldAlert,
      title: "Virality is not truthfulness",
      body: "Fast-spreading true emergencies and verified news score high too. Never describe this system as rumor or fake-news detection.",
    },
    {
      icon: TrendingDown,
      title: "Temporal calibration drift",
      body: "Probability calibration and quantile size thresholds shift as platform interfaces and sharing norms evolve.",
    },
    {
      icon: Lock,
      title: "Dual-use amplification risk",
      body: "Early virality forecasts could guide amplification of misleading hooks if misused outside research diagnostics.",
    },
  ];

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-1 gap-10 lg:grid-cols-[minmax(0,680px)_220px]">
      <div className="space-y-8">
        {/* Hero block */}
        <section id="overview" className="scroll-mt-28 space-y-4">
          <p className="font-mono text-xs uppercase tracking-[0.08em] text-accent-2">
            Observatory Specification
          </p>
          <h2 className="font-display text-3xl font-semibold leading-tight tracking-[-0.02em] text-text-1 sm:text-[40px]">
            Cascade Virality Predictor
          </h2>
          <p className="text-base leading-relaxed text-text-2">
            Predicts whether an early information cascade will reach the upper tail of final reach
            using strictly its early propagation graph topology and edge timestamps.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Chip variant="accent">Inputs: structure + timestamps only</Chip>
            <Chip variant="cyan">Mode: early prediction</Chip>
            <Chip variant="viral">Scope: not a truth detector</Chip>
          </div>
        </section>

        {/* Problem & Method */}
        <section id="method" className="scroll-mt-28 space-y-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-accent-2" strokeWidth={1.5} aria-hidden="true" />
            <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-text-1">
              Problem &amp; Method
            </h3>
          </div>

          <PipelineDiagram />

          <Card className="space-y-3 text-sm leading-relaxed text-text-2">
            <p>
              All cascades are truncated strictly at <code className="font-mono text-accent-2">timestamp &le; T</code>{" "}
              and guarded by <code className="font-mono text-accent-2">assert_no_future_events()</code>.
              Cascades with fewer than 3 early edges are excluded and reported transparently.
            </p>
            <p>
              Primary evaluation uses chronological temporal splitting (70% train / 10% validation /
              20% test) with the virality quantile threshold fit strictly on training sizes. Tuned
              Random Forest models are benchmarked against Logistic Regression, a Prior Dummy, and a
              Naive <code className="font-mono text-accent-2">num_edges</code>-only baseline.
            </p>
          </Card>
        </section>

        {/* Data Sources */}
        <section id="data-sources" className="scroll-mt-28 space-y-4">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-accent-2" strokeWidth={1.5} aria-hidden="true" />
            <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-text-1">
              Real Data Sources &amp; Licenses
            </h3>
          </div>
          <p className="text-sm leading-relaxed text-text-2">
            No synthetic cascade data is ever generated or used as a fallback. Users supply real
            public datasets under their original academic and platform terms:
          </p>
          <div className="space-y-3">
            <Card className="p-4 space-y-1">
              <p className="text-sm font-semibold text-text-1">
                Twitter15 &amp; Twitter16 (Ma et al.)
              </p>
              <p className="text-xs leading-relaxed text-text-2">
                Parent-child propagation trees with minute-level delays. Non-commercial academic
                research; veracity labels and tweet text are strictly ignored.
              </p>
            </Card>
            <Card className="p-4 space-y-1">
              <p className="text-sm font-semibold text-text-1">
                PHEME Conversation Trees (Zubiaga et al.)
              </p>
              <p className="text-xs leading-relaxed text-text-2">
                Reply-to trees (<code className="font-mono text-accent-2">structure.json</code>) with
                UTC timestamps. Annotations licensed under CC-BY 4.0; veracity annotations and text
                excluded.
              </p>
            </Card>
            <Card className="p-4 space-y-1">
              <p className="text-sm font-semibold text-text-1">Canonical Edge CSV</p>
              <p className="text-xs leading-relaxed text-text-2">
                Any real cascade edge list formatted as{" "}
                <code className="font-mono text-accent-2">
                  cascade_id, parent_id, child_id, timestamp
                </code>{" "}
                with opaque node identifiers.
              </p>
            </Card>
          </div>
        </section>

        {/* Honest Limitations */}
        <section id="limitations" className="scroll-mt-28 space-y-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-viral" strokeWidth={1.5} aria-hidden="true" />
            <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-text-1">
              Honest Limitations
            </h3>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {limitationCards.map(({ icon: Icon, title, body }) => (
              <Card key={title} className="p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-accent-2" strokeWidth={1.5} aria-hidden="true" />
                  <h4 className="text-xs font-semibold text-text-1">{title}</h4>
                </div>
                <p className="text-xs leading-relaxed text-text-2">{body}</p>
              </Card>
            ))}
          </div>
        </section>

        {/* Ethics */}
        <section id="ethics" className="scroll-mt-28 space-y-4">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-success" strokeWidth={1.5} aria-hidden="true" />
            <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-text-1">
              Ethics &amp; Documentation
            </h3>
          </div>
          <Card className="space-y-3 text-xs leading-relaxed text-text-2">
            <p>
              User identifiers are treated strictly as opaque graph node IDs with zero
              de-anonymization or user-history enrichment. Outputs are scoped to descriptive
              structural research alongside explicit uncertainty and limitations.
            </p>
            <p className="font-mono text-[11px] text-text-3">
              Docs: README.md · docs/methodology.md · docs/data-sources.md · docs/viva-questions.md
            </p>
          </Card>
        </section>
      </div>

      {/* Sticky Table of Contents on desktop */}
      <aside aria-label="Table of contents" className="hidden lg:block">
        <div className="sticky top-28 space-y-2 border-l border-subtle pl-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-3">
            On this page
          </p>
          <ul className="space-y-1.5 text-xs">
            {SECTIONS.map((sec) => {
              const isActive = activeId === sec.id;
              return (
                <li key={sec.id}>
                  <a
                    href={`#${sec.id}`}
                    className={cn(
                      "block rounded-lg px-2 py-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                      isActive
                        ? "bg-accent/10 font-medium text-accent-2"
                        : "text-text-3 hover:text-text-1"
                    )}
                  >
                    {sec.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>
    </div>
  );
}
