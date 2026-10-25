import type { Item } from "../api/types";
import { hash, toneFor } from "../lib/genre";

type CoverItem = Pick<Item, "id" | "title" | "year" | "genres">;

/**
 * Typeset cover built only from metadata (MovieLens ships no artwork, so we never fake a poster).
 * Colour comes from the primary genre, the geometric motif and layout from a hash of the id.
 */
export function CoverArt({ item, size = "md" }: { item: CoverItem; size?: "sm" | "md" | "lg" }) {
  const [bg, ink, motif] = toneFor(item.genres);
  const h = hash(item.id);
  const variant = h % 5;
  const titleTop = variant === 1 || variant === 4;
  const len = item.title.length;
  const titleSize =
    size === "lg"
      ? len > 40 ? "text-3xl" : len > 22 ? "text-4xl" : "text-5xl"
      : size === "sm"
        ? len > 30 ? "text-sm" : "text-base"
        : len > 40 ? "text-lg" : len > 22 ? "text-xl" : "text-2xl";

  return (
    <div
      className="relative aspect-[2/3] w-full overflow-hidden rounded-[3px] shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_18px_40px_-24px_rgba(0,0,0,0.8)]"
      style={{ background: bg, color: ink }}
      role="img"
      aria-label={`Typeset cover for ${item.title}${item.year ? ` (${item.year})` : ""}`}
    >
      <Motif variant={variant} color={motif} seed={h} />
      <div className="cover-grain absolute inset-0 opacity-60" />

      <div className={`absolute inset-x-0 flex items-start justify-between px-3 ${size === "sm" ? "top-2" : "top-3"}`}>
        <span className="font-mono text-[9px] tracking-[0.18em] opacity-75">No.&nbsp;{item.id}</span>
        {item.year && <span className="font-mono text-[9px] tracking-[0.18em] opacity-75">{item.year}</span>}
      </div>

      <div
        className={`absolute inset-x-0 px-3 ${titleTop ? (size === "sm" ? "top-7" : "top-9") : size === "sm" ? "bottom-7" : "bottom-10"}`}
      >
        <p className={`font-display leading-[0.95] tracking-[-0.01em] line-clamp-4 [text-wrap:balance] ${titleSize}`}>
          {item.title}
        </p>
      </div>

      {size !== "sm" && (
        <div className="absolute inset-x-3 bottom-3 flex items-center gap-2 border-t pt-1.5" style={{ borderColor: `${ink}40` }}>
          <span className="truncate text-[8.5px] font-medium uppercase tracking-[0.2em] opacity-80">
            {item.genres.slice(0, 2).join(" · ") || "Film"}
          </span>
        </div>
      )}
    </div>
  );
}

function Motif({ variant, color, seed }: { variant: number; color: string; seed: number }) {
  const r = (n: number) => ((seed >>> n) & 0xff) / 255; // deterministic jitter 0..1
  return (
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 200 300" preserveAspectRatio="xMidYMid slice" aria-hidden>
      {variant === 0 && <circle cx={130 + r(3) * 40} cy={95 + r(7) * 30} r={70} fill={color} opacity={0.85} />}
      {variant === 1 && (
        <g fill={color}>
          <rect x="0" y={175} width="200" height="16" opacity={0.9} />
          <rect x="0" y={199} width="200" height="7" opacity={0.6} />
          <rect x="0" y={214} width="200" height="3" opacity={0.4} />
        </g>
      )}
      {variant === 2 && <path d={`M${-20 + r(5) * 30} 300 L${150 + r(9) * 40} 0 L${210} 0 L${40 + r(5) * 30} 300 Z`} fill={color} opacity={0.75} />}
      {variant === 3 && (
        <g fill="none" stroke={color} strokeWidth="5">
          {[28, 50, 72, 94].map((rad, i) => (
            <circle key={rad} cx={60 + r(11) * 80} cy={110} r={rad} opacity={0.95 - i * 0.18} />
          ))}
        </g>
      )}
      {variant === 4 && (
        <g fill={color}>
          <rect x={142 + r(13) * 20} y="0" width="22" height="300" opacity={0.8} />
          <circle cx={60 + r(4) * 30} cy={230} r={14} />
        </g>
      )}
    </svg>
  );
}
