import { useId, type ReactNode } from "react";
import { cn } from "../lib/cn";
import { Card, CardHeader, CardTitle } from "./ui/Card";

interface ChartFrameProps {
  title: string;
  subtitle?: string;
  summary: string;
  headerRight?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ChartFrame({
  title,
  subtitle,
  summary,
  headerRight,
  children,
  className,
}: ChartFrameProps) {
  const summaryId = useId();

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="mb-2">
        <div>
          <CardTitle>{title}</CardTitle>
          {subtitle && <p className="mt-1 text-xs text-text-3">{subtitle}</p>}
        </div>
        {headerRight}
      </CardHeader>

      <p id={summaryId} className="sr-only">
        {summary}
      </p>

      <div aria-describedby={summaryId} className="w-full flex-1">
        {children}
      </div>
    </Card>
  );
}
