import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

interface StatTileProps {
  label: string;
  value: string;
  sublabel?: string;
  delta?: string;
  deltaTone?: "positive" | "negative" | "neutral";
  accent?: "default" | "accent" | "cyan" | "viral" | "calm" | "success";
  compact?: boolean;
  sparkline?: ReactNode;
  className?: string;
}

const valueColorMap: Record<NonNullable<StatTileProps["accent"]>, string> = {
  default: "text-text-1",
  accent: "text-[#93B8FF]",
  cyan: "text-accent-2",
  viral: "text-viral",
  calm: "text-calm",
  success: "text-success",
};

export function StatTile({
  label,
  value,
  sublabel,
  delta,
  deltaTone = "neutral",
  accent = "default",
  compact = false,
  sparkline,
  className,
}: StatTileProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-subtle bg-bg-2/70",
        compact ? "p-3" : "panel-surface p-4",
        className
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-2">
          {label}
        </p>
        {delta && (
          <span
            className={cn(
              "font-mono text-[11px] tabular-nums",
              deltaTone === "positive"
                ? "text-success"
                : deltaTone === "negative"
                  ? "text-viral"
                  : "text-text-3"
            )}
          >
            {delta}
          </span>
        )}
      </div>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <p
          className={cn(
            "font-mono font-semibold tabular-nums tracking-tight",
            compact ? "text-xl" : "text-[26px] leading-tight",
            valueColorMap[accent]
          )}
        >
          {value}
        </p>
        {sparkline}
      </div>
      {sublabel && <p className="mt-1 text-xs text-text-3">{sublabel}</p>}
    </div>
  );
}
