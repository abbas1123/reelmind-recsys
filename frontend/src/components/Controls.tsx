import { ToggleButton, ToggleButtonGroup } from "@heroui/react";
import type { ReactNode } from "react";

interface Option<T extends string> {
  value: T;
  label: ReactNode;
  disabled?: boolean;
  testId?: string;
}

/** Pill segmented control built on HeroUI's accessible ToggleButtonGroup. */
export function Segmented<T extends string>({ label, value, onChange, options, size = "md" }: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: Option<T>[];
  size?: "sm" | "md";
}) {
  return (
    <ToggleButtonGroup
      aria-label={label}
      selectionMode="single"
      disallowEmptySelection
      selectedKeys={new Set([value])}
      onSelectionChange={(keys) => onChange([...keys][0] as T)}
      className="inline-flex max-w-full gap-1 overflow-x-auto rounded-full bg-surface-2 p-1 shadow-none ring-1 ring-line [scrollbar-width:none]"
    >
      {options.map((o) => (
        <ToggleButton
          key={o.value}
          id={o.value}
          isDisabled={o.disabled}
          data-testid={o.testId}
          className={`${size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm"} shrink-0 gap-1.5 rounded-full border-0 bg-transparent font-semibold text-text-2 shadow-none hover:bg-white/5 hover:text-text data-[selected]:bg-white data-[selected]:text-black data-[disabled]:opacity-40`}
        >
          {o.label}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

/** Horizontal, scrollable chip filters (e.g. genres). */
export function FilterList({ label, value, onChange, options, allLabel = "All" }: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  options: { name: string; count?: number }[];
  allLabel?: string;
}) {
  const items = [{ name: null as string | null, count: undefined as number | undefined }, ...options];
  return (
    <div className="scroll-row -mx-4 flex gap-2 overflow-x-auto px-4 sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10" role="group" aria-label={label}>
      {items.map(({ name, count }) => {
        const active = value === name;
        return (
          <button
            key={name ?? "__all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(name)}
            className={`shrink-0 rounded-full px-4 py-1.5 text-sm font-semibold outline-none transition focus-visible:ring-2 focus-visible:ring-brand ${
              active ? "bg-white text-black" : "bg-surface-2 text-text-2 ring-1 ring-line hover:bg-surface-3 hover:text-text"
            }`}
          >
            {name ?? allLabel}
            {count !== undefined && <span className={`ml-1.5 text-xs font-medium ${active ? "text-black/55" : "text-text-3"}`}>{count}</span>}
          </button>
        );
      })}
    </div>
  );
}
