import { Button, Input, Label, SearchField, TextField } from "@heroui/react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { api } from "../api/client";
import { FilterList, Segmented } from "../components/Controls";
import { ErrorAlert } from "../components/Feedback";
import { MovieGrid, SectionHeading } from "../components/MovieRow";
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

const yearInput = "h-9 w-20 rounded-none border-0 border-b border-rule-strong bg-transparent px-0 font-mono text-[13px] shadow-none focus:border-amber";

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

  return (
    <div className="flex flex-col gap-12">
      <header className="flex flex-col gap-8">
        <div className="grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <p className="kicker">Discover · 3,883 films</p>
            <h1 className="mt-3 font-display text-[48px] leading-[0.95] tracking-[-0.02em] sm:text-[64px]">Search the archive</h1>
          </div>
          <Segmented
            label="Search mode"
            value={mode}
            onChange={setMode}
            options={[
              { value: "keyword", label: "Keyword" },
              { value: "semantic", label: "Semantic · local model", disabled: !semanticOk, testId: "mode-semantic" },
            ]}
          />
        </div>

        <SearchField value={q} onChange={setQ} aria-label="Search films" className="w-full">
          <Label className="sr-only">Search</Label>
          <SearchField.Group className="h-auto rounded-none border-0 border-b border-paper bg-transparent px-0 shadow-none">
            <SearchField.Input
              placeholder={mode === "semantic" ? "Describe it — “a heist that goes wrong”, “lonely robot in space”…" : "Title, theme or tag…"}
              data-testid="search-input"
              className="h-16 bg-transparent px-0 font-display text-[28px] placeholder:text-paper-3 sm:text-[34px]"
            />
            <SearchField.ClearButton />
          </SearchField.Group>
        </SearchField>

        <div className="flex flex-col gap-4 md:flex-row md:items-end md:gap-8">
          <div className="min-w-0 flex-1">
            <p className="kicker mb-2">Genre</p>
            <FilterList label="Genre filter" value={genre} onChange={setGenre} options={genres.data?.map((g) => ({ name: g.name, count: g.n_items })) ?? []} />
          </div>
          <div className="flex shrink-0 items-end gap-4">
            <TextField value={yearFrom} onChange={setYearFrom} aria-label="From year" className="flex flex-col gap-1">
              <Label className="kicker">From</Label>
              <Input inputMode="numeric" placeholder="1919" className={yearInput} />
            </TextField>
            <TextField value={yearTo} onChange={setYearTo} aria-label="To year" className="flex flex-col gap-1">
              <Label className="kicker">To</Label>
              <Input inputMode="numeric" placeholder="2000" className={yearInput} />
            </TextField>
          </div>
        </div>
      </header>

      {query ? (
        <section aria-label="Search results" className="flex flex-col gap-6">
          <SectionHeading
            title={search.data ? `${search.data.total} results` : "Searching…"}
            aside={<span className="kicker">{mode === "semantic" ? "all-MiniLM-L6-v2 · on this machine" : "title match + TF-IDF"}</span>}
          >
            <span data-testid="search-summary">
              {search.data
                ? `${search.data.total} matches for “${search.data.query}” (${search.data.mode === "semantic" ? "semantic, local embeddings" : "keyword"})`
                : ""}
            </span>
          </SectionHeading>
          {search.error && <ErrorAlert error={search.error} />}
          <MovieGrid items={search.data?.results.map((r) => ({ item: r.item }))} loading={search.isLoading} />
          {search.data?.total === 0 && <p className="text-paper-3">No matches. Try semantic mode or fewer filters.</p>}
        </section>
      ) : genre === null ? (
        <section aria-label="Trending" className="flex flex-col gap-6">
          <SectionHeading index="01" title="Trending at the end of the dataset">
            Recency-weighted popularity — half-life counted in interactions, chosen on validation. Choose a genre to browse it.
          </SectionHeading>
          {trending.error && <ErrorAlert error={trending.error} />}
          <MovieGrid items={trending.data?.map((item) => ({ item }))} loading={trending.isLoading} />
        </section>
      ) : (
        <section aria-label={`Browse ${genre}`} className="flex flex-col gap-6">
          <SectionHeading index="01" title={`Most rated: ${genre}`} aside={browse.data && <span className="kicker">{browse.data.pages[0].total} films</span>} />
          {browse.error && <ErrorAlert error={browse.error} />}
          <MovieGrid items={browse.data?.pages.flatMap((p) => p.items).map((item) => ({ item }))} loading={browse.isLoading} />
          {browse.hasNextPage && (
            <Button variant="outline" className="self-center" onPress={() => browse.fetchNextPage()} isDisabled={browse.isFetchingNextPage}>
              Load more
            </Button>
          )}
        </section>
      )}
    </div>
  );
}
