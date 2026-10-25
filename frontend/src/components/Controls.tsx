import { ToggleButton, ToggleButtonGroup } from "@heroui/react";

interface Option<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
  testId?: string;
}

/** Hairline segmented control built on HeroUI's accessible ToggleButtonGroup. */
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
      className="inline-flex gap-0 rounded-[3px] border border-rule-strong bg-transparent p-0 shadow-none"
    >
      {options.map((o) => (
        <ToggleButton
          key={o.value}
          id={o.value}
          isDisabled={o.disabled}
          data-testid={o.testId}
          className={`${size === "sm" ? "h-7 px-2.5 text-[11.5px]" : "h-9 px-3.5 text-[12.5px]"} rounded-none border-0 border-r border-rule-strong bg-transparent font-medium text-paper-3 shadow-none last:border-r-0 hover:bg-transparent hover:text-paper data-[selected]:bg-paper data-[selected]:text-ink data-[disabled]:opacity-40`}
        >
          {o.label}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

/** Horizontal, scrollable list of text filters (e.g. genres). */
export function FilterList({ label, value, onChange, options, allLabel = "All" }: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  options: { name: string; count?: number }[];
  allLabel?: string;
}) {
  const items = [{ name: null as string | null, count: undefined as number | undefined }, ...options];
  return (
    <div className="scroll-row -mx-5 flex gap-1 overflow-x-auto px-5 sm:-mx-8 sm:px-8" role="group" aria-label={label}>
      {items.map(({ name, count }) => {
        const active = value === name;
        return (
          <button
            key={name ?? "__all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(name)}
            className={`shrink-0 rounded-[3px] border px-2.5 py-1 text-[12.5px] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-amber ${
              active ? "border-paper bg-paper text-ink" : "border-rule text-paper-2 hover:border-rule-strong hover:text-paper"
            }`}
          >
            {name ?? allLabel}
            {count !== undefined && <span className={`ml-1.5 font-mono text-[10px] ${active ? "text-ink/60" : "text-paper-3"}`}>{count}</span>}
          </button>
        );
      })}
    </div>
  );
}
