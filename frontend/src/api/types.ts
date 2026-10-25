// Mirrors backend/app/schemas.py

export interface Item {
  id: number;
  domain: string;
  title: string;
  year: number | null;
  genres: string[];
  tags: string[];
  n_ratings: number;
  mean_rating: number | null;
  external_ids: Record<string, unknown>;
  poster_url: string | null;
}

export interface ItemDetail extends Item {
  user_rating: number | null;
  is_favorite: boolean;
}

export interface ScoredItem {
  item: Item;
  score: number;
  reason: string | null;
  source: string | null;
  because_item_id: number | null;
}

export interface RecSection {
  key: string;
  title: string;
  items: ScoredItem[];
}

export type Bucket = "cold" | "light" | "warm";
export type Strategy = "hybrid" | "cf" | "content" | "popularity";

export interface RecommendationsResponse {
  user_id: number;
  strategy: Strategy;
  history_size: number;
  bucket: Bucket;
  sections: RecSection[];
}

export interface User {
  id: number;
  display_name: string;
  ml_user_id: number | null;
  onboarding_done: boolean;
  created_at: string;
  n_ratings: number;
  n_favorites: number;
  preferred_genres: string[];
}

export interface Genre {
  name: string;
  n_items: number;
}

export interface RatingRow {
  item: Item;
  rating: number;
  created_at: string;
}

export interface FavoriteRow {
  item: Item;
  created_at: string;
}

export interface InteractionRow {
  id: number;
  kind: string;
  item: Item | null;
  query: string | null;
  value: number | null;
  created_at: string;
}

export interface SearchResponse {
  query: string;
  mode: "keyword" | "semantic";
  total: number;
  results: ScoredItem[];
}

export interface Page {
  total: number;
  items: Item[];
}

export interface Health {
  status: "ok" | "degraded";
  engine_loaded: boolean;
  semantic_search: boolean;
  items_in_db: number;
  detail: string | null;
}

// ---- evaluation report (artifacts/reports/model_comparison.json) ----
export type MetricMap = Record<string, number>;

export interface RankingResult {
  n_users: number;
  metrics: MetricMap;
  ci95?: Record<string, [number, number]>;
  beyond: MetricMap;
  segments?: Record<string, { n_users: number; "ndcg@10": number; "recall@20": number }>;
  [key: string]: unknown;
}

export interface RatingResult {
  n_ratings: number;
  rmse: number;
  mae: number;
  rmse_warm: number | null;
  mae_warm: number | null;
}

export interface ModelEntry {
  family: string;
  skipped?: string;
  best_params?: Record<string, unknown>;
  grid?: Array<Record<string, unknown>>;
  val?: RankingResult;
  val_cold?: Record<string, RankingResult>;
  test?: RankingResult;
  test_cold?: Record<string, RankingResult>;
  secondary_test?: RankingResult;
  rating?: { val: RatingResult; test: RatingResult };
  fit_seconds_train_val?: number;
  weight_search?: Record<string, unknown>;
  note?: string;
}

export interface EvaluationReport {
  generated_at: string;
  quick_mode: boolean;
  dataset: Record<string, unknown> & { n_users: number; n_items: number; n_interactions: number };
  protocol: {
    primary_metric: string;
    relevance_threshold: number;
    k_values: number[];
    bootstrap_samples: number;
    tasks: Record<string, number>;
  };
  models: Record<string, ModelEntry>;
  selection: { selected: string; rule: string; ranking: Array<Record<string, number | string>> };
  serving: Record<string, unknown>;
  library_versions: Record<string, string>;
  limitations: string[];
  seed: number;
  total_seconds: number;
}

export interface EdaSummary {
  n_users: number;
  n_items_catalog: number;
  n_items_rated: number;
  n_items_unrated: number;
  n_interactions: number;
  sparsity: number;
  rating_mean: number;
  positive_share: number;
  item_popularity_gini: number;
  time_range: { min: string; max: string };
  items_with_tags: number;
  charts: string[];
  [key: string]: unknown;
}
