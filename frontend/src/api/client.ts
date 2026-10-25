import type {
  EdaSummary,
  EvaluationReport,
  FavoriteRow,
  Genre,
  Health,
  InteractionRow,
  Item,
  ItemDetail,
  Page,
  RatingRow,
  RecommendationsResponse,
  ScoredItem,
  SearchResponse,
  Strategy,
  User,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | string[] | null | undefined>;

function qs(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
    else sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, params?: Query): Promise<T> {
  const res = await fetch(`/api${path}${qs(params)}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const get = <T>(path: string, params?: Query) => request<T>("GET", path, undefined, params);

export const api = {
  health: () => get<Health>("/health"),

  users: () => get<User[]>("/users"),
  user: (id: number) => get<User>(`/users/${id}`),
  createUser: (display_name: string) => request<User>("POST", "/users", { display_name }),
  movielensProfile: (mlUserId: number) => request<User>("POST", `/users/from-movielens/${mlUserId}`),
  deleteUser: (id: number) => request<void>("DELETE", `/users/${id}`),

  genres: () => get<Genre[]>("/genres"),
  onboardingCandidates: (genres: string[], k = 24) => get<Item[]>("/onboarding/candidates", { genres, k }),
  setPreferences: (id: number, genres: string[]) => request<User>("PUT", `/users/${id}/preferences`, { genres }),

  recommendations: (id: number, opts: { k?: number; genre?: string | null; strategy?: Strategy } = {}) =>
    get<RecommendationsResponse>(`/users/${id}/recommendations`, opts),

  trending: (k = 20, genre?: string | null) => get<Item[]>("/items/trending", { k, genre }),
  topRated: (k = 20, genre?: string | null) => get<Item[]>("/items/top-rated", { k, genre }),
  genreItems: (genre: string, opts: { sort?: string; limit?: number; offset?: number } = {}) =>
    get<Page>(`/genres/${encodeURIComponent(genre)}/items`, opts),
  search: (q: string, opts: { mode?: "keyword" | "semantic"; genre?: string | null; year_from?: number; year_to?: number; k?: number } = {}) =>
    get<SearchResponse>("/search", { q, ...opts }),
  item: (id: number, userId?: number | null) => get<ItemDetail>(`/items/${id}`, { user_id: userId ?? undefined }),
  similar: (id: number, mode: "hybrid" | "collaborative" | "content" = "hybrid", k = 12) =>
    get<ScoredItem[]>(`/items/${id}/similar`, { mode, k }),

  rate: (userId: number, itemId: number, rating: number) =>
    request<RatingRow>("PUT", `/users/${userId}/ratings/${itemId}`, { rating }),
  unrate: (userId: number, itemId: number) => request<void>("DELETE", `/users/${userId}/ratings/${itemId}`),
  ratings: (userId: number) => get<RatingRow[]>(`/users/${userId}/ratings`),
  favorite: (userId: number, itemId: number) => request<FavoriteRow>("PUT", `/users/${userId}/favorites/${itemId}`),
  unfavorite: (userId: number, itemId: number) => request<void>("DELETE", `/users/${userId}/favorites/${itemId}`),
  favorites: (userId: number) => get<FavoriteRow[]>(`/users/${userId}/favorites`),
  logInteraction: (userId: number, kind: "view" | "click" | "search", itemId?: number, query?: string) =>
    request<InteractionRow>("POST", `/users/${userId}/interactions`, { kind, item_id: itemId, query }),
  history: (userId: number, limit = 50) => get<InteractionRow[]>(`/users/${userId}/history`, { limit }),

  modelInfo: () => get<Record<string, unknown>>("/model/info"),
  evaluation: () => get<EvaluationReport>("/model/evaluation"),
  eda: () => get<EdaSummary>("/model/eda"),
};
