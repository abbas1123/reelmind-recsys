import { Skeleton } from "@heroui/react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import type { Item } from "../api/types";
import { CoverArt } from "./CoverArt";

export function MovieMeta({ item, className = "" }: { item: Item; className?: string }) {
  return (
    <p className={`font-mono text-[11px] text-paper-3 tabular ${className}`}>
      {item.year ?? "—"}
      {item.mean_rating !== null ? (
        <>
          {" · "}
          <span className="text-paper-2">{item.mean_rating.toFixed(2)}</span>
          <span title={`${item.n_ratings.toLocaleString()} MovieLens ratings`}> ({compact(item.n_ratings)})</span>
        </>
      ) : (
        <span title="No ratings in MovieLens 1M — reachable only through content similarity"> · unrated</span>
      )}
    </p>
  );
}

function compact(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k` : String(n);
}

export function MovieCard({ item, reason, index, extra }: {
  item: Item;
  reason?: string | null;
  index?: number;
  extra?: ReactNode;
}) {
  return (
    <article className="group flex w-full flex-col gap-2.5" data-testid="movie-card" data-item-id={item.id}>
      <Link
        to={`/movie/${item.id}`}
        className="relative block outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
      >
        <div className="transition-transform duration-300 ease-out group-hover:-translate-y-1">
          <CoverArt item={item} />
        </div>
        {index !== undefined && (
          <span className="absolute -left-1 -top-2 font-mono text-[10px] text-paper-3">{String(index).padStart(2, "0")}</span>
        )}
      </Link>
      <div className="min-w-0">
        <Link to={`/movie/${item.id}`} className="link-underline block truncate text-[13.5px] font-medium text-paper" title={item.title}>
          {item.title}
        </Link>
        <MovieMeta item={item} className="mt-0.5" />
        {reason && (
          <p className="mt-1 line-clamp-2 font-display text-[14px] italic leading-snug text-paper-2" data-testid="rec-reason">
            {reason}
          </p>
        )}
        {extra}
      </div>
    </article>
  );
}

export function MovieCardSkeleton() {
  return (
    <div className="flex w-full flex-col gap-2.5">
      <Skeleton className="aspect-[2/3] w-full rounded-[3px]" />
      <Skeleton className="h-3 w-3/4 rounded-sm" />
      <Skeleton className="h-2.5 w-1/2 rounded-sm" />
    </div>
  );
}
