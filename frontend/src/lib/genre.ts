// Film-stock tones per genre: [background, ink, motif]. Shared by covers and onboarding tiles.
export const GENRE_TONES: Record<string, readonly [string, string, string]> = {
  Drama: ["#4a1d1a", "#f3e6d4", "#b0483a"],
  Comedy: ["#7a5813", "#fbf1d6", "#e9b440"],
  Action: ["#6a2914", "#f9e7d6", "#e46a2e"],
  Adventure: ["#3d4318", "#f1edd6", "#aab04b"],
  Animation: ["#1c3465", "#eaeffb", "#6890e4"],
  "Children's": ["#23503a", "#e6f2e8", "#71c28c"],
  Crime: ["#27221f", "#eee7dc", "#b6412f"],
  Documentary: ["#443e33", "#efe9dd", "#bcac8c"],
  Fantasy: ["#37254d", "#f0e8f8", "#a183d6"],
  "Film-Noir": ["#141312", "#ece8df", "#8e8a83"],
  Horror: ["#16211a", "#e6ece2", "#8e2421"],
  Musical: ["#5d1f46", "#f9e7f1", "#e27db3"],
  Mystery: ["#23253f", "#e9e9f6", "#8086cc"],
  Romance: ["#63323b", "#f9eaeb", "#e78c98"],
  "Sci-Fi": ["#0e373b", "#e1f1f1", "#40b8b1"],
  Thriller: ["#1f272e", "#e7ecef", "#cfa43d"],
  War: ["#3d3c2b", "#ecebdd", "#9f9b73"],
  Western: ["#5c3720", "#f7eadb", "#d48c4b"],
};

const FALLBACK = ["#2a2622", "#eee7dc", "#9a8f7d"] as const;

export function toneFor(genres: string[]) {
  return GENRE_TONES[genres[0] ?? ""] ?? FALLBACK;
}

/** Small deterministic hash (stable across sessions) used to vary cover layouts. */
export function hash(n: number): number {
  let x = (n ^ 0x9e3779b9) >>> 0;
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b) >>> 0;
  x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35) >>> 0;
  return (x ^ (x >>> 16)) >>> 0;
}

export const fmtCount = (n: number) => n.toLocaleString("en-US");
