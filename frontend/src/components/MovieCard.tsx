import { Skeleton } from "@heroui/react";
import { Sparkles, Star } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import type { Item } from "../api/types";
import { compact } from "../lib/genre";
import { Poster } from "./Poster";

export function MovieMeta({ item, className = "" }: { item: Item; className?: string }) {
  return (
    <p className={`flex items-center gap-1.5 text-xs text-text-3 tabular ${className}`}>
      <span>{item.year ?? "—"}</span>
      {item.mean_rating !== null ? (
        <>
          <span aria-hidden>·</span>
          <Star className="size-3 fill-gold text-gold" aria-hidden />
          <span className="text-text-2" title={`${item.n_ratings.toLocaleString()} MovieLens ratings`}>
            {item.mean_rating.toFixed(1)}
          </span>
          <span>({compact(item.n_ratings)})</span>
        </>
      ) : (
        <span title="No ratings in MovieLens 1M — reachable only through content similarity">· new</span>
      )}
    </p>
  );
}

/** Poster card used in carousels and grids. */
export function MovieCard({ item, reason, extra, className = "" }: {
  item: Item;
  reason?: string | null;
  extra?: ReactNode;
  className?: string;
}) {
  return (
    <article className={`group flex flex-col gap-2.5 ${className}`} data-testid="movie-card" data-item-id={item.id}>
      <Link
        to={`/movie/${item.id}`}
        className="relative block aspect-[2/3] overflow-hidden rounded-xl bg-surface-2 shadow-lg shadow-black/40 ring-1 ring-white/5 outline-none transition duration-300 ease-out group-hover:-translate-y-1 group-hover:shadow-2xl group-hover:ring-white/25 focus-visible:ring-2 focus-visible:ring-brand"
      >
        <Poster item={item} className="transition duration-500 group-hover:scale-[1.04]" />
        <span className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 transition group-hover:opacity-100" />
      </Link>
      <div className="min-w-0 px-0.5">
        <Link to={`/movie/${item.id}`} className="block truncate text-sm font-semibold hover:text-brand" title={item.title}>
          {item.title}
        </Link>
        <MovieMeta item={item} className="mt-0.5" />
        {reason && (
          <p className="mt-1 flex items-start gap-1 text-xs leading-snug text-text-2" data-testid="rec-reason">
            <Sparkles className="mt-0.5 size-3 shrink-0 text-brand" aria-hidden />
            <span className="line-clamp-2">{reason}</span>
          </p>
        )}
        {extra}
      </div>
    </article>
  );
}

export function MovieCardSkeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col gap-2.5 ${className}`}>
      <Skeleton className="aspect-[2/3] w-full rounded-xl" />
      <Skeleton className="h-3.5 w-3/4 rounded-full" />
      <Skeleton className="h-3 w-1/2 rounded-full" />
    </div>
  );
}
