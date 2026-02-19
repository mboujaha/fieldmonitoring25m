"use client";

import { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "soft" | "success" | "warn" | "danger";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variants: Record<BadgeVariant, string> = {
  default: "bg-[var(--ink-800)] text-[#04101c]",
  soft: "bg-[var(--surface-2)] text-[var(--ink-700)] border border-[var(--line)]",
  success: "bg-[var(--success-100)] text-[var(--success-700)] border border-[var(--success-200)]",
  warn: "bg-[var(--warn-100)] text-[var(--warn-700)] border border-[var(--warn-200)]",
  danger: "bg-[var(--danger-100)] text-[var(--danger-700)] border border-[var(--danger-200)]",
};

export function Badge({ variant = "soft", className, ...props }: BadgeProps) {
  return (
    <span
      {...props}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
        variants[variant],
        className,
      )}
    />
  );
}
