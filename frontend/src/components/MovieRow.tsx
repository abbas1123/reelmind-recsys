import type { ReactNode } from "react";
import type { Item } from "../api/types";
import { MovieCard, MovieCardSkeleton } from "./MovieCard";

interface RowItem {
  item: Item;
  reason?: string | null;
}

export function SectionHeading({ index, title, aside, children }: {
  index?: string;
  title: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-3 border-t border-rule pt-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-baseline gap-4">
        {index && <span className="font-mono text-[11px] text-paper-3">{index}</span>}
        <div>
          <h2 className="font-display text-[28px] leading-none tracking-[-0.01em] sm:text-[32px]">{title}</h2>
          {children && <div className="mt-1.5 text-sm text-paper-3">{children}</div>}
        </div>
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </header>
  );
}

export function MovieRow({ title, index, subtitle, items, loading, testId, numbered }: {
  title: ReactNode;
  index?: string;
  subtitle?: ReactNode;
  items: RowItem[] | undefined;
  loading?: boolean;
  testId?: string;
  numbered?: boolean;
}) {
  return (
    <section className="flex flex-col gap-5" data-testid={testId} aria-label={typeof title === "string" ? title : undefined}>
      <SectionHeading
        index={index}
        title={title}
        aside={items && !loading ? <span className="kicker">{items.length} titles</span> : undefined}
      >
        {subtitle}
      </SectionHeading>
      <div className="scroll-row -mx-5 flex gap-5 overflow-x-auto px-5 pb-1 sm:-mx-8 sm:px-8">
        {loading &&
          Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="w-[148px] shrink-0 sm:w-[164px]">
              <MovieCardSkeleton />
            </div>
          ))}
        {!loading && items?.length === 0 && <p className="py-8 text-sm text-paper-3">Nothing here yet.</p>}
        {!loading &&
          items?.map(({ item, reason }, i) => (
            <div key={item.id} className="w-[148px] shrink-0 sm:w-[164px]">
              <MovieCard item={item} reason={reason} index={numbered ? i + 1 : undefined} />
            </div>
          ))}
      </div>
    </section>
  );
}

export function MovieGrid({ items, loading }: { items: RowItem[] | undefined; loading?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
      {loading && Array.from({ length: 12 }).map((_, i) => <MovieCardSkeleton key={i} />)}
      {!loading && items?.map(({ item, reason }) => <MovieCard key={item.id} item={item} reason={reason} />)}
    </div>
  );
}
