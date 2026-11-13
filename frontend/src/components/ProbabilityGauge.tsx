import { useEffect, useId, useState } from "react";
import { Badge } from "./ui/Badge";

interface ProbabilityGaugeProps {
  probability: number;
  threshold: number;
  predictedViral: boolean;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

export function ProbabilityGauge({
  probability,
  threshold,
  predictedViral,
}: ProbabilityGaugeProps) {
  const gradId = useId();
  const clamped = Math.max(0, Math.min(1, probability));
  const [displayProb, setDisplayProb] = useState(clamped);

  useEffect(() => {
    const prefersReduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) {
      setDisplayProb(clamped);
      return;
    }

    let rafId = 0;
    const duration = 600;
    const startVal = 0;
    const startTime = performance.now();

    const step = (now: number) => {
      const t = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayProb(startVal + (clamped - startVal) * eased);
      if (t < 1) {
        rafId = requestAnimationFrame(step);
      }
    };

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [clamped]);

  // 240-degree sweep: -120° to +120°
  const startDeg = -120;
  const sweepDeg = 240;
  const endDeg = startDeg + sweepDeg;
  const activeEndDeg = startDeg + sweepDeg * Math.max(0.005, displayProb);
  const thresholdDeg = startDeg + sweepDeg * Math.max(0, Math.min(1, threshold));

  const cx = 100;
  const cy = 92;
  const r = 68;

  const trackPath = describeArc(cx, cy, r, startDeg, endDeg);
  const valuePath = describeArc(cx, cy, r, startDeg, activeEndDeg);
  const tickInner = polarToCartesian(cx, cy, r - 9, thresholdDeg);
  const tickOuter = polarToCartesian(cx, cy, r + 9, thresholdDeg);

  return (
    <div className="flex flex-col items-center">
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped * 100)}
        aria-label={`Virality probability ${(clamped * 100).toFixed(1)} percent`}
      >
        <svg viewBox="0 0 200 148" className="h-40 w-52" aria-hidden="true">
          <defs>
            <linearGradient id={gradId} x1="0%" y1="50%" x2="100%" y2="50%">
              <stop offset="0%" stopColor="#38BDF8" />
              <stop offset="55%" stopColor="#4F8CFF" />
              <stop offset="100%" stopColor="#F59E0B" />
            </linearGradient>
          </defs>

          <path
            d={trackPath}
            fill="none"
            stroke="#121C33"
            strokeWidth="14"
            strokeLinecap="round"
          />

          <path
            d={valuePath}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth="14"
            strokeLinecap="round"
          />

          <line
            x1={tickInner.x}
            y1={tickInner.y}
            x2={tickOuter.x}
            y2={tickOuter.y}
            stroke="#E6EBFF"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          <text
            x={cx}
            y="88"
            textAnchor="middle"
            className="fill-text-1 font-display font-semibold tabular-nums"
            style={{ fontSize: "30px" }}
          >
            {(displayProb * 100).toFixed(1)}%
          </text>
          <text
            x={cx}
            y="108"
            textAnchor="middle"
            className="fill-text-3 font-mono"
            style={{ fontSize: "11px" }}
          >
            Threshold {(threshold * 100).toFixed(0)}%
          </text>
        </svg>
      </div>

      <Badge variant={predictedViral ? "viral" : "calm"} className="-mt-1 px-3 py-1 text-xs">
        <span
          aria-hidden="true"
          className={`h-2 w-2 rounded-full ${predictedViral ? "bg-viral" : "bg-calm"}`}
        />
        {predictedViral ? "Highly viral" : "Not highly viral"}
      </Badge>
    </div>
  );
}
