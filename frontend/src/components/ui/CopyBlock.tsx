import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

interface CopyBlockProps {
  code: string;
  label?: string;
  className?: string;
}

export function CopyBlock({ code, label, className }: CopyBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      className={cn(
        "rounded-xl border border-subtle bg-bg-0/90 p-3 text-left",
        className
      )}
    >
      {label && (
        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-3">
          {label}
        </p>
      )}
      <div className="flex items-center justify-between gap-3">
        <pre className="overflow-x-auto font-mono text-xs text-accent-2">
          <code>{code}</code>
        </pre>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          aria-label={copied ? "Copied command" : "Copy command"}
          className="shrink-0"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-success" strokeWidth={1.75} aria-hidden="true" />
              <span className="text-success">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
              <span>Copy</span>
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
