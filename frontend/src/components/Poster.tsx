import { useState } from "react";
import type { Item } from "../api/types";
import { genreColor, hash } from "../lib/genre";

type PosterItem = Pick<Item, "id" | "title" | "year" | "genres" | "poster_url">;

/**
 * Real poster when one was cached by `recsys download-posters`; otherwise a gradient artwork
 * built from the genre colour (MovieLens itself ships no images).
 */
export function Poster({ item, className = "", eager = false }: { item: PosterItem; className?: string; eager?: boolean }) {
  const [failed, setFailed] = useState(false);
  if (item.poster_url && !failed) {
    return (
      <img
        src={item.poster_url}
        alt={`Poster: ${item.title}`}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        onError={() => setFailed(true)}
        className={`h-full w-full object-cover ${className}`}
      />
    );
  }
  return <Artwork item={item} className={className} />;
}

export function Artwork({ item, className = "" }: { item: PosterItem; className?: string }) {
  const base = genreColor(item.genres);
  const h = hash(item.id);
  const x = 20 + (h % 60);
  const y = 15 + ((h >>> 8) % 50);
  return (
    <div
      role="img"
      aria-label={`Artwork for ${item.title} (no poster available)`}
      className={`relative flex h-full w-full flex-col justify-end overflow-hidden p-3 ${className}`}
      style={{
        background: `radial-gradient(120% 90% at ${x}% ${y}%, ${base} 0%, transparent 60%),
          radial-gradient(90% 80% at ${100 - x}% 100%, ${base}aa 0%, transparent 55%),
          linear-gradient(160deg, #1d1d27, #0e0e14)`,
      }}
    >
      <p className="line-clamp-3 text-[15px] font-extrabold leading-tight tracking-tight text-white drop-shadow">{item.title}</p>
      {item.year && <p className="mt-0.5 text-xs font-medium text-white/70">{item.year}</p>}
    </div>
  );
}
