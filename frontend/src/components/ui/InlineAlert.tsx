import { AlertCircle, Info, RotateCw } from "lucide-react";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

interface InlineAlertProps {
  tone?: "error" | "info" | "warning";
  code?: string;
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function InlineAlert({
  tone = "error",
  code,
  title,
  message,
  onRetry,
  className,
}: InlineAlertProps) {
  const Icon = tone === "info" ? Info : AlertCircle;
  const toneStyles =
    tone === "error"
      ? "border-danger/35 bg-danger/10 text-text-1"
      : tone === "warning"
        ? "border-viral/35 bg-viral/10 text-text-1"
        : "border-accent/30 bg-bg-2/80 text-text-2";
  const iconColor =
    tone === "error" ? "text-danger" : tone === "warning" ? "text-viral" : "text-accent-2";

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start justify-between gap-3 rounded-xl border p-4 text-sm",
        toneStyles,
        className
      )}
    >
      <div className="flex items-start gap-3">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconColor)} strokeWidth={1.5} aria-hidden="true" />
        <div className="space-y-1">
          {(code || title) && (
            <div className="flex flex-wrap items-center gap-2">
              {code && (
                <span className="rounded bg-bg-0/80 px-1.5 py-0.5 font-mono text-[11px] font-medium text-text-2">
                  {code}
                </span>
              )}
              {title && <span className="text-xs font-semibold text-text-1">{title}</span>}
            </div>
          )}
          <p className="text-xs leading-relaxed text-text-2">{message}</p>
        </div>
      </div>

      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry} className="shrink-0">
          <RotateCw className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  );
}
