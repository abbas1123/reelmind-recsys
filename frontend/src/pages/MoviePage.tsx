import { Button } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Star, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../api/client";
import { Segmented } from "../components/Controls";
import { CenterSpinner, ErrorAlert, Notice } from "../components/Feedback";
import { MovieRow } from "../components/MovieRow";
import { Poster } from "../components/Poster";
import { RatingStars } from "../components/RatingStars";
import { genreColor } from "../lib/genre";
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
  // This page stays mounted between /movie/:id routes: drop the previous film's errors on navigation, and show
  // only the latest action's error (an old failed rating must not linger after a successful save).
  useEffect(() => {
    rate.reset();
    unrate.reset();
    fav.reset();
  }, [id]);
  const actionError = [rate, unrate, fav].reduce((a, b) => (b.submittedAt > a.submittedAt ? b : a)).error;

  if (item.isLoading) return <CenterSpinner label="Loading film" />;
  if (item.error || !item.data) return <ErrorAlert error={item.error ?? "Not found"} />;
  const m = item.data;

  return (
    <div className="flex flex-col gap-12">
      <article className="relative isolate -mx-4 -mt-4 overflow-hidden px-4 pb-10 pt-8 sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10 lg:pt-14">
        <div className="absolute inset-0 -z-10 scale-125 opacity-50 blur-3xl saturate-150" aria-hidden>
          <Poster item={m} eager />
        </div>
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-bg/40 via-bg/80 to-bg" aria-hidden />

        <div className="grid gap-8 md:grid-cols-[260px_1fr] lg:grid-cols-[300px_1fr] lg:gap-12">
          <div className="mx-auto aspect-[2/3] w-56 overflow-hidden rounded-2xl shadow-2xl shadow-black/70 ring-1 ring-white/15 md:w-full">
            <Poster item={m} eager />
          </div>

          <div className="flex flex-col gap-6 md:pt-4">
            <div className="flex flex-wrap gap-2">
              {m.genres.map((g) => (
                <Link
                  key={g}
                  to={`/discover?genre=${encodeURIComponent(g)}`}
                  className="rounded-full px-3 py-1 text-xs font-bold text-white transition hover:brightness-110"
                  style={{ background: genreColor(g) }}
                >
                  {g}
                </Link>
              ))}
            </div>
            <h1 className="text-4xl font-extrabold leading-[1.02] tracking-tight [text-wrap:balance] sm:text-6xl" data-testid="movie-title">
              {m.title}
            </h1>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-text-2">
              <span className="text-base font-semibold text-text">{m.year ?? "Year unknown"}</span>
              <span className="flex items-center gap-1.5">
                <Star className="size-5 fill-gold text-gold" aria-hidden />
                <span className="text-xl font-extrabold text-text tabular">{m.mean_rating !== null ? m.mean_rating.toFixed(2) : "—"}</span>
                <span className="text-text-3">/ 5 MovieLens</span>
              </span>
              <span className="flex items-center gap-1.5">
                <Users className="size-4 text-text-3" aria-hidden />
                <span className="font-semibold text-text tabular">{m.n_ratings.toLocaleString()}</span> ratings
              </span>
            </div>

            {profileId && (
              <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-white/5 p-4 ring-1 ring-white/10 backdrop-blur">
                <Button
                  size="lg"
                  className={`rounded-full px-6 font-bold ${m.is_favorite ? "bg-white text-black hover:bg-white/85" : ""}`}
                  variant={m.is_favorite ? "secondary" : "primary"}
                  onPress={() => fav.mutate(!m.is_favorite)}
                  aria-pressed={m.is_favorite}
                  data-testid="favorite-button"
                >
                  {m.is_favorite ? <Check className="size-5" /> : <Plus className="size-5" />}
                  {m.is_favorite ? "In your list" : "Add to my list"}
                </Button>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-text-2">Your rating</span>
                  <RatingStars value={m.user_rating} onChange={(r) => rate.mutate(r)} />
                  {m.user_rating !== null && (
                    <button type="button" className="text-xs font-semibold text-text-3 hover:text-text" onClick={() => unrate.mutate()}>
                      Clear
                    </button>
                  )}
                </div>
              </div>
            )}
            {actionError && <ErrorAlert error={actionError} />}

            {m.tags.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-3">Community tags · MovieLens 32M</p>
                <div className="flex flex-wrap gap-2">
                  {m.tags.map((t) => (
                    <span key={t} className="rounded-full bg-white/8 px-3 py-1 text-sm text-text-2 ring-1 ring-white/10">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {m.n_ratings === 0 && (
              <Notice title="New to the catalogue">Nobody rated this film in MovieLens 1M, so it is reached only through content similarity.</Notice>
            )}
          </div>
        </div>
      </article>

      <section className="flex flex-col gap-4">
        <Segmented
          label="Similarity type"
          value={simMode}
          onChange={setSimMode}
          size="sm"
          options={[
            { value: "hybrid", label: "More like this" },
            { value: "collaborative", label: "Viewers also rated" },
            { value: "content", label: "Same vibe" },
          ]}
        />
        {similar.error && <ErrorAlert error={similar.error} />}
        <MovieRow
          testId="similar-row"
          title={simMode === "collaborative" ? "Viewers also rated" : simMode === "content" ? "Same vibe" : "More like this"}
          subtitle={SIM_COPY[simMode]}
          items={similar.data?.map((s) => ({ item: s.item }))}
          loading={similar.isLoading}
        />
      </section>
    </div>
  );
}
