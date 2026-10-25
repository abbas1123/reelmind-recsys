import { Button } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../api/client";
import { Segmented } from "../components/Controls";
import { CoverArt } from "../components/CoverArt";
import { CenterSpinner, ErrorAlert, Notice } from "../components/Feedback";
import { MovieRow } from "../components/MovieRow";
import { RatingStars } from "../components/RatingStars";
import { useProfile } from "../state/profile";

type SimMode = "hybrid" | "collaborative" | "content";

const SIM_COPY: Record<SimMode, string> = {
  hybrid: "Collaborative and content similarity, each normalised and summed.",
  collaborative: "Films the same viewers rated (item-to-item weights of the trained model).",
  content: "Closest by title, year, genres and community tags.",
};

export default function MoviePage() {
  const id = Number(useParams().id);
  const { profileId, refresh } = useProfile();
  const qc = useQueryClient();
  const [simMode, setSimMode] = useState<SimMode>("hybrid");
  const item = useQuery({ queryKey: ["item", id, profileId], queryFn: () => api.item(id, profileId) });
  const similar = useQuery({ queryKey: ["similar", id, simMode], queryFn: () => api.similar(id, simMode, 14) });

  // Log one view per film shown. The ref survives React StrictMode's dev-only effect re-run, which logged every view twice.
  const loggedView = useRef<string | null>(null);
  useEffect(() => {
    const key = `${profileId}:${id}`;
    if (profileId && Number.isFinite(id) && loggedView.current !== key) {
      loggedView.current = key;
      api.logInteraction(profileId, "view", id).catch(() => undefined);
    }
  }, [id, profileId]);

  const afterChange = () => {
    qc.invalidateQueries({ queryKey: ["item", id] });
    qc.invalidateQueries({ queryKey: ["recs"] });
    qc.invalidateQueries({ queryKey: ["ratings"] });
    qc.invalidateQueries({ queryKey: ["favorites"] });
    refresh();
  };
  const rate = useMutation({ mutationFn: (r: number) => api.rate(profileId!, id, r), onSuccess: afterChange });
  const unrate = useMutation({ mutationFn: () => api.unrate(profileId!, id), onSuccess: afterChange });
  const fav = useMutation({
    mutationFn: async (on: boolean) => {
      if (on) await api.favorite(profileId!, id);
      else await api.unfavorite(profileId!, id);
    },
    onSuccess: afterChange,
  });

  if (item.isLoading) return <CenterSpinner label="Loading film" />;
  if (item.error || !item.data) return <ErrorAlert error={item.error ?? "Not found"} />;
  const m = item.data;

  return (
    <div className="flex flex-col gap-16">
      <article className="grid gap-10 md:grid-cols-[300px_1fr] lg:gap-16">
        <div className="mx-auto w-60 md:w-full">
          <CoverArt item={m} size="lg" />
          <p className="mt-3 font-mono text-[10px] leading-relaxed text-paper-3">Cover typeset from metadata. MovieLens contains no artwork.</p>
        </div>

        <div className="flex flex-col gap-8">
          <div>
            <p className="kicker">
              No. {m.id} · {m.year ?? "year unknown"} ·{" "}
              {m.genres.map((g, i) => (
                <span key={g}>
                  {i > 0 && " / "}
                  <Link to={`/discover?genre=${encodeURIComponent(g)}`} className="hover:text-amber">
                    {g}
                  </Link>
                </span>
              ))}
            </p>
            <h1 className="mt-4 font-display text-[52px] leading-[0.92] tracking-[-0.02em] [text-wrap:balance] sm:text-[76px]" data-testid="movie-title">
              {m.title}
            </h1>
          </div>

          <dl className="grid grid-cols-2 border-y border-rule sm:grid-cols-3">
            <div className="border-r border-rule py-4 pr-4">
              <dt className="kicker">MovieLens average</dt>
              <dd className="mt-1 font-display text-[40px] leading-none tabular">
                {m.mean_rating !== null ? m.mean_rating.toFixed(2) : "—"}
                <span className="font-sans text-sm text-paper-3"> / 5</span>
              </dd>
            </div>
            <div className="py-4 pl-4 sm:border-r sm:border-rule sm:pr-4">
              <dt className="kicker">Ratings</dt>
              <dd className="mt-1 font-display text-[40px] leading-none tabular">{m.n_ratings.toLocaleString()}</dd>
            </div>
            {profileId && (
              <div className="col-span-2 border-t border-rule py-4 sm:col-span-1 sm:border-t-0 sm:pl-4">
                <dt className="kicker">Your rating</dt>
                <dd className="mt-2 flex items-center gap-3">
                  <RatingStars value={m.user_rating} onChange={(r) => rate.mutate(r)} />
                  {m.user_rating !== null && (
                    <button type="button" className="kicker hover:text-paper" onClick={() => unrate.mutate()}>
                      Clear
                    </button>
                  )}
                </dd>
              </div>
            )}
          </dl>

          {profileId && (
            <div className="flex flex-wrap items-center gap-4">
              <Button
                variant={m.is_favorite ? "primary" : "outline"}
                onPress={() => fav.mutate(!m.is_favorite)}
                aria-pressed={m.is_favorite}
                data-testid="favorite-button"
              >
                {m.is_favorite ? "✓ In your list" : "+ Add to my list"}
              </Button>
              <span className="text-[13px] text-paper-3">Ratings and saves are folded into your recommendations immediately.</span>
            </div>
          )}
          {(rate.error || unrate.error || fav.error) && <ErrorAlert error={rate.error ?? unrate.error ?? fav.error} />}

          {m.tags.length > 0 && (
            <div>
              <p className="kicker mb-2">Community tags · MovieLens 32M</p>
              <p className="max-w-2xl font-display text-[20px] leading-snug text-paper-2">
                {m.tags.map((t, i) => (
                  <span key={t}>
                    {i > 0 && <span className="text-paper-3"> · </span>}
                    {t}
                  </span>
                ))}
              </p>
            </div>
          )}

          {m.n_ratings === 0 && (
            <Notice title="Cold item">Nobody rated this film in MovieLens 1M. It can only be reached through content similarity.</Notice>
          )}
        </div>
      </article>

      <section className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="kicker">Related films</p>
          <Segmented
            label="Similarity type"
            value={simMode}
            onChange={setSimMode}
            size="sm"
            options={[
              { value: "hybrid", label: "Blend" },
              { value: "collaborative", label: "Viewers also rated" },
              { value: "content", label: "Same vibe" },
            ]}
          />
        </div>
        {similar.error && <ErrorAlert error={similar.error} />}
        <MovieRow
          testId="similar-row"
          index="01"
          title={simMode === "collaborative" ? "Viewers also rated" : simMode === "content" ? "Same vibe" : "If you liked this"}
          subtitle={SIM_COPY[simMode]}
          items={similar.data?.map((s) => ({ item: s.item }))}
          loading={similar.isLoading}
        />
      </section>
    </div>
  );
}
