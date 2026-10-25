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
  const px = size === "sm" ? 16 : 24;
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
          className="rounded-md p-0.5 outline-none transition-transform enabled:hover:scale-115 focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-default"
        >
          <svg width={px} height={px} viewBox="0 0 24 24" aria-hidden>
            <path
              d="M12 2.6l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.4l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z"
              fill={n <= shown ? "var(--gold)" : "rgb(255 255 255 / 0.12)"}
              stroke={n <= shown ? "var(--gold)" : "rgb(255 255 255 / 0.25)"}
              strokeWidth="1"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      ))}
    </div>
  );
}
