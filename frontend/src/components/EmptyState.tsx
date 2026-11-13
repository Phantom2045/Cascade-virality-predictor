import { CopyBlock } from "./ui/CopyBlock";

interface EmptyStateProps {
  title: string;
  description: string;
  showSetupSteps?: boolean;
}

function FaintTreeIllustration() {
  return (
    <svg
      viewBox="0 0 120 72"
      className="h-16 w-28 text-accent opacity-60"
      aria-hidden="true"
      fill="none"
    >
      <path
        d="M60 12L34 36M60 12L86 36M34 36L20 60M34 36L48 60M86 36L72 60M86 36L100 60"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="1.5"
        strokeDasharray="3 3"
      />
      <circle cx="60" cy="12" r="5" fill="#22D3EE" fillOpacity="0.35" stroke="#22D3EE" strokeWidth="1.5" />
      <circle cx="34" cy="36" r="4" fill="#4F8CFF" fillOpacity="0.3" stroke="#4F8CFF" strokeWidth="1.5" />
      <circle cx="86" cy="36" r="4" fill="#4F8CFF" fillOpacity="0.3" stroke="#4F8CFF" strokeWidth="1.5" />
      <circle cx="20" cy="60" r="3" fill="#38BDF8" fillOpacity="0.4" />
      <circle cx="48" cy="60" r="3" fill="#38BDF8" fillOpacity="0.4" />
      <circle cx="72" cy="60" r="3" fill="#F59E0B" fillOpacity="0.45" />
      <circle cx="100" cy="60" r="3" fill="#38BDF8" fillOpacity="0.4" />
    </svg>
  );
}

export function EmptyState({
  title,
  description,
  showSetupSteps = true,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      className="panel-surface flex flex-col items-center gap-4 p-6 text-center"
    >
      <FaintTreeIllustration />
      <div className="max-w-md space-y-1.5">
        <h2 className="font-display text-base font-semibold tracking-tight text-text-1">
          {title}
        </h2>
        <p className="text-xs leading-relaxed text-text-2">{description}</p>
      </div>

      {showSetupSteps && (
        <div className="w-full max-w-lg space-y-3 text-left">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-3">
            Real-data setup (no synthetic fallback)
          </p>
          <p className="text-xs text-text-2">
            Place a supported public propagation dataset under{" "}
            <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono text-[11px] text-accent-2">
              backend/data/raw/&lt;dataset&gt;/
            </code>{" "}
            and run training:
          </p>
          <CopyBlock
            label="Backend PowerShell"
            code="python -m app.ml.train --dataset twitter15"
          />
        </div>
      )}
    </div>
  );
}
