import { useState } from "react";

/** Five whole-star rating (MovieLens 1M uses integers 1–5). Accessible as a radio group. */
export function RatingStars({ value, onChange, size = "md", label = "Your rating" }: {
  value: number | null;
  onChange?: (v: number) => void;
  size?: "sm" | "md";
  label?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = hover ?? value ?? 0;
  const px = size === "sm" ? 14 : 20;
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex items-center gap-0.5" onMouseLeave={() => setHover(null)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          disabled={!onChange}
          onMouseEnter={() => onChange && setHover(n)}
          onClick={() => onChange?.(n)}
          className="rounded-sm p-0.5 outline-none transition-transform enabled:hover:scale-110 focus-visible:ring-2 focus-visible:ring-amber disabled:cursor-default"
        >
          <svg width={px} height={px} viewBox="0 0 24 24" aria-hidden>
            <path
              d="M12 2.8l2.8 6 6.5.7-4.9 4.4 1.4 6.4L12 17l-5.8 3.3 1.4-6.4-4.9-4.4 6.5-.7z"
              fill={n <= shown ? "var(--amber)" : "transparent"}
              stroke={n <= shown ? "var(--amber)" : "var(--paper-3)"}
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      ))}
    </div>
  );
}
