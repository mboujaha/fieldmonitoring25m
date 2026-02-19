"use client";

import { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "h-10 w-full rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 text-sm text-[var(--ink-800)] outline-none transition placeholder:text-[var(--ink-500)] focus:border-[var(--accent-400)] focus:ring-2 focus:ring-[var(--accent-200)]",
        props.className,
      )}
    />
  );
}
