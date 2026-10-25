import { Skeleton } from "@heroui/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Bucket, ScoredItem, Strategy } from "../api/types";
import { FilterList, Segmented } from "../components/Controls";
import { CoverArt } from "../components/CoverArt";
import { ErrorAlert } from "../components/Feedback";
import { MovieMeta } from "../components/MovieCard";
import { MovieRow } from "../components/MovieRow";
import { useProfile } from "../state/profile";

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "hybrid", label: "Hybrid" },
  { value: "cf", label: "Collaborative" },
  { value: "content", label: "Content" },
  { value: "popularity", label: "Popularity" },
];

const BUCKET_NOTE: Record<Bucket, { label: string; text: string }> = {
  cold: {
    label: "Cold start",
    text: "No ratings yet. Popular, well-rated films weighted by the genres you chose.",
  },
  light: {
    label: "Light history",
    text: "One to four ratings. Hybrid weights tuned on simulated new users: collaborative, content and trending signals blended.",
  },
  warm: {
    label: "Warm profile",
    text: "Enough history for the collaborative hybrid, tuned on validation users and checked once on the test split.",
  },
};

export default function HomePage() {
  const { profile, profileId } = useProfile();
  const [strategy, setStrategy] = useState<Strategy>("hybrid");
  const [genre, setGenre] = useState<string | null>(null);
  const genres = useQuery({ queryKey: ["genres"], queryFn: api.genres });
  const recs = useQuery({
    queryKey: ["recs", profileId, strategy, genre],
    queryFn: () => api.recommendations(profileId!, { k: 20, strategy, genre }),
    enabled: profileId !== null,
  });
  const topRated = useQuery({ queryKey: ["topRated", genre], queryFn: () => api.topRated(20, genre) });

  const top = recs.data?.sections.find((s) => s.key === "top_picks");
  const rest = recs.data?.sections.filter((s) => s.key !== "top_picks") ?? [];
  const note = recs.data ? BUCKET_NOTE[recs.data.bucket] : null;

  return (
    <div className="flex flex-col gap-14">
      <section className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div>
          <p className="kicker">
            Programme · {new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="mt-4 font-display text-[48px] leading-[0.92] tracking-[-0.02em] sm:text-[72px]">
            Picked for <em className="text-amber">{profile?.display_name ?? "you"}</em>
          </h1>
        </div>
        <aside className="flex flex-col justify-end gap-3 border-l border-rule pl-5" data-testid="bucket">
          {note ? (
            <>
              <p className="kicker !text-amber">
                {note.label} <span className="sr-only">({recs.data!.bucket})</span>
              </p>
              <p className="text-[13.5px] leading-relaxed text-paper-2">{note.text}</p>
              <p className="font-mono text-[11px] text-paper-3 tabular">
                History: {recs.data!.history_size.toLocaleString()} ratings · bucket “{recs.data!.bucket}”
              </p>
            </>
          ) : (
            <Skeleton className="h-16 w-full rounded-sm" />
          )}
        </aside>
      </section>

      <section className="flex flex-col gap-4 border-y border-rule py-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <span className="kicker">Ranking</span>
          <Segmented label="Recommendation strategy" value={strategy} onChange={setStrategy} options={STRATEGIES} size="sm" />
        </div>
        <div className="flex items-center gap-4">
          <span className="kicker shrink-0">Genre</span>
          <div className="min-w-0 flex-1">
            <FilterList
              label="Filter by genre"
              value={genre}
              onChange={setGenre}
              options={genres.data?.map((g) => ({ name: g.name })) ?? []}
              allLabel="All genres"
            />
          </div>
        </div>
      </section>

      {recs.error && <ErrorAlert error={recs.error} onRetry={() => recs.refetch()} />}

      <section data-testid="section-top_picks" aria-label={top?.title ?? "Top picks"} className="flex flex-col gap-6">
        <header className="flex items-end justify-between gap-4">
          <h2 className="font-display text-[32px] leading-none">{top?.title ?? "Top picks for you"}</h2>
          <span className="kicker">{strategy} ranking</span>
        </header>
        {recs.isLoading && <FeatureSkeleton />}
        {top && top.items.length > 0 && <Feature items={top.items} />}
      </section>

      {rest.map((s, i) => (
        <MovieRow
          key={s.key}
          index={String(i + 2).padStart(2, "0")}
          testId={`section-${s.key}`}
          title={s.title}
          subtitle={s.key === "trending" ? "Recency-weighted popularity (half-life counted in interactions)" : "Item-to-item similarity, collaborative and content blended"}
          items={s.items.map((x) => ({ item: x.item }))}
        />
      ))}

      <MovieRow
        index={String(rest.length + 2).padStart(2, "0")}
        testId="section-top-rated"
        title={genre ? `The canon: ${genre}` : "The canon"}
        subtitle="Highest damped average rating among films with at least 50 ratings"
        items={topRated.data?.map((item) => ({ item }))}
        loading={topRated.isLoading}
      />
    </div>
  );
}

/** First pick as a large feature, the next picks as a numbered list, the remainder as a strip. */
function Feature({ items }: { items: ScoredItem[] }) {
  const [lead, ...others] = items;
  const list = others.slice(0, 5);
  const strip = others.slice(5);
  return (
    <div className="flex flex-col gap-10">
      <div className="grid gap-8 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <article className="grid grid-cols-[minmax(0,200px)_1fr] gap-6" data-testid="movie-card" data-item-id={lead.item.id}>
          <Link to={`/movie/${lead.item.id}`} className="block outline-none focus-visible:ring-2 focus-visible:ring-amber">
            <CoverArt item={lead.item} />
          </Link>
          <div className="flex flex-col justify-end gap-3">
            <span className="font-display text-[64px] leading-none text-amber">01</span>
            <Link to={`/movie/${lead.item.id}`} className="font-display text-[34px] leading-[1.02] tracking-[-0.01em] hover:text-amber">
              {lead.item.title}
            </Link>
            <MovieMeta item={lead.item} />
            <p className="text-[12px] uppercase tracking-[0.14em] text-paper-3">{lead.item.genres.join(" · ")}</p>
            {lead.reason && (
              <p className="border-l-2 border-amber pl-3 font-display text-[18px] italic leading-snug text-paper-2" data-testid="rec-reason">
                {lead.reason}
              </p>
            )}
          </div>
        </article>
        <ol className="border-t border-rule">
          {list.map((x, i) => (
            <li key={x.item.id} className="border-b border-rule" data-testid="movie-card" data-item-id={x.item.id}>
              <Link to={`/movie/${x.item.id}`} className="group grid grid-cols-[2.25rem_44px_1fr] items-center gap-4 py-3 outline-none focus-visible:bg-ink-raised">
                <span className="font-mono text-[11px] text-paper-3">{String(i + 2).padStart(2, "0")}</span>
                <CoverArt item={x.item} size="sm" />
                <span className="min-w-0">
                  <span className="block truncate font-display text-[21px] leading-tight group-hover:text-amber">{x.item.title}</span>
                  <MovieMeta item={x.item} />
                  {x.reason && (
                    <span className="block truncate font-display text-[14px] italic text-paper-3" data-testid="rec-reason">
                      {x.reason}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </div>
      {strip.length > 0 && (
        <MovieRow title="More in this programme" index="—" items={strip.map((x) => ({ item: x.item, reason: x.reason }))} numbered={false} />
      )}
    </div>
  );
}

function FeatureSkeleton() {
  return (
    <div className="grid gap-8 md:grid-cols-[1.15fr_1fr]">
      <div className="grid grid-cols-[200px_1fr] gap-6">
        <Skeleton className="aspect-[2/3] w-full rounded-[3px]" />
        <div className="flex flex-col justify-end gap-3">
          <Skeleton className="h-10 w-3/4 rounded-sm" />
          <Skeleton className="h-4 w-1/2 rounded-sm" />
        </div>
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-sm" />
        ))}
      </div>
    </div>
  );
}
