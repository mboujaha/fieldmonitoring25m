"use client";

import { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "default" | "secondary" | "outline" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  default:
    "bg-[var(--accent-600)] text-[#021216] shadow-[0_0_0_1px_rgba(94,227,218,0.25),0_8px_18px_rgba(6,22,26,0.45)] hover:bg-[var(--accent-500)] disabled:bg-[var(--ink-300)] disabled:text-[var(--ink-600)]",
  secondary:
    "bg-[var(--surface-1)] text-[var(--ink-800)] border border-[var(--line)] hover:border-[var(--line-strong)] hover:bg-[var(--surface-2)]",
  outline:
    "bg-transparent text-[var(--ink-800)] border border-[var(--line-strong)] hover:bg-[var(--surface-2)]",
  ghost: "bg-transparent text-[var(--ink-700)] hover:bg-[var(--surface-2)]",
  danger: "bg-[var(--danger-500)] text-[var(--ink-900)] hover:bg-[var(--danger-600)]",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
};

export function Button({ className, variant = "default", size = "md", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition duration-200 ease-out disabled:cursor-not-allowed",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  );
}
