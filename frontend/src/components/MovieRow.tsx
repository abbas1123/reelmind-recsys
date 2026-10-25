import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { Link } from "react-router";
import type { Item } from "../api/types";
import { MovieCard, MovieCardSkeleton } from "./MovieCard";
import { Poster } from "./Poster";

interface RowItem {
  item: Item;
  reason?: string | null;
}

export function SectionHeading({ title, subtitle, aside, as: Tag = "h2" }: {
  title: ReactNode;
  subtitle?: ReactNode;
  aside?: ReactNode;
  as?: "h1" | "h2";
}) {
  return (
    <header className="flex items-end justify-between gap-4">
      <div className="min-w-0">
        <Tag className="text-xl font-bold tracking-tight sm:text-2xl">{title}</Tag>
        {subtitle && <p className="mt-1 text-sm text-text-3">{subtitle}</p>}
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </header>
  );
}

function Scroller({ children, label }: { children: ReactNode; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const scroll = (dir: 1 | -1) => ref.current?.scrollBy({ left: dir * ref.current.clientWidth * 0.85, behavior: "smooth" });
  return (
    <div className="group/row relative">
      <div ref={ref} className="scroll-row -mx-4 flex gap-4 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
        {children}
      </div>
      {(["prev", "next"] as const).map((d) => (
        <button
          key={d}
          type="button"
          aria-label={`Scroll ${label} ${d === "prev" ? "left" : "right"}`}
          onClick={() => scroll(d === "prev" ? -1 : 1)}
          className={`absolute top-[38%] z-10 hidden size-10 -translate-y-1/2 place-items-center rounded-full bg-black/70 text-white opacity-0 ring-1 ring-white/20 backdrop-blur transition hover:bg-black group-hover/row:opacity-100 focus-visible:opacity-100 lg:grid ${
            d === "prev" ? "-left-4" : "-right-4"
          }`}
        >
          {d === "prev" ? <ChevronLeft className="size-5" /> : <ChevronRight className="size-5" />}
        </button>
      ))}
    </div>
  );
}

export function MovieRow({ title, subtitle, items, loading, testId, aside }: {
  title: ReactNode;
  subtitle?: ReactNode;
  items: RowItem[] | undefined;
  loading?: boolean;
  testId?: string;
  aside?: ReactNode;
}) {
  const label = typeof title === "string" ? title : "row";
  return (
    <section className="flex flex-col gap-4" data-testid={testId} aria-label={typeof title === "string" ? title : undefined}>
      <SectionHeading title={title} subtitle={subtitle} aside={aside} />
      <Scroller label={label}>
        {loading && Array.from({ length: 8 }).map((_, i) => <MovieCardSkeleton key={i} className="w-[142px] shrink-0 sm:w-[168px] xl:w-[184px]" />)}
        {!loading && items?.length === 0 && <p className="py-10 text-sm text-text-3">Nothing here yet.</p>}
        {!loading &&
          items?.map(({ item, reason }) => (
            <MovieCard key={item.id} item={item} reason={reason} className="w-[142px] shrink-0 sm:w-[168px] xl:w-[184px]" />
          ))}
      </Scroller>
    </section>
  );
}

/** Netflix-style "Top 10" row: oversized outlined rank numerals next to the posters. */
export function Top10Row({ title, subtitle, items, testId }: { title: string; subtitle?: string; items: Item[] | undefined; testId?: string }) {
  return (
    <section className="flex flex-col gap-4" data-testid={testId} aria-label={title}>
      <SectionHeading title={title} subtitle={subtitle} />
      <Scroller label={title}>
        {items?.slice(0, 10).map((item, i) => (
          <Link
            key={item.id}
            to={`/movie/${item.id}`}
            className="group flex shrink-0 items-end outline-none focus-visible:ring-2 focus-visible:ring-brand"
            aria-label={`#${i + 1} ${item.title}`}
          >
            <span className="rank-numeral -mr-5 select-none text-[118px] sm:text-[150px]" aria-hidden>
              {i + 1}
            </span>
            <span className="relative block aspect-[2/3] w-[112px] overflow-hidden rounded-lg shadow-xl shadow-black/60 ring-1 ring-white/10 transition duration-300 group-hover:-translate-y-1 sm:w-[132px]">
              <Poster item={item} />
            </span>
          </Link>
        ))}
      </Scroller>
    </section>
  );
}

/** Instagram-Explore-style grid: every 7th tile is featured at double size. */
export function MovieGrid({ items, loading, explore = false }: { items: RowItem[] | undefined; loading?: boolean; explore?: boolean }) {
  return (
    <div className={`grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 ${explore ? "[grid-auto-flow:dense]" : ""}`}>
      {loading && Array.from({ length: 12 }).map((_, i) => <MovieCardSkeleton key={i} />)}
      {!loading &&
        items?.map(({ item, reason }, i) => (
          <MovieCard
            key={item.id}
            item={item}
            reason={reason}
            className={explore && i % 7 === 0 ? "col-span-2 row-span-2 [&_a:first-child]:rounded-2xl" : ""}
          />
        ))}
    </div>
  );
}
