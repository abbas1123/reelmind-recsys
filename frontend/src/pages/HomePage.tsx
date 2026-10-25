import { Button, Skeleton } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Info, Plus, Sparkles, Star } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import type { Bucket, ScoredItem, Strategy } from "../api/types";
import { FilterList, Segmented } from "../components/Controls";
import { ErrorAlert } from "../components/Feedback";
import { MovieRow, Top10Row } from "../components/MovieRow";
import { Poster } from "../components/Poster";
import { useProfile } from "../state/profile";

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "hybrid", label: "For you" },
  { value: "cf", label: "Collaborative" },
  { value: "content", label: "Content" },
  { value: "popularity", label: "Popular" },
];

const BUCKET_NOTE: Record<Bucket, string> = {
  cold: "No ratings yet — popular, well-rated films weighted by the genres you picked.",
  light: "A few ratings — hybrid weights tuned on simulated new users blend collaborative, content and trending signals.",
  warm: "Enough history for the collaborative hybrid, tuned on validation users and checked once on the test split.",
};

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Good night" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

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
  const trending = useQuery({ queryKey: ["trending10", genre], queryFn: () => api.trending(10, genre) });

  const top = recs.data?.sections.find((s) => s.key === "top_picks");
  const rest = recs.data?.sections.filter((s) => s.key !== "top_picks" && s.key !== "trending") ?? [];
  const [lead, ...others] = top?.items ?? [];

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-text-3">{greeting()}</p>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{profile?.display_name ?? "…"}</h1>
        </div>
        <Segmented label="Recommendation strategy" value={strategy} onChange={setStrategy} options={STRATEGIES} />
      </div>

      <FilterList label="Filter by genre" value={genre} onChange={setGenre} options={genres.data?.map((g) => ({ name: g.name })) ?? []} allLabel="All genres" />

      {recs.error && <ErrorAlert error={recs.error} onRetry={() => recs.refetch()} />}

      <section data-testid="section-top_picks" aria-label={top?.title ?? "Top picks"} className="flex flex-col gap-10">
        {recs.isLoading && <Skeleton className="h-[440px] w-full rounded-[28px]" />}
        {lead && <Billboard rec={lead} bucket={recs.data!.bucket} history={recs.data!.history_size} />}
        {top && top.items.length === 0 && (
          <p className="rounded-3xl bg-surface-1 p-10 text-center text-text-2 ring-1 ring-line">
            Nothing left to recommend with these filters — you have rated everything that matches. Try another genre or ranking.
          </p>
        )}
        {others.length > 0 && (
          <MovieRow
            title={top?.title ?? "Top picks for you"}
            subtitle={STRATEGIES.find((s) => s.value === strategy)?.label + " ranking · personalised"}
            items={others.map((x) => ({ item: x.item, reason: x.reason }))}
          />
        )}
      </section>

      {rest.map((s) => (
        <MovieRow key={s.key} testId={`section-${s.key}`} title={s.title} subtitle="Similar by who watched it and what it is about" items={s.items.map((x) => ({ item: x.item }))} />
      ))}

      {trending.error && <ErrorAlert error={trending.error} onRetry={() => trending.refetch()} />}
      <Top10Row
        testId="section-trending"
        title={genre ? `Top 10 in ${genre}` : "Top 10 trending"}
        subtitle="Recency-weighted popularity (half-life counted in interactions)"
        items={trending.data}
      />

      {topRated.error && <ErrorAlert error={topRated.error} onRetry={() => topRated.refetch()} />}
      <MovieRow
        testId="section-top-rated"
        title={genre ? `Highest rated ${genre}` : "All-time highest rated"}
        subtitle="Damped average rating, at least 50 ratings"
        items={topRated.data?.map((item) => ({ item }))}
        loading={topRated.isLoading}
      />
    </div>
  );
}

/** Netflix-style hero for the #1 recommendation with the poster as a blurred backdrop. */
function Billboard({ rec, bucket, history }: { rec: ScoredItem; bucket: Bucket; history: number }) {
  const { profileId, refresh } = useProfile();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const m = rec.item;
  const save = useMutation({
    mutationFn: () => api.favorite(profileId!, m.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["favorites"] });
      refresh();
    },
  });
  return (
    <article className="relative isolate overflow-hidden rounded-[28px] bg-surface-1 ring-1 ring-line" data-testid="movie-card" data-item-id={m.id}>
      <div className="absolute inset-0 -z-10 scale-125 opacity-60 blur-3xl saturate-150" aria-hidden>
        <Poster item={m} eager />
      </div>
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-bg via-bg/85 to-bg/30" aria-hidden />
      <div className="absolute inset-0 -z-10 bg-gradient-to-t from-bg/80 via-transparent to-transparent" aria-hidden />

      <div className="grid items-center gap-8 p-6 sm:p-10 md:grid-cols-[1fr_auto]">
        <div className="flex max-w-2xl flex-col gap-4">
          <span className="inline-flex w-fit items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-white ring-1 ring-white/15 backdrop-blur">
            <Sparkles className="size-3.5 text-brand" aria-hidden /> #1 pick for you
          </span>
          <Link to={`/movie/${m.id}`} className="text-4xl font-extrabold leading-[1.02] tracking-tight hover:underline sm:text-6xl">
            {m.title}
          </Link>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-2">
            <span className="font-semibold text-text">{m.year}</span>
            {m.mean_rating !== null && (
              <span className="flex items-center gap-1">
                <Star className="size-4 fill-gold text-gold" aria-hidden />
                <span className="font-semibold text-text">{m.mean_rating.toFixed(1)}</span> ({m.n_ratings.toLocaleString()} ratings)
              </span>
            )}
            <span>{m.genres.join(" · ")}</span>
          </p>
          {rec.reason && (
            <p className="flex items-center gap-2 text-base font-medium text-text" data-testid="rec-reason">
              <Sparkles className="size-4 shrink-0 text-brand" aria-hidden />
              {rec.reason}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-3">
            <Button size="lg" className="rounded-full bg-white px-7 font-bold text-black hover:bg-white/85" onPress={() => navigate(`/movie/${m.id}`)}>
              View details
            </Button>
            <Button size="lg" variant="secondary" className="rounded-full bg-white/15 px-6 text-white backdrop-blur hover:bg-white/25" onPress={() => save.mutate()} isDisabled={save.isPending || save.isSuccess}>
              {save.isSuccess ? <Check className="size-5" /> : <Plus className="size-5" />}
              {save.isSuccess ? "Saved" : "My list"}
            </Button>
          </div>
          {save.error && <ErrorAlert error={save.error} />}
          <p className="mt-1 flex items-start gap-2 text-xs text-text-3" data-testid="bucket">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>
              <span className="font-semibold uppercase text-text-2">{bucket}</span> · {BUCKET_NOTE[bucket]} History: {history.toLocaleString()} ratings.
            </span>
          </p>
        </div>
        <Link to={`/movie/${m.id}`} className="hidden aspect-[2/3] w-56 overflow-hidden rounded-2xl shadow-2xl shadow-black/60 ring-1 ring-white/15 transition hover:scale-[1.02] md:block lg:w-64" tabIndex={-1} aria-hidden>
          <Poster item={m} eager />
        </Link>
      </div>
    </article>
  );
}
