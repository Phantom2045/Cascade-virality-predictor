import { AlertTriangle, CheckCircle2, FileUp, Wrench } from "lucide-react";
import { useRef, useState } from "react";
import type { ValidationReport } from "../api/client";
import { cn } from "../lib/cn";
import { Button } from "./ui/Button";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
  validationReport: ValidationReport | null;
  isLoading: boolean;
}

export function UploadZone({
  onFileSelected,
  validationReport,
  isLoading,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      onFileSelected(file);
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "rounded-xl border border-dashed p-4 text-center transition-all duration-150",
          dragActive
            ? "scale-[1.01] border-accent bg-accent/10"
            : "border-subtle bg-bg-0/60 hover:border-accent/45"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          aria-label="Upload canonical cascade CSV"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <FileUp className="mx-auto h-5 w-5 text-accent-2" strokeWidth={1.5} aria-hidden="true" />
        <p className="mt-2 text-xs leading-relaxed text-text-2">
          Drop UTF-8 <span className="font-mono text-text-1">.csv</span> with{" "}
          <code className="font-mono text-[11px] text-accent-2">
            cascade_id, parent_id, child_id, timestamp
          </code>
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={isLoading}
          onClick={() => inputRef.current?.click()}
          className="mt-3"
        >
          {isLoading ? "Processing CSV..." : "Choose CSV File"}
        </Button>
      </div>

      {validationReport && (
        <div
          aria-label="CSV validation report"
          className="rounded-xl border border-subtle bg-bg-0/80 p-3 text-xs space-y-2"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 font-medium text-text-1">
              {validationReport.is_valid ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-success" strokeWidth={1.5} aria-hidden="true" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-danger" strokeWidth={1.5} aria-hidden="true" />
              )}
              Validation Report
            </span>
            <span className="font-mono text-[11px] text-text-3 tabular-nums">
              {validationReport.valid_edges} edges · {validationReport.cascades_count} cascade(s)
            </span>
          </div>

          <ul className="space-y-1 text-[11px] text-text-2">
            <li className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3 w-3 shrink-0 text-success" strokeWidth={1.5} aria-hidden="true" />
              <span>
                Read <span className="font-mono">{validationReport.total_rows}</span> rows ·{" "}
                <span className="font-mono">{validationReport.valid_edges}</span> valid edges
              </span>
            </li>
            {(validationReport.actions_taken ?? []).map((act, idx) => (
              <li key={`act-${idx}`} className="flex items-start gap-1.5 text-text-2">
                <Wrench className="mt-0.5 h-3 w-3 shrink-0 text-accent" strokeWidth={1.5} aria-hidden="true" />
                <span>{act}</span>
              </li>
            ))}
            {(validationReport.warnings ?? []).map((w, idx) => (
              <li key={`warn-${idx}`} className="flex items-start gap-1.5 text-viral">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-viral" strokeWidth={1.5} aria-hidden="true" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
