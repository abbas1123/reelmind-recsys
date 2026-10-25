import { Button, Input, Label, SearchField, TextField } from "@heroui/react";
import { useInfiniteQuery, useQueries, useQuery } from "@tanstack/react-query";
import { Sparkles, Type } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigationType, useSearchParams } from "react-router";
import { api } from "../api/client";
import type { Genre } from "../api/types";
import { FilterList, Segmented } from "../components/Controls";
import { ErrorAlert } from "../components/Feedback";
import { MovieGrid, SectionHeading } from "../components/MovieRow";
import { Poster } from "../components/Poster";
import { genreColor } from "../lib/genre";
import { useProfile } from "../state/profile";

type Mode = "keyword" | "semantic";
const PAGE = 24;

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const yearInput = "h-10 w-24 rounded-full bg-surface-2 px-4 text-sm tabular ring-1 ring-line focus:ring-2 focus:ring-brand";

export default function DiscoverPage() {
  const { profileId } = useProfile();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [mode, setMode] = useState<Mode>((params.get("mode") as Mode) ?? "keyword");
  const [genre, setGenre] = useState<string | null>(params.get("genre"));
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const query = useDebounced(q.trim());
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const genres = useQuery({ queryKey: ["genres"], queryFn: api.genres });

  // Links and back/forward to /discover (same page, new URL) must reset the filters; our own URL updates use
  // `replace`, so they are skipped and never overwrite what the user is typing.
  const location = useLocation();
  const navigationType = useNavigationType();
  useEffect(() => {
    if (navigationType === "REPLACE") return;
    setQ(params.get("q") ?? "");
    setMode((params.get("mode") as Mode) ?? "keyword");
    setGenre(params.get("genre"));
  }, [location.key]);

  useEffect(() => {
    const next: Record<string, string> = {};
    if (query) next.q = query;
    if (mode !== "keyword") next.mode = mode;
    if (genre) next.genre = genre;
    setParams(next, { replace: true });
  }, [query, mode, genre, setParams]);

  const yf = /^\d{4}$/.test(yearFrom) ? Number(yearFrom) : undefined;
  const yt = /^\d{4}$/.test(yearTo) ? Number(yearTo) : undefined;
  const search = useQuery({
    queryKey: ["search", query, mode, genre, yf, yt],
    queryFn: async () => {
      const res = await api.search(query, { mode, genre, year_from: yf, year_to: yt, k: 48 });
      if (profileId) api.logInteraction(profileId, "search", undefined, query).catch(() => undefined);
      return res;
    },
    enabled: query.length > 0,
  });
  const browse = useInfiniteQuery({
    queryKey: ["browse", genre],
    queryFn: ({ pageParam }) => api.genreItems(genre!, { sort: "popular", limit: PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (pages.length * PAGE < last.total ? pages.length * PAGE : undefined),
    enabled: query.length === 0 && genre !== null,
  });
  const trending = useQuery({
    queryKey: ["trending", 48],
    queryFn: () => api.trending(48),
    enabled: query.length === 0 && genre === null,
  });

  const semanticOk = health.data?.semantic_search ?? false;
  const idle = !query && genre === null;

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-5">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">Discover</h1>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <SearchField value={q} onChange={setQ} aria-label="Search films" className="flex-1">
            <Label className="sr-only">Search</Label>
            <SearchField.Group className="h-14 rounded-full bg-surface-2 px-5 shadow-none ring-1 ring-line focus-within:ring-2 focus-within:ring-brand">
              <SearchField.SearchIcon className="size-5 text-text-3" />
              <SearchField.Input
                placeholder={mode === "semantic" ? "Describe a mood: “a heist that goes wrong”, “lonely robot in space”…" : "Search by title, theme or tag…"}
                data-testid="search-input"
                className="h-full bg-transparent text-base placeholder:text-text-3"
              />
              <SearchField.ClearButton />
            </SearchField.Group>
          </SearchField>
          <Segmented
            label="Search mode"
            value={mode}
            onChange={setMode}
            options={[
              { value: "keyword", label: <><Type className="size-4" aria-hidden /> Keyword</> },
              { value: "semantic", label: <><Sparkles className="size-4" aria-hidden /> AI semantic</>, disabled: !semanticOk, testId: "mode-semantic" },
            ]}
          />
        </div>
        {!idle && (
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
            <div className="min-w-0 flex-1">
              <FilterList label="Genre filter" value={genre} onChange={setGenre} options={genres.data?.map((g) => ({ name: g.name, count: g.n_items })) ?? []} />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <TextField value={yearFrom} onChange={setYearFrom} aria-label="From year">
                <Label className="sr-only">From year</Label>
                <Input inputMode="numeric" placeholder="From" className={yearInput} />
              </TextField>
              <span className="text-text-3">–</span>
              <TextField value={yearTo} onChange={setYearTo} aria-label="To year">
                <Label className="sr-only">To year</Label>
                <Input inputMode="numeric" placeholder="To" className={yearInput} />
              </TextField>
            </div>
          </div>
        )}
      </header>

      {query ? (
        <section aria-label="Search results" className="flex flex-col gap-5">
          <SectionHeading
            title={search.data ? (search.data.mode === "semantic" ? `Top ${search.data.results.length} by meaning` : `${search.data.total} results`) : "Searching…"}
            subtitle={
              <span data-testid="search-summary">
                {search.data
                  ? search.data.mode === "semantic"
                    ? `Closest films to “${search.data.query}” (semantic, local embeddings — every film is scored, so there is no match count)`
                    : `${search.data.total} matches for “${search.data.query}” (keyword)`
                  : ""}
              </span>
            }
          />
          {search.error && <ErrorAlert error={search.error} />}
          <MovieGrid items={search.data?.results.map((r) => ({ item: r.item }))} loading={search.isLoading} explore />
          {search.data?.total === 0 && <p className="text-text-3">No matches. Try AI semantic mode or fewer filters.</p>}
        </section>
      ) : genre === null ? (
        <>
          <section aria-label="Browse all" className="flex flex-col gap-5">
            <SectionHeading title="Browse all" subtitle="Every genre in the MovieLens catalogue" />
            <BrowseTiles genres={genres.data ?? []} onPick={setGenre} />
          </section>
          <section aria-label="Trending" className="flex flex-col gap-5">
            <SectionHeading title="Trending at the end of the dataset" subtitle="Recency-weighted popularity — half-life counted in interactions, chosen on validation." />
            {trending.error && <ErrorAlert error={trending.error} />}
            <MovieGrid items={trending.data?.map((item) => ({ item }))} loading={trending.isLoading} explore />
          </section>
        </>
      ) : (
        <section aria-label={`Browse ${genre}`} className="flex flex-col gap-5">
          <SectionHeading title={`Most rated: ${genre}`} subtitle={browse.data ? `${browse.data.pages[0].total} films` : undefined} />
          {browse.error && <ErrorAlert error={browse.error} />}
          <MovieGrid items={browse.data?.pages.flatMap((p) => p.items).map((item) => ({ item }))} loading={browse.isLoading} />
          {browse.hasNextPage && (
            <Button variant="secondary" className="self-center rounded-full px-6" onPress={() => browse.fetchNextPage()} isDisabled={browse.isFetchingNextPage}>
              Load more
            </Button>
          )}
        </section>
      )}
    </div>
  );
}

/** Spotify-style coloured genre tiles with the genre's most-rated poster tilted in the corner. */
function BrowseTiles({ genres, onPick }: { genres: Genre[]; onPick: (g: string) => void }) {
  const covers = useQueries({
    queries: genres.map((g) => ({
      queryKey: ["genreCover", g.name],
      queryFn: () => api.genreItems(g.name, { sort: "popular", limit: 1 }),
      staleTime: Infinity,
    })),
  });
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {genres.map((g, i) => {
        const cover = covers[i]?.data?.items[0];
        return (
          <button
            key={g.name}
            type="button"
            onClick={() => onPick(g.name)}
            className="group relative h-32 overflow-hidden rounded-2xl p-4 text-left outline-none transition duration-300 hover:scale-[1.03] focus-visible:ring-2 focus-visible:ring-white"
            style={{ background: genreColor(g.name) }}
          >
            <span className="relative z-10 block text-lg font-extrabold leading-tight text-white">{g.name}</span>
            <span className="relative z-10 mt-1 block text-xs font-semibold text-white/80">{g.n_items} films</span>
            {cover && (
              <span className="absolute -bottom-2 -right-4 aspect-[2/3] w-20 rotate-[22deg] overflow-hidden rounded-md shadow-xl shadow-black/50 transition duration-300 group-hover:rotate-[16deg]" aria-hidden>
                <Poster item={cover} />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
