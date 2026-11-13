import { cn } from "../../lib/cn";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn("skeleton-shimmer rounded-lg bg-bg-2", className)}
    />
  );
}

export function AnalyzePanelSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading panel">
      <div className="panel-surface p-5 space-y-4">
        <div className="flex justify-between">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
        <Skeleton className="mx-auto h-32 w-48 rounded-2xl" />
        <Skeleton className="mx-auto h-6 w-36 rounded-full" />
      </div>
      <div className="panel-surface p-5 space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-5/6" />
        <Skeleton className="h-6 w-4/6" />
      </div>
    </div>
  );
}

export function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading evaluation report">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="panel-surface p-4 space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Skeleton className="h-72 rounded-panel lg:col-span-6" />
        <Skeleton className="h-72 rounded-panel lg:col-span-6" />
      </div>
    </div>
  );
}
