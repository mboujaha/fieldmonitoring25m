"use client";

import { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card(props: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={cn(
        "rounded-xl border border-[var(--line)] bg-[var(--surface-0)]/92 p-4 shadow-[0_1px_0_rgba(139,190,255,0.10),0_14px_24px_rgba(0,0,0,0.32)]",
        props.className,
      )}
    />
  );
}

export function CardTitle(props: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 {...props} className={cn("text-sm font-semibold tracking-wide text-[var(--ink-800)]", props.className)} />
  );
}

export function CardHint(props: HTMLAttributes<HTMLParagraphElement>) {
  return <p {...props} className={cn("text-xs text-[var(--ink-600)]", props.className)} />;
}
