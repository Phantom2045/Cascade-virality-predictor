export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const rem = Math.round(seconds % 60);
    return rem > 0 && mins < 10 ? `${mins}m ${rem}s` : `${(seconds / 60).toFixed(1)}m`;
  }
  const hrs = Math.floor(seconds / 3600);
  const remMins = Math.round((seconds % 3600) / 60);
  if (seconds < 86400) {
    return remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`;
  }
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function formatPct(val: number, digits = 1): string {
  return `${(val * 100).toFixed(digits)}%`;
}

export function formatMetric(val: number, digits = 3): string {
  return Number.isFinite(val) ? val.toFixed(digits) : "—";
}

export function formatSecondsClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";
  return `${Math.round(seconds).toLocaleString()}s`;
}
