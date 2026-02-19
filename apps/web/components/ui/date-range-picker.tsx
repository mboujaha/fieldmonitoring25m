"use client";

import { useMemo, useState } from "react";
import { DateRange, DayPicker } from "react-day-picker";
import { format } from "date-fns";
import { CalendarDays } from "lucide-react";
import "react-day-picker/style.css";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface DateRangePickerProps {
  value: DateRange | undefined;
  onChange: (value: DateRange | undefined) => void;
  disabled?: boolean;
  className?: string;
}

function rangeLabel(value: DateRange | undefined): string {
  if (!value?.from && !value?.to) {
    return "Pick date range";
  }
  if (value.from && value.to) {
    return `${format(value.from, "MMM d, yyyy")} - ${format(value.to, "MMM d, yyyy")}`;
  }
  if (value.from) {
    return format(value.from, "MMM d, yyyy");
  }
  return "Pick date range";
}

export function DateRangePicker({ value, onChange, disabled = false, className }: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const label = useMemo(() => rangeLabel(value), [value]);

  return (
    <div className={cn("w-full", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="secondary"
            disabled={disabled}
            className={cn(
              "h-10 w-full justify-start border border-[var(--line)] bg-[var(--surface-1)] text-left font-medium text-[var(--ink-800)] hover:bg-[var(--surface-2)]",
              !value?.from && "text-[var(--ink-500)]",
            )}
          >
            <CalendarDays className="mr-2 h-4 w-4 text-[var(--accent-400)]" />
            <span className="truncate">{label}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[700px] max-w-[calc(100vw-2rem)] p-3">
          <DayPicker
            mode="range"
            selected={value}
            onSelect={(next) => {
              onChange(next);
              if (next?.from && next?.to) {
                setOpen(false);
              }
            }}
            showOutsideDays
            weekStartsOn={1}
            className="rdp-fieldmonitor"
            classNames={{
              months: "flex flex-col gap-3 sm:flex-row",
              month: "space-y-3",
              month_caption: "relative flex h-8 items-center justify-center",
              caption_label: "text-sm font-semibold text-[var(--ink-800)]",
              nav: "flex items-center gap-1",
              button_previous:
                "absolute left-0 inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] transition hover:bg-[var(--surface-2)]",
              button_next:
                "absolute right-0 inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] transition hover:bg-[var(--surface-2)]",
              month_grid: "w-full border-collapse",
              weekdays: "flex",
              weekday:
                "w-9 text-center text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-500)]",
              week: "mt-1 flex w-full",
              day: "h-9 w-9 p-0 text-center text-sm",
              day_button:
                "h-9 w-9 rounded-md font-medium text-[var(--ink-800)] transition hover:bg-[var(--surface-2)]",
              selected:
                "bg-[var(--accent-500)] text-[#04141a] hover:bg-[var(--accent-500)] hover:text-[#04141a]",
              range_start:
                "bg-[var(--accent-500)] text-[#04141a] hover:bg-[var(--accent-500)] hover:text-[#04141a]",
              range_end:
                "bg-[var(--accent-500)] text-[#04141a] hover:bg-[var(--accent-500)] hover:text-[#04141a]",
              range_middle: "bg-[var(--accent-100)] text-[var(--ink-800)]",
              today: "border border-[var(--accent-400)]",
              outside: "text-[var(--ink-500)] opacity-55",
              disabled: "text-[var(--ink-500)] opacity-35",
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
