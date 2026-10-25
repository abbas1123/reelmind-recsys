import { Tabs } from "@heroui/react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api/client";
import { ErrorAlert } from "../components/Feedback";
import { MovieCard } from "../components/MovieCard";
import { MovieGrid } from "../components/MovieRow";
import { RatingStars } from "../components/RatingStars";
import { useProfile } from "../state/profile";

const tabClass =
  "h-10 rounded-none bg-transparent px-0 text-[13px] text-paper-3 data-[selected]:text-paper data-[hovered]:text-paper";

export default function MePage() {
  const { profileId, profile } = useProfile();
  const ratings = useQuery({ queryKey: ["ratings", profileId], queryFn: () => api.ratings(profileId!) });
  const favorites = useQuery({ queryKey: ["favorites", profileId], queryFn: () => api.favorites(profileId!) });
  const history = useQuery({ queryKey: ["history", profileId], queryFn: () => api.history(profileId!, 100) });

  return (
    <div className="flex flex-col gap-10">
      <header>
        <p className="kicker">Your archive</p>
        <h1 className="mt-3 font-display text-[48px] leading-[0.95] tracking-[-0.02em] sm:text-[64px]">{profile?.display_name ?? "My list"}</h1>
        {profile?.ml_user_id && (
          <p className="mt-3 text-sm text-paper-2">
            This profile also carries MovieLens user #{profile.ml_user_id}&rsquo;s original ratings, which are not listed here.
          </p>
        )}
      </header>

      <Tabs aria-label="My activity" defaultSelectedKey="favorites">
        <Tabs.ListContainer className="border-b border-rule">
          <Tabs.List className="gap-8 bg-transparent p-0">
            <Tabs.Tab id="favorites" className={tabClass}>
              Saved <span className="ml-1 font-mono text-[11px]">{favorites.data?.length ?? 0}</span>
              <Tabs.Indicator className="rounded-none bg-amber" />
            </Tabs.Tab>
            <Tabs.Tab id="ratings" className={tabClass}>
              Ratings <span className="ml-1 font-mono text-[11px]">{ratings.data?.length ?? 0}</span>
              <Tabs.Indicator className="rounded-none bg-amber" />
            </Tabs.Tab>
            <Tabs.Tab id="history" className={tabClass}>
              History
              <Tabs.Indicator className="rounded-none bg-amber" />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>

        <Tabs.Panel id="favorites" className="pt-8">
          {favorites.error && <ErrorAlert error={favorites.error} />}
          {favorites.data?.length === 0 && <p className="font-display text-2xl text-paper-3">Nothing saved yet. Open a film and add it to your list.</p>}
          <div data-testid="favorites-grid">
            <MovieGrid items={favorites.data?.map((f) => ({ item: f.item }))} loading={favorites.isLoading} />
          </div>
        </Tabs.Panel>

        <Tabs.Panel id="ratings" className="pt-8">
          {ratings.error && <ErrorAlert error={ratings.error} />}
          {ratings.data?.length === 0 && <p className="font-display text-2xl text-paper-3">No ratings yet.</p>}
          <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {ratings.data?.map((r) => (
              <MovieCard
                key={r.item.id}
                item={r.item}
                extra={
                  <div className="mt-1">
                    <RatingStars size="sm" value={r.rating} label={`Your rating for ${r.item.title}`} />
                  </div>
                }
              />
            ))}
          </div>
        </Tabs.Panel>

        <Tabs.Panel id="history" className="pt-6">
          {history.error && <ErrorAlert error={history.error} />}
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-b border-rule text-left">
                <th className="kicker py-2 font-normal">When</th>
                <th className="kicker py-2 font-normal">Action</th>
                <th className="kicker py-2 font-normal">Subject</th>
              </tr>
            </thead>
            <tbody>
              {history.data?.map((h) => (
                <tr key={h.id} className="border-b border-rule">
                  <td className="py-2.5 pr-4 font-mono text-[11px] text-paper-3 tabular">
                    <time dateTime={h.created_at}>{new Date(h.created_at).toLocaleString("en-GB")}</time>
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-[11px] uppercase tracking-[0.12em] text-paper-2">
                    {h.kind}
                    {h.kind === "rate" && h.value !== null && ` ${h.value}★`}
                    {h.kind === "favorite" && (h.value ? " +" : " −")}
                  </td>
                  <td className="py-2.5">
                    {h.item ? (
                      <Link className="link-underline" to={`/movie/${h.item.id}`}>
                        {h.item.title}
                      </Link>
                    ) : (
                      <span className="font-display text-[16px] italic text-paper-2">“{h.query}”</span>
                    )}
                  </td>
                </tr>
              ))}
              {history.data?.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-6 text-paper-3">
                    No activity yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Tabs.Panel>
      </Tabs>
    </div>
  );
}
