// Spotify-style tile colours per genre (also used for artwork fallbacks).
export const GENRE_COLORS: Record<string, string> = {
  Action: "#e2492f",
  Adventure: "#d97a1c",
  Animation: "#2d6cdf",
  "Children's": "#1e9e6a",
  Comedy: "#d4a017",
  Crime: "#6b4bd1",
  Documentary: "#4f7d6e",
  Drama: "#b8336a",
  Fantasy: "#8b45c9",
  "Film-Noir": "#3d3d4d",
  Horror: "#8c1c23",
  Musical: "#d6488c",
  Mystery: "#3c4fb0",
  Romance: "#e0507a",
  "Sci-Fi": "#0f8c99",
  Thriller: "#4a5a6a",
  War: "#6d6a3a",
  Western: "#a5632d",
};

export function genreColor(genres: string[] | string | undefined): string {
  const g = Array.isArray(genres) ? genres[0] : genres;
  return (g && GENRE_COLORS[g]) || "#3a3a4a";
}

/** Small deterministic hash (stable across sessions) used to vary fallback artwork. */
export function hash(n: number): number {
  let x = (n ^ 0x9e3779b9) >>> 0;
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b) >>> 0;
  x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35) >>> 0;
  return (x ^ (x >>> 16)) >>> 0;
}

export const compact = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k` : String(n));
