import { Tabs } from "@heroui/react";
import { useQuery } from "@tanstack/react-query";
import { Eye, Heart, HeartOff, Search, Star } from "lucide-react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { InteractionRow } from "../api/types";
import { avatarGradient, initials } from "../components/AppShell";
import { ErrorAlert } from "../components/Feedback";
import { MovieCard } from "../components/MovieCard";
import { MovieGrid } from "../components/MovieRow";
import { Poster } from "../components/Poster";
import { RatingStars } from "../components/RatingStars";
import { useProfile } from "../state/profile";

const tabClass =
  "h-10 rounded-full px-5 text-sm font-semibold text-text-3 data-[selected]:text-black data-[hovered]:text-text data-[selected]:data-[hovered]:text-black";

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-3xl bg-surface-1 p-10 text-center text-text-2 ring-1 ring-line">{children}</p>;
}

function HistoryIcon({ row }: { row: InteractionRow }) {
  const cls = "size-4";
  if (row.kind === "rate") return <Star className={`${cls} fill-gold text-gold`} aria-hidden />;
  if (row.kind === "favorite") return row.value ? <Heart className={`${cls} fill-brand text-brand`} aria-hidden /> : <HeartOff className={cls} aria-hidden />;
  if (row.kind === "search") return <Search className={cls} aria-hidden />;
  return <Eye className={cls} aria-hidden />;
}

export default function MePage() {
  const { profileId, profile } = useProfile();
  // Always refetch on open: views, searches and onboarding ratings are logged elsewhere without invalidating these.
  const ratings = useQuery({ queryKey: ["ratings", profileId], queryFn: () => api.ratings(profileId!), staleTime: 0 });
  const favorites = useQuery({ queryKey: ["favorites", profileId], queryFn: () => api.favorites(profileId!), staleTime: 0 });
  const history = useQuery({ queryKey: ["history", profileId], queryFn: () => api.history(profileId!, 100), staleTime: 0 });

  return (
    <div className="flex flex-col gap-8">
      <header className="flex items-center gap-5">
        <span
          className="grid size-20 shrink-0 place-items-center rounded-3xl text-2xl font-extrabold text-white shadow-xl shadow-black/40 sm:size-28 sm:text-4xl"
          style={{ background: profile ? avatarGradient(profile.id) : "var(--surface-3)" }}
          aria-hidden
        >
          {profile ? initials(profile.display_name) : "?"}
        </span>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-text-3">Profile</p>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">{profile?.display_name ?? "My list"}</h1>
          <p className="mt-1 text-sm text-text-2">
            {favorites.data?.length ?? 0} saved · {ratings.data?.length ?? 0} rated in the app
            {profile?.ml_user_id ? ` · plus MovieLens user #${profile.ml_user_id}'s original ratings` : ""}
          </p>
        </div>
      </header>

      <Tabs aria-label="My activity" defaultSelectedKey="favorites">
        <Tabs.ListContainer>
          <Tabs.List className="w-fit gap-1 rounded-full bg-surface-2 p-1 ring-1 ring-line">
            <Tabs.Tab id="favorites" className={tabClass}>
              Saved ({favorites.data?.length ?? 0})
              <Tabs.Indicator className="rounded-full bg-white" />
            </Tabs.Tab>
            <Tabs.Tab id="ratings" className={tabClass}>
              Ratings ({ratings.data?.length ?? 0})
              <Tabs.Indicator className="rounded-full bg-white" />
            </Tabs.Tab>
            <Tabs.Tab id="history" className={tabClass}>
              History
              <Tabs.Indicator className="rounded-full bg-white" />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>

        <Tabs.Panel id="favorites" className="pt-8">
          {favorites.error && <ErrorAlert error={favorites.error} />}
          {favorites.data?.length === 0 && <Empty>Nothing saved yet. Open any film and tap “Add to my list”.</Empty>}
          <div data-testid="favorites-grid">
            <MovieGrid items={favorites.data?.map((f) => ({ item: f.item }))} loading={favorites.isLoading} />
          </div>
        </Tabs.Panel>

        <Tabs.Panel id="ratings" className="pt-8">
          {ratings.error && <ErrorAlert error={ratings.error} />}
          {ratings.data?.length === 0 && <Empty>No ratings yet.</Empty>}
          {ratings.isLoading ? (
            <MovieGrid items={undefined} loading />
          ) : (
            <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
              {ratings.data?.map((r) => (
                <MovieCard key={r.item.id} item={r.item} extra={<div className="mt-1.5"><RatingStars size="sm" value={r.rating} label={`Your rating for ${r.item.title}`} /></div>} />
              ))}
            </div>
          )}
        </Tabs.Panel>

        <Tabs.Panel id="history" className="pt-6">
          {history.error && <ErrorAlert error={history.error} />}
          {history.data?.length === 0 && <Empty>No activity yet.</Empty>}
          <ul className="flex flex-col gap-2">
            {history.data?.map((h) => (
              <li key={h.id} className="flex items-center gap-4 rounded-2xl bg-surface-1 p-3 ring-1 ring-line">
                {h.item ? (
                  <Link to={`/movie/${h.item.id}`} className="aspect-[2/3] w-10 shrink-0 overflow-hidden rounded-md" tabIndex={-1} aria-hidden>
                    <Poster item={h.item} />
                  </Link>
                ) : (
                  <span className="grid aspect-[2/3] w-10 shrink-0 place-items-center rounded-md bg-surface-3" aria-hidden>
                    <Search className="size-4 text-text-3" />
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-semibold">
                    <HistoryIcon row={h} />
                    <span className="uppercase tracking-wide text-text-3">
                      {h.kind}
                      {h.kind === "rate" && h.value !== null && ` ${h.value}★`}
                      {h.kind === "favorite" && (h.value ? " +" : " −")}
                    </span>
                  </p>
                  {h.item ? (
                    <Link className="block truncate font-semibold hover:text-brand" to={`/movie/${h.item.id}`}>
                      {h.item.title}
                    </Link>
                  ) : (
                    <span className="block truncate text-text-2">“{h.query}”</span>
                  )}
                </div>
                <time className="shrink-0 text-xs text-text-3 tabular" dateTime={h.created_at}>
                  {new Date(h.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                </time>
              </li>
            ))}
          </ul>
        </Tabs.Panel>
      </Tabs>
    </div>
  );
}
