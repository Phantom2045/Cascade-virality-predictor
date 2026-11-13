import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium leading-tight border",
  {
    variants: {
      variant: {
        neutral: "bg-bg-2 text-text-2 border-subtle",
        accent: "bg-accent/15 text-[#93B8FF] border-accent/30",
        cyan: "bg-accent-2/15 text-accent-2 border-accent-2/30",
        viral: "bg-viral/15 text-[#FBBF24] border-viral/35",
        calm: "bg-calm/15 text-calm border-calm/35",
        success: "bg-success/15 text-success border-success/35",
        danger: "bg-danger/15 text-danger border-danger/35",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function Chip({ className, variant = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        badgeVariants({ variant }),
        "rounded-lg px-2.5 py-1 font-mono text-[11px]",
        className
      )}
      {...props}
    />
  );
}
